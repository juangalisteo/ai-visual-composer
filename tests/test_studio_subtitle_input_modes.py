import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.controllers.run_controller import RunController
from app.core.start import ejecutar_studio
from app.modules.studio import (
    StudioInputMode,
    StudioInputPreparationService,
    StudioProfileLoader,
    StudioRenderResult,
)
from app.modules.subtitles.cue_transformer import SubtitleCueTransformer
from app.modules.subtitles.external_media_subtitles import (
    ExternalMediaSubtitlePreparationService,
)
from app.modules.subtitles.timing import (
    SubtitleTimingResolver,
    whisper_timing_path,
)
from app.shared.profile_identity import ProfileKey
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


class StudioSubtitleInputModesTest(unittest.TestCase):

    SOURCE_SRT = (
        "1\n"
        "00:00:01,000 --> 00:00:04,000\n"
        "Bienvenidos todos a Modo Conciencia.\n"
    )

    def setUp(self):
        self.profile_key = ProfileKey.for_component("studio", "instagram")
        self.profile = StudioProfileLoader().load(
            ProfileResolver().load(self.profile_key),
            self.profile_key,
        )

    def _subtitle_profile(self, style):
        return SubtitleProfileResolver().load(
            SubtitleProfileKey.for_profile(self.profile_key, style)
        )

    def test_selected_srt_video_directory_ignores_video_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            srt_video = root / "srt_video"
            video = root / "video"
            srt_video.mkdir()
            video.mkdir()
            source_video = srt_video / "source.mp4"
            source_srt = srt_video / "human.srt"
            source_video.write_bytes(b"source")
            source_srt.write_text(self.SOURCE_SRT, encoding="utf-8")
            (video / "unexpected-one.mp4").write_bytes(b"one")
            (video / "unexpected-two.mp4").write_bytes(b"two")

            prepared = StudioInputPreparationService(root).prepare(
                self.profile,
                StudioInputMode.SRT_VIDEO,
            )

        self.assertEqual(source_video, prepared.video_path)
        self.assertEqual(source_srt, prepared.subtitle_path)

    def test_selected_video_directory_ignores_srt_video_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            srt_video = root / "srt_video"
            video = root / "video"
            srt_video.mkdir()
            video.mkdir()
            (srt_video / "unexpected-one.mp4").write_bytes(b"one")
            (srt_video / "unexpected-two.mp4").write_bytes(b"two")
            selected_video = video / "source.mp4"
            selected_video.write_bytes(b"source")

            prepared = StudioInputPreparationService(root).prepare(
                self.profile,
                StudioInputMode.VIDEO,
            )

        self.assertEqual(selected_video, prepared.video_path)
        self.assertIsNone(prepared.subtitle_path)
        self.assertEqual(StudioInputMode.VIDEO, prepared.mode)

    def test_srt_source_is_authoritative_with_common_fallback_models(self):
        source = self.SOURCE_SRT
        source_hash = hashlib.sha256(source.encode("utf-8")).digest()
        single_line = SubtitleCueTransformer(
            self._subtitle_profile("single_line"),
            self.profile.fps,
        ).transform(source)
        word_by_word = SubtitleCueTransformer(
            self._subtitle_profile("word_by_word"),
            self.profile.fps,
        ).transform(source)

        self.assertIn("Bienvenidos todos a Modo Conciencia.", single_line)
        self.assertIn("00:00:01,000 --> 00:00:04,000", single_line)
        self.assertIn("Bienvenidos", word_by_word)
        self.assertIn("Conciencia", word_by_word)
        self.assertNotIn("Conciencia.", word_by_word)
        self.assertEqual(source_hash, hashlib.sha256(source.encode("utf-8")).digest())

    def test_video_preparation_uses_common_whisper_sidecar_and_real_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video_path = root / "external.mp4"
            video_path.write_bytes(b"video")
            runner = _AudioExtractionRunner()
            builder = _WhisperSubtitleBuilder()
            prepared = ExternalMediaSubtitlePreparationService(
                runner=runner,
                subtitle_builder=builder,
                timing_resolver=SubtitleTimingResolver(),
            ).prepare(video_path, root / "working")
            output = SubtitleCueTransformer(
                self._subtitle_profile("word_by_word"),
                self.profile.fps,
            ).transform(
                prepared.subtitle_path.read_text(encoding="utf-8"),
                timing=prepared.timing,
            )

        self.assertIn("-map", runner.command)
        self.assertIn("0:a:0", runner.command)
        self.assertEqual("whisper", prepared.timing.source)
        self.assertIn("00:00:00,000 --> 00:00:00,200", output)
        self.assertIn("00:00:00,900 --> 00:00:01,200", output)

    def test_video_runtime_persists_base_and_render_derivative(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            preparation = SimpleNamespace(
                video_path=Path("input/studio/video/source.mp4"),
                subtitle_path=None,
                input_mode="video",
                profile_key=self.profile_key,
                profile=self.profile,
                subtitle_profile=self._subtitle_profile("word_by_word"),
            )
            subtitle_service = _CapturingSubtitlePreparation()
            renderer = Mock()
            output_path = root / "demo" / "video" / "demo.mp4"
            renderer.render.return_value = StudioRenderResult(
                source_video_path=preparation.video_path,
                source_subtitle_path=Path("temporary/whisper.srt"),
                output_path=output_path,
                command=(),
                expected_duration=1.2,
                generated_duration=1.2,
                source_had_audio=True,
                silence_added=False,
                music_path=None,
            )
            resolver = Mock(resolve=Mock(return_value=output_path))

            with patch(
                "app.core.start.time.perf_counter",
                side_effect=(10.0, 12.5),
            ), patch(
                "app.core.start.ProgressLogger"
            ) as progress_logger:
                result = ejecutar_studio(
                    subtitle_style="word_by_word",
                    input_mode="video",
                    preparation_service=Mock(return_value=preparation),
                    external_subtitle_preparation_service=subtitle_service,
                    render_service=renderer,
                    output_path_resolver=resolver,
                    project=Mock(),
                )

            base = root / "demo" / "subtitles" / "demo.srt"
            persisted = root / "demo" / "subtitles" / "demo_word_by_word.srt"
            self.assertEqual(
                "1\n00:00:00,000 --> 00:00:01,200\nuno dos\n",
                base.read_text(encoding="utf-8"),
            )
            self.assertNotEqual(
                base.read_text(encoding="utf-8"),
                persisted.read_text(encoding="utf-8"),
            )
            self.assertEqual(persisted, result.generated_subtitle_path)
            self.assertEqual(base, result.base_subtitle_path)
            self.assertEqual(2.5, result.subtitle_preparation_duration)
            progress_logger.start.assert_called_once_with(
                "PREPARANDO SUBTÍTULOS"
            )
            progress_logger.finish.assert_called_once_with(
                "SUBTÍTULOS PREPARADOS",
                2.5,
            )
            kwargs = renderer.render.call_args.kwargs
            self.assertEqual(persisted, kwargs["subtitle_path"])
            self.assertNotIn("subtitle_timing", kwargs)
            self.assertFalse(subtitle_service.subtitle_path.exists())
            self.assertFalse(subtitle_service.audio_path.exists())
            self.assertFalse(subtitle_service.subtitle_path.parent.exists())

    def test_srt_video_persists_immutable_base_and_render_derivative(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            human_srt = root / "human.srt"
            human_srt.write_text(self.SOURCE_SRT, encoding="utf-8")
            source_bytes = human_srt.read_bytes()
            preparation = SimpleNamespace(
                video_path=root / "source.mp4",
                subtitle_path=human_srt,
                input_mode="srt_video",
                profile_key=self.profile_key,
                profile=self.profile,
                subtitle_profile=self._subtitle_profile("single_line"),
            )
            renderer = Mock()
            renderer.render.return_value = "rendered"
            output_path = root / "demo" / "video" / "demo.mp4"
            resolver = Mock(resolve=Mock(return_value=output_path))

            result = ejecutar_studio(
                subtitle_style="single_line",
                input_mode="srt_video",
                preparation_service=Mock(return_value=preparation),
                render_service=renderer,
                output_path_resolver=resolver,
                project=Mock(),
            )

            self.assertEqual("rendered", result)
            base = root / "demo" / "subtitles" / "demo.srt"
            derived = root / "demo" / "subtitles" / "demo_single_line.srt"
            self.assertEqual(source_bytes, human_srt.read_bytes())
            self.assertEqual(self.SOURCE_SRT, base.read_text(encoding="utf-8"))
            self.assertNotEqual(base.read_text(encoding="utf-8"), derived.read_text(encoding="utf-8"))
            self.assertEqual(
                derived,
                renderer.render.call_args.kwargs["subtitle_path"],
            )

    def test_srt_video_original_preserves_the_persisted_base_for_render(self):
        source = (
            "1\n"
            "00:00:10,000 --> 00:00:11,500\n"
            "MATEO 13\n"
            "Con puntuacion.\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            human_srt = root / "human.srt"
            human_srt.write_text(source, encoding="utf-8")
            source_bytes = human_srt.read_bytes()
            preparation = SimpleNamespace(
                video_path=root / "source.mp4",
                subtitle_path=human_srt,
                input_mode="srt_video",
                profile_key=self.profile_key,
                profile=self.profile,
                subtitle_profile=self._subtitle_profile("word_by_word"),
                subtitle_original=True,
            )
            renderer = Mock()
            renderer.render.return_value = "rendered"
            output_path = root / "demo" / "video" / "demo.mp4"

            with patch("app.core.start.SubtitleCueTransformer") as transformer:
                ejecutar_studio(
                    subtitle_style="word_by_word",
                    input_mode="srt_video",
                    preparation_service=Mock(return_value=preparation),
                    render_service=renderer,
                    output_path_resolver=Mock(resolve=Mock(return_value=output_path)),
                    project=Mock(),
                    subtitle_original=True,
                )

            base = root / "demo" / "subtitles" / "demo.srt"
            self.assertEqual(source_bytes, human_srt.read_bytes())
            self.assertEqual(source, base.read_text(encoding="utf-8"))
            self.assertEqual(base, renderer.render.call_args.kwargs["subtitle_path"])
            transformer.assert_not_called()

    def test_video_rejects_original_before_whisper_or_render(self):
        subtitle_service = Mock()
        renderer = Mock()

        with self.assertRaisesRegex(
            ValueError,
            "ORIGINAL solo esta disponible para STUDIO SRT \\+ VIDEO",
        ):
            ejecutar_studio(
                subtitle_style="single_line",
                input_mode="video",
                subtitle_original=True,
                external_subtitle_preparation_service=subtitle_service,
                render_service=renderer,
            )

        subtitle_service.prepare.assert_not_called()
        renderer.render.assert_not_called()

    def test_original_preserves_srt_base_for_both_studio_platforms(self):
        source = "1\n00:00:00,000 --> 00:00:01,000\nMATEO 13\n"
        for platform in ("instagram", "youtube"):
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                profile_key = ProfileKey.for_component("studio", platform)
                profile = StudioProfileLoader().load(
                    ProfileResolver().load(profile_key),
                    profile_key,
                )
                subtitle_profile = SubtitleProfileResolver().load(
                    SubtitleProfileKey.for_profile(profile_key, "word_by_word")
                )
                human_srt = root / "human.srt"
                human_srt.write_text(source, encoding="utf-8")
                preparation = SimpleNamespace(
                    video_path=root / "source.mp4",
                    subtitle_path=human_srt,
                    input_mode="srt_video",
                    profile_key=profile_key,
                    profile=profile,
                    subtitle_profile=subtitle_profile,
                    subtitle_original=True,
                )
                renderer = Mock()
                renderer.render.return_value = "rendered"
                output_path = root / "demo" / "video" / "demo.mp4"

                with patch("app.core.start.SubtitleCueTransformer") as transformer:
                    ejecutar_studio(
                        subtitle_style="word_by_word",
                        input_mode="srt_video",
                        subtitle_original=True,
                        preparation_service=Mock(return_value=preparation),
                        render_service=renderer,
                        output_path_resolver=Mock(
                            resolve=Mock(return_value=output_path)
                        ),
                        project=Mock(),
                    )

                base = root / "demo" / "subtitles" / "demo.srt"
                self.assertEqual(source, base.read_text(encoding="utf-8"))
                self.assertEqual(base, renderer.render.call_args.kwargs["subtitle_path"])
                transformer.assert_not_called()

    def test_menu_selects_input_before_subtitles(self):
        controller = RunController()
        order = []
        with patch.object(
            controller, "select_profile",
            side_effect=lambda _: order.append("profile") or {
                "profile_key": self.profile_key
            },
        ), patch.object(
            controller, "select_studio_input_mode",
            side_effect=lambda: order.append("input") or "video",
        ), patch.object(
            controller,
            "select_studio_input_files",
            side_effect=lambda *_: order.append("files") or SimpleNamespace(
                video_path=Path("input/studio/video/source.mp4"),
                subtitle_path=None,
            ),
        ), patch.object(
            controller, "select_studio_subtitle_options",
            side_effect=lambda *_: order.append("subtitle") or (
                "single_line",
                False,
            ),
        ), patch.object(
            controller, "select_studio_music", return_value=None,
        ), patch.object(
            controller, "select_studio_intro_outro", return_value=None,
        ), patch.object(
            controller, "ask_project_name", return_value="studio",
        ), patch.object(
            controller, "ask_clear_output", return_value=False,
        ):
            options = controller._run_studio()

        self.assertEqual(["input", "profile", "files", "subtitle"], order)
        self.assertEqual("video", options["studio_input_mode"])

    def test_srt_video_subtitle_choice_is_the_only_style_selection(self):
        controller = RunController()
        messages = []
        controller._print = messages.append
        for selected, expected_style, expected_original in (
            ("original", "single_line", True),
            (
                "subtitulo_studio_instagram_linea_unica",
                "subtitulo_studio_instagram_linea_unica",
                False,
            ),
            (
                "subtitulo_studio_instagram_palabra_por_palabra",
                "subtitulo_studio_instagram_palabra_por_palabra",
                False,
            ),
        ):
            with self.subTest(selected=selected):
                controller._select_from_list = Mock(return_value=selected)
                with patch.object(
                    controller,
                    "select_studio_subtitle_config",
                ) as visual_style:
                    style, original = controller.select_studio_subtitle_options(
                        self.profile_key,
                        StudioInputMode.SRT_VIDEO.value,
                    )

                self.assertEqual(expected_style, style)
                self.assertEqual(expected_original, original)
                visual_style.assert_not_called()
                controller._select_from_list.assert_called_once_with(
                    (
                        "original",
                        "subtitulo_studio_instagram_linea_unica",
                        "subtitulo_studio_instagram_palabra_por_palabra",
                    )
                )

        self.assertIn("\nSUBT\u00cdTULOS\n", messages)
        self.assertIn("1. ORIGINAL", messages)
        self.assertIn("2. Línea única", messages)
        self.assertIn("3. Palabra por palabra", messages)

    def test_video_offers_only_transformed_subtitle_styles(self):
        controller = RunController()
        messages = []
        controller._print = messages.append
        controller._select_from_list = Mock(
            return_value="subtitulo_studio_instagram_linea_unica"
        )

        style, original = controller.select_studio_subtitle_options(
            self.profile_key,
            StudioInputMode.VIDEO.value,
        )

        self.assertEqual("subtitulo_studio_instagram_linea_unica", style)
        self.assertFalse(original)
        self.assertIn("\nSUBT\u00cdTULOS\n", messages)
        self.assertIn("1. Línea única", messages)
        self.assertIn("2. Palabra por palabra", messages)
        self.assertNotIn("ORIGINAL", "\n".join(messages))

    def test_design_profile_uses_declared_style_without_a_second_selector(self):
        profile_key = ProfileKey.for_component(
            "studio",
            "instagram",
            family="design",
            profile_id="studio_instagram_design_modo_conciencia_studio_1",
        )
        controller = RunController()
        controller._print = Mock()
        controller._select_from_list = Mock()

        style, original = controller.select_studio_subtitle_options(
            profile_key,
            StudioInputMode.SRT_VIDEO.value,
        )

        self.assertEqual("word_by_word", style)
        self.assertFalse(original)
        controller._select_from_list.assert_not_called()
        controller._print.assert_not_called()
        self.assertEqual(
            "word_by_word",
            controller.select_studio_subtitle_config(profile_key),
        )

    def test_discovery_accepts_a_future_visual_model_without_menu_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subtitle_dir = root / "studio" / "instagram" / "estandar"
            subtitle_dir.mkdir(parents=True)
            for style in ("single_line", "word_by_word", "modo_conciencia"):
                profile_id = (
                    "subtitulo_studio_instagram_"
                    + {
                        "single_line": "linea_unica",
                        "word_by_word": "palabra_por_palabra",
                        "modo_conciencia": "modo_conciencia",
                    }[style]
                )
                (subtitle_dir / f"{profile_id}.json").write_text(
                    json.dumps({
                        "component": "studio",
                        "platform": "instagram",
                        "profile_id": profile_id,
                        "display_name": profile_id,
                        "style": style,
                        "cue_policy": {"mode": "single_line"},
                        "render_style": {
                            "font": "unisans",
                            "font_size": 14,
                            "bold": False,
                            "primary_colour": "&H00FFFFFF",
                            "outline_colour": "&H80000000",
                            "back_colour": "&H00000000",
                            "border_style": 1,
                            "outline": 0,
                            "shadow": 1,
                            "alignment": 2,
                            "margin_v": 55,
                            "offset": 0.0,
                        },
                    }),
                    encoding="utf-8",
                )

            styles = SubtitleProfileResolver(root).discover_styles(
                self.profile_key,
            )

        self.assertEqual(
            ("single_line", "modo_conciencia", "word_by_word"),
            styles,
        )


class _AudioExtractionRunner:

    def __init__(self):
        self.command = ()

    def run(self, command):
        self.command = tuple(command)
        Path(command[-1]).write_bytes(b"audio")


class _WhisperSubtitleBuilder:

    def build(self, audio_path, output_path):
        output_path = Path(output_path)
        output_path.write_text(
            "1\n00:00:00,000 --> 00:00:01,200\nuno dos\n",
            encoding="utf-8",
        )
        whisper_timing_path(output_path).write_text(
            json.dumps({
                "segments": [{
                    "words": [
                        {"word": "uno", "start": 0.0, "end": 0.2},
                        {"word": "dos", "start": 0.9, "end": 1.2},
                    ],
                }],
            }),
            encoding="utf-8",
        )
        return output_path


class _CapturingSubtitlePreparation:

    def prepare(self, video_path, working_directory):
        working_directory = Path(working_directory)
        self.audio_path = working_directory / "source_audio.wav"
        self.subtitle_path = working_directory / "whisper.srt"
        self.audio_path.write_bytes(b"audio")
        self.subtitle_path.write_text(
            "1\n00:00:00,000 --> 00:00:01,200\nuno dos\n",
            encoding="utf-8",
        )
        timing = SubtitleTimingResolver().resolve(
            subtitle_path=self._write_sidecar(),
            audio_path=self.audio_path,
        )
        return SimpleNamespace(
            audio_path=self.audio_path,
            subtitle_path=self.subtitle_path,
            timing=timing,
        )

    def _write_sidecar(self):
        whisper_timing_path(self.subtitle_path).write_text(
            json.dumps({
                "segments": [{
                    "words": [
                        {"word": "uno", "start": 0.0, "end": 0.2},
                    ],
                }],
            }),
            encoding="utf-8",
        )
        return self.subtitle_path


if __name__ == "__main__":
    unittest.main()
