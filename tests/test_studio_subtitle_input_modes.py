import hashlib
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.controllers.run_controller import RunController
from app.core.start import (
    _persist_studio_render_subtitle,
    ejecutar_studio,
)
from app.modules.studio import (
    StudioInputMode,
    StudioInputPreparationService,
    StudioProfileLoader,
    StudioRenderResult,
)
from app.modules.subtitles.io.external_media_subtitles import (
    ExternalMediaSubtitlePreparationService,
)
from app.modules.subtitles.pipeline.cue_transformer import SubtitleCueTransformer
from app.modules.subtitles.policies.timing import (
    SubtitleTimingResolver,
    whisper_timing_path,
)
from app.shared.profile_identity import OperationalProfileKey, ProfileKey
from app.shared.config_manager import ConfigManager
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


def _load_studio_profile(profile_key):
    operational_key = OperationalProfileKey(
        profile_key.component,
        profile_key.platform,
        profile_key.profile_id,
    )
    return StudioProfileLoader().load(
        ProfileResolver().load_operational(operational_key),
        operational_key,
    )


class StudioSubtitleInputModesTest(unittest.TestCase):

    SOURCE_SRT = (
        "1\n"
        "00:00:01,000 --> 00:00:04,000\n"
        "Bienvenidos todos a Modo Conciencia.\n"
    )

    def setUp(self):
        self.profile_key = ProfileKey.for_component("studio", "instagram")
        self.profile = _load_studio_profile(self.profile_key)

    def _subtitle_profile(self, style):
        return SubtitleProfileResolver().load(
            SubtitleProfileKey.for_profile(self.profile_key, style)
        )

    @staticmethod
    def _design_subtitle_key():
        descriptors = SubtitleProfileResolver().discover_profiles_for_family(
            "studio", "instagram", "design",
        )
        return next(
            descriptor.key
            for descriptor in descriptors
            if descriptor.profile_id == "modo_conciencia_reels"
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

    def test_current_studio_modes_preserve_source_and_apply_declared_capabilities(self):
        source = self.SOURCE_SRT
        source_hash = hashlib.sha256(source.encode("utf-8")).digest()
        three_two_words = SubtitleCueTransformer(
            self._subtitle_profile("single_line"),
            self.profile.fps,
        ).transform(source)
        word_by_word = SubtitleCueTransformer(
            self._subtitle_profile("word_by_word"),
            self.profile.fps,
        ).transform(source)

        self.assertIn("Bienvenidos", three_two_words)
        self.assertIn("todos a", three_two_words)
        self.assertIn("Modo Conciencia.", three_two_words)
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
            derived = root / "demo" / "subtitles" / "demo_three_two_words.srt"
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

    def test_design_original_applies_declared_case_and_preserves_srt_structure(self):
        source = (
            "1\n"
            "00:00:10,000 --> 00:00:11,500\n"
            "Qué ocurre cuando dejamos de buscar fuera\n\n"
            "2\n"
            "00:00:12,000 --> 00:00:13,500\n"
            "Segundo cue humano\n"
        )
        environment = {
            "MC_PROFILE_COMPONENT": "studio",
            "MC_PROFILE_PLATFORM": "instagram",
            "MC_PROFILE_ID": "studio_instagram",
            "MC_PROFILE_FAMILY": "system",
        }
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            environment,
            clear=False,
        ):
            root = Path(directory)
            base = root / "demo" / "subtitles" / "demo.srt"
            base.parent.mkdir(parents=True)
            base.write_text(source, encoding="utf-8")
            subtitle_profile = ConfigManager().get_subtitle_profile(
                self._design_subtitle_key(), original=True,
            )

            with patch("app.core.start.SubtitleCueTransformer") as transformer:
                rendered_path = _persist_studio_render_subtitle(
                    base_subtitle_path=base,
                    output_path=root / "demo" / "video" / "demo.mp4",
                    subtitle_profile=subtitle_profile,
                    render_fps=self.profile.fps,
                    original=True,
                )

            rendered = rendered_path.read_text(encoding="utf-8")
            self.assertEqual(source, base.read_text(encoding="utf-8"))
            self.assertEqual(source.upper(), rendered)
            source = source.lower()
            rendered = rendered.lower().replace(
                source.splitlines()[2],
                source.splitlines()[2].capitalize(),
            )
            self.assertEqual(
                ["1", "2"],
                [block.splitlines()[0] for block in rendered.strip().split("\n\n")],
            )
            self.assertEqual(
                [
                    "00:00:10,000 --> 00:00:11,500",
                    "00:00:12,000 --> 00:00:13,500",
                ],
                [block.splitlines()[1] for block in rendered.strip().split("\n\n")],
            )
            self.assertEqual(2, len(rendered.strip().split("\n\n")))
            self.assertIn(
                "Qué ocurre cuando dejamos de buscar fuera",
                rendered,
            )
            self.assertIn("segundo cue humano", rendered)
            self.assertNotEqual(base, rendered_path)
            transformer.assert_not_called()

    def test_design_original_with_text_case_original_uses_the_persisted_base(self):
        source = (
            "1\n"
            "00:00:01,000 --> 00:00:02,000\n"
            "Texto humano sin cambios\n"
        )
        environment = {
            "MC_PROFILE_COMPONENT": "studio",
            "MC_PROFILE_PLATFORM": "instagram",
            "MC_PROFILE_ID": "studio_instagram",
            "MC_PROFILE_FAMILY": "system",
        }
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            environment,
            clear=False,
        ):
            root = Path(directory)
            base = root / "demo" / "subtitles" / "demo.srt"
            base.parent.mkdir(parents=True)
            base.write_text(source, encoding="utf-8")
            design_profile = ConfigManager().get_subtitle_profile(
                self._design_subtitle_key(), original=True,
            )
            subtitle_profile = replace(
                design_profile,
                cue_policy={
                    **design_profile.cue_policy,
                    "text_case": "original",
                },
            )

            with patch("app.core.start.SubtitleCueTransformer") as transformer:
                rendered_path = _persist_studio_render_subtitle(
                    base_subtitle_path=base,
                    output_path=root / "demo" / "video" / "demo.mp4",
                    subtitle_profile=subtitle_profile,
                    render_fps=self.profile.fps,
                    original=True,
                )

            self.assertEqual(base, rendered_path)
            self.assertEqual(source, rendered_path.read_text(encoding="utf-8"))
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
                profile = _load_studio_profile(profile_key)
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

    def test_menu_selects_subtitles_before_video(self):
        controller = RunController()
        order = []
        with patch.object(
            controller, "_select_studio_profile",
            side_effect=lambda *_: (
                order.append("subtitle"),
                setattr(
                    controller,
                    "_active_studio_subtitle_key",
                    self._subtitle_profile("single_line").key,
                ),
                setattr(controller, "_active_studio_subtitle_original", False),
                (self.profile_key, self.profile),
            )[-1],
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
            controller, "select_studio_music", return_value=None,
        ), patch.object(
            controller, "select_studio_intro_outro", return_value=None,
        ), patch.object(
            controller, "ask_project_name", return_value="studio",
        ), patch.object(
            controller, "ask_clear_output", return_value=False,
        ):
            options = controller._run_studio()

        self.assertEqual(["input", "subtitle", "files"], order)
        self.assertEqual("video", options["studio_input_mode"])

    def test_studio_subtitle_selector_discovers_standard_and_design_before_video(self):
        controller = RunController()
        messages = []
        controller._print = messages.append
        resolver = SubtitleProfileResolver()
        design = resolver.discover_profiles_for_family(
            "studio", "instagram", "design",
        )[0]
        standard = resolver.discover_profiles_for_family(
            "studio", "instagram", "estandar",
        )
        controller._select_from_list = Mock(
            side_effect=("instagram", "design", design),
        )

        selected, original = controller._select_studio_subtitle_profile(
            StudioInputMode.VIDEO.value,
        )

        self.assertEqual(design.key, selected)
        self.assertFalse(original)
        self.assertIn("SUBTÍTULOS", "\n".join(messages))
        self.assertIn("1. MODO CONCIENCIA", messages)
        self.assertIn("2. FORMATO ESTÁNDAR", messages)
        self.assertIn("2. Modo Conciencia | Reels", messages)
        self.assertTrue(
            {
                "Doble línea",
                "Dos palabras",
                "Tres palabras",
                "Línea única",
                "Palabra única",
            }.issubset(
                {descriptor.display_name for descriptor in standard}
            )
        )

    def test_srt_video_selector_uses_real_profiles_and_activates_original_policy(self):
        resolver = SubtitleProfileResolver()
        cases = (
            ("instagram", "design", "modo_conciencia_reels"),
            ("instagram", "estandar", "subtitulo_studio_instagram_linea_unica"),
            ("instagram", "estandar", "subtitulo_studio_instagram_palabra_por_palabra"),
            ("youtube", "estandar", "subtitulo_studio_youtube_linea_unica"),
        )
        for platform, family, profile_id in cases:
            with self.subTest(
                platform=platform,
                family=family,
                profile_id=profile_id,
            ):
                controller = RunController()
                messages = []
                controller._print = messages.append
                descriptor = next(
                    item
                    for item in resolver.discover_profiles_for_family(
                        "studio", platform, family,
                    )
                    if item.profile_id == profile_id
                )
                controller._select_from_list = Mock(
                    side_effect=(platform, family, descriptor),
                )

                selected, original = controller._select_studio_subtitle_profile(
                    StudioInputMode.SRT_VIDEO.value,
                )

                self.assertEqual(descriptor.key, selected)
                self.assertTrue(original)
                self.assertNotIn("ORIGINAL", "\n".join(messages))

    def test_studio_primado_negativo_uses_visible_label_and_keeps_technical_family(self):
        controller = RunController()
        messages = []
        controller._print = messages.append
        descriptor = SubtitleProfileResolver().discover_profiles_for_family(
            "studio", "instagram", "primado_negativo",
        )[0]
        controller._select_from_list = Mock(
            side_effect=("primado_negativo", descriptor),
        )

        selected = controller._select_studio_video_audio_srt_subtitle_profile(
            OperationalProfileKey("studio", "instagram", "studio_instagram"),
        )

        self.assertEqual("primado_negativo", selected.family)
        self.assertEqual(descriptor.key, selected)
        self.assertIn("1. MODO CONCIENCIA", messages)
        self.assertIn("2. FORMATO ESTÁNDAR", messages)
        self.assertIn("3. PRIMADO NEGATIVO", messages)

    def test_srt_video_original_standard_profiles_preserve_human_structure(self):
        source = (
            "1\n"
            "00:00:01,000 --> 00:00:02,000\n"
            "Texto humano, con puntuación.\n\n"
            "2\n"
            "00:00:03,000 --> 00:00:04,000\n"
            "Segundo cue humano.\n"
        )
        resolver = SubtitleProfileResolver()
        descriptors = resolver.discover_profiles_for_family(
            "studio", "instagram", "estandar",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "demo" / "subtitles" / "demo.srt"
            base.parent.mkdir(parents=True)
            base.write_text(source, encoding="utf-8")
            for descriptor in descriptors:
                with self.subTest(profile_id=descriptor.profile_id), patch(
                    "app.core.start.SubtitleCueTransformer"
                ) as transformer:
                    rendered_path = _persist_studio_render_subtitle(
                        base_subtitle_path=base,
                        output_path=root / "demo" / "video" / "demo.mp4",
                        subtitle_profile=resolver.load(descriptor.key),
                        render_fps=self.profile.fps,
                        original=True,
                    )

                self.assertEqual(base, rendered_path)
                self.assertEqual(source, base.read_text(encoding="utf-8"))
                self.assertEqual(
                    source,
                    rendered_path.read_text(encoding="utf-8"),
                )
                transformer.assert_not_called()

    def test_srt_video_selected_profile_is_not_taken_from_discovery_order(self):
        source = Path(
            "config/profiles/studio/instagram/estandar/subtitulos/"
            "subtitulo_studio_instagram_linea_unica.json"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subtitle_dir = root / "studio/instagram/test_family/subtitulos"
            subtitle_dir.mkdir(parents=True)
            for profile_id, display_name in (
                ("test_profile_first", "First profile"),
                ("test_profile_selected", "Selected profile"),
            ):
                payload = json.loads(source.read_text(encoding="utf-8"))
                payload.update(
                    {
                        "family": "test_family",
                        "profile_id": profile_id,
                        "display_name": display_name,
                    }
                )
                (subtitle_dir / f"{profile_id}.json").write_text(
                    json.dumps(payload), encoding="utf-8",
                )

            resolver = SubtitleProfileResolver(root)
            descriptors = resolver.discover_profiles_for_family(
                "studio", "instagram", "test_family",
            )
            selected_descriptor = next(
                descriptor
                for descriptor in descriptors
                if descriptor.profile_id == "test_profile_selected"
            )
            controller = RunController(subtitle_profile_resolver=resolver)
            operational_key = OperationalProfileKey(
                "studio", "instagram", "test_operational",
            )
            controller._select_from_list = Mock(
                side_effect=("instagram", "test_family", selected_descriptor),
            )

            with patch.object(
                controller,
                "_select_studio_operational_profile",
                return_value=(operational_key, Mock()),
            ) as operational:
                profile_key, _ = controller._select_studio_profile(
                    StudioInputMode.SRT_VIDEO.value,
                )
            selected = controller._studio_profile_options(profile_key)[
                "subtitle_profile_key"
            ]
            original = controller._active_studio_subtitle_original

        self.assertEqual(operational_key, profile_key)
        self.assertEqual(selected_descriptor.key, selected)
        self.assertNotEqual(descriptors[0].key, selected)
        self.assertTrue(original)

    def test_design_and_standard_word_by_word_profiles_are_independent(self):
        resolver = SubtitleProfileResolver()
        design = resolver.discover_profiles_for_family(
            "studio", "instagram", "design",
        )[0]
        standard = next(
            descriptor for descriptor in resolver.discover_profiles_for_family(
                "studio", "instagram", "estandar",
            )
            if descriptor.mode == "word_by_word"
        )

        self.assertNotEqual(design.key.profile_id, standard.key.profile_id)
        self.assertEqual("word_by_word", design.mode)
        self.assertEqual("word_by_word", standard.mode)
        self.assertNotEqual(design.key.family, standard.key.family)

    def test_future_family_is_discovered_from_subtitles_without_root_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subtitle_dir = root / "studio/instagram/test_family/subtitulos"
            subtitle_dir.mkdir(parents=True)
            payload = json.loads(
                Path(
                    "config/profiles/studio/instagram/estandar/subtitulos/"
                    "subtitulo_studio_instagram_linea_unica.json"
                ).read_text(encoding="utf-8")
            )
            payload.update(
                {
                    "family": "test_family",
                    "profile_id": "test_profile",
                    "display_name": "Test profile",
                }
            )
            (subtitle_dir / "test_profile.json").write_text(
                json.dumps(payload), encoding="utf-8",
            )

            resolver = SubtitleProfileResolver(root)
            families = resolver.discover_families("studio", "instagram")
            descriptors = resolver.discover_profiles_for_family(
                "studio", "instagram", "test_family",
            )
            self.assertFalse(any(subtitle_dir.parent.glob("*.json")))

        self.assertIn("test_family", families)
        self.assertEqual("test_profile", descriptors[0].profile_id)

    def test_srt_video_subtitle_choice_is_the_only_style_selection(self):
        controller = RunController()
        messages = []
        controller._print = messages.append
        descriptors = controller.subtitle_profile_resolver.discover_profiles(
            self.profile_key
        )
        for descriptor in descriptors:
            with self.subTest(profile_id=descriptor.profile_id):
                controller._select_from_list = Mock(return_value=descriptor)
                with patch.object(
                    controller,
                    "select_studio_subtitle_config",
                ) as visual_style:
                    style, original = controller.select_studio_subtitle_options(
                        self.profile_key,
                        StudioInputMode.SRT_VIDEO.value,
                    )

                self.assertEqual(descriptor.key, style)
                self.assertTrue(original)
                visual_style.assert_not_called()
                controller._select_from_list.assert_called_once_with(
                    tuple(descriptors)
                )

        self.assertIn("\nSUBT\u00cdTULOS\n", messages)
        for index, descriptor in enumerate(descriptors, start=1):
            self.assertIn(f"{index}. {descriptor.display_name}", messages)
        self.assertNotIn("ORIGINAL", "\n".join(messages))

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
        descriptors = controller.subtitle_profile_resolver.discover_profiles(
            self.profile_key
        )
        for index, descriptor in enumerate(descriptors, start=1):
            self.assertIn(f"{index}. {descriptor.display_name}", messages)
        self.assertNotIn("ORIGINAL", "\n".join(messages))

    def test_design_srt_video_offers_only_its_real_profile(self):
        profile_key = ProfileKey.for_component(
            "studio",
            "instagram",
            family="design",
            profile_id="studio_instagram_design_modo_conciencia_reels",
        )
        controller = RunController()
        messages = []
        controller._print = messages.append
        descriptors = controller.subtitle_profile_resolver.discover_profiles(
            profile_key
        )
        descriptor = next(
            item
            for item in descriptors
            if item.profile_id == "modo_conciencia_reels"
        )
        controller._select_from_list = Mock(return_value=descriptor)
        selected, original = controller.select_studio_subtitle_options(
            profile_key,
            StudioInputMode.SRT_VIDEO.value,
        )

        self.assertEqual(descriptor.key, selected)
        self.assertTrue(original)
        controller._select_from_list.assert_called_once_with(descriptors)
        self.assertIn("\nSUBTÍTULOS\n", messages)
        self.assertIn("1. Modo Conciencia | Podcast", messages)
        self.assertIn("2. Modo Conciencia | Reels", messages)
        self.assertNotIn("ORIGINAL", "\n".join(messages))

    def test_design_video_audio_srt_uses_its_autonomous_subtitle_profile(self):
        environment = {
            "MC_PROFILE_COMPONENT": "studio",
            "MC_PROFILE_PLATFORM": "instagram",
            "MC_PROFILE_ID": "studio_instagram",
            "MC_PROFILE_FAMILY": "system",
        }
        with patch.dict(os.environ, environment, clear=False):
            subtitle_profile = ConfigManager().get_subtitle_profile(
                self._design_subtitle_key(),
            )

        self.assertEqual("word_by_word", subtitle_profile.cue_policy["mode"])
        self.assertEqual("oswald", subtitle_profile.render_style["font"])
        self.assertEqual(22, subtitle_profile.render_style["font_size"])
        self.assertTrue(subtitle_profile.render_style["bold"])

    def test_discovery_accepts_a_future_profile_with_an_existing_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subtitle_dir = root / "studio" / "instagram" / "estandar" / "subtitulos"
            subtitle_dir.mkdir(parents=True)
            for profile_suffix, mode in (
                ("linea_unica", "single_line"),
                ("palabra_por_palabra", "word_by_word"),
                ("modo_conciencia", "word_by_word"),
            ):
                profile_id = (
                    "subtitulo_studio_instagram_"
                    + profile_suffix
                )
                (subtitle_dir / f"{profile_id}.json").write_text(
                    json.dumps({
                        "component": "studio",
                        "platform": "instagram",
                        "family": "estandar",
                        "profile_id": profile_id,
                        "display_name": profile_id,
                        "cue_policy": {"mode": mode},
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
            ("single_line", "word_by_word", "word_by_word"),
            tuple(
                style.value if hasattr(style, "value") else style
                for style in styles
            ),
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
