import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.controllers.interaction.contracts import (
    StudioOperationalSelection,
    StudioProfileSelection,
    StudioSubtitleSelection,
)
from app.controllers.run_controller import RunController
from app.modules.studio.execution_coordinator import StudioExecutionCoordinator
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
from app.shared.profile_identity import OperationalProfileKey
from app.shared.config_manager import ConfigManager
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


STUDIO_PROFILE_IDS = {
    "vertical": "studio_vertical",
    "horizontal": "studio_horizontal",
}

STUDIO_STANDARD_SUBTITLE_PROFILE_IDS = {
    ("vertical", "single_line"): "subtitulo_studio_vertical_linea_unica",
    ("vertical", "word_by_word"): (
        "subtitulo_studio_vertical_palabra_por_palabra"
    ),
    ("horizontal", "single_line"): "subtitulo_studio_horizontal_linea_unica",
    ("horizontal", "word_by_word"): "subtitulo_studio_horizontal_palabra_por_palabra",
}


def _load_studio_profile(profile_key):
    operational_key = OperationalProfileKey(
        profile_key.component,
        profile_key.format,
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
        # Solo para los tests del menu heredado (se retiran en L5b/L5c).
        self.operational_key = OperationalProfileKey(
            "studio", "vertical", "studio_vertical"
        )
        self.profile = _load_studio_profile(self.operational_key)

    def _subtitle_profile(self, style):
        return SubtitleProfileResolver().load(
            SubtitleProfileKey(
                "studio",
                "vertical",
                STUDIO_STANDARD_SUBTITLE_PROFILE_IDS[("vertical", style)],
                "estandar",
            )
        )

    @staticmethod
    def _design_subtitle_key():
        descriptors = SubtitleProfileResolver().discover_profiles_for_family(
            "studio", "vertical", "design",
        )
        return next(
            descriptor.key
            for descriptor in descriptors
            if descriptor.profile_id == "modo_conciencia_palabra_unica"
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
                profile_key=self.operational_key,
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
                "app.modules.studio.execution_coordinator.time.perf_counter",
                side_effect=(10.0, 12.5),
            ), patch(
                "app.modules.studio.execution_coordinator.ProgressLogger"
            ) as progress_logger:
                result = StudioExecutionCoordinator().run_standard(
                    subtitle_profile_key=preparation.subtitle_profile.key,
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
            self.assertEqual("whisper", kwargs["subtitle_timing"].source)
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
                profile_key=self.operational_key,
                profile=self.profile,
                subtitle_profile=self._subtitle_profile("single_line"),
            )
            renderer = Mock()
            renderer.render.return_value = "rendered"
            output_path = root / "demo" / "video" / "demo.mp4"
            resolver = Mock(resolve=Mock(return_value=output_path))

            result = StudioExecutionCoordinator().run_standard(
                subtitle_profile_key=preparation.subtitle_profile.key,
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
                profile_key=self.operational_key,
                profile=self.profile,
                subtitle_profile=self._subtitle_profile("word_by_word"),
                subtitle_original=True,
            )
            renderer = Mock()
            renderer.render.return_value = "rendered"
            output_path = root / "demo" / "video" / "demo.mp4"

            with patch(
                "app.modules.studio.execution_coordinator.SubtitleCueTransformer"
            ) as transformer:
                StudioExecutionCoordinator().run_standard(
                    subtitle_profile_key=preparation.subtitle_profile.key,
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
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "demo" / "subtitles" / "demo.srt"
            base.parent.mkdir(parents=True)
            base.write_text(source, encoding="utf-8")
            subtitle_profile = ConfigManager().get_subtitle_profile_by_key(
                self._design_subtitle_key(),
            )

            with patch(
                "app.modules.studio.execution_coordinator.SubtitleCueTransformer"
            ) as transformer:
                rendered_path = StudioExecutionCoordinator.persist_render_subtitle(
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
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "demo" / "subtitles" / "demo.srt"
            base.parent.mkdir(parents=True)
            base.write_text(source, encoding="utf-8")
            design_profile = ConfigManager().get_subtitle_profile_by_key(
                self._design_subtitle_key(),
            )
            subtitle_profile = replace(
                design_profile,
                cue_policy={
                    **design_profile.cue_policy,
                    "text_case": "original",
                },
            )

            with patch(
                "app.modules.studio.execution_coordinator.SubtitleCueTransformer"
            ) as transformer:
                rendered_path = StudioExecutionCoordinator.persist_render_subtitle(
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
            "ORIGINAL solo está disponible para STUDIO SRT \\+ VIDEO",
        ):
            StudioExecutionCoordinator().run_standard(
                subtitle_profile_key=self._subtitle_profile("single_line").key,
                input_mode="video",
                subtitle_original=True,
                external_subtitle_preparation_service=subtitle_service,
                render_service=renderer,
            )

        subtitle_service.prepare.assert_not_called()
        renderer.render.assert_not_called()

    def test_original_preserves_srt_base_for_both_studio_formats(self):
        source = "1\n00:00:00,000 --> 00:00:01,000\nMATEO 13\n"
        for profile_format in ("horizontal", "vertical"):
            with self.subTest(profile_format=profile_format), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                profile_key = OperationalProfileKey(
                    "studio", profile_format, STUDIO_PROFILE_IDS[profile_format]
                )
                profile = _load_studio_profile(profile_key)
                subtitle_profile = SubtitleProfileResolver().load(
                    SubtitleProfileKey(
                        "studio",
                        profile_format,
                        STUDIO_STANDARD_SUBTITLE_PROFILE_IDS[
                            (profile_format, "word_by_word")
                        ],
                        "estandar",
                    )
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

                with patch(
                    "app.modules.studio.execution_coordinator.SubtitleCueTransformer"
                ) as transformer:
                    StudioExecutionCoordinator().run_standard(
                        subtitle_profile_key=subtitle_profile.key,
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
            controller, "_select_studio_profile_selection",
            side_effect=lambda *_: (
                order.append("subtitle"),
                StudioProfileSelection(
                    operational=StudioOperationalSelection(
                        self.operational_key,
                        self.profile,
                    ),
                    subtitle=StudioSubtitleSelection(
                        self._subtitle_profile("single_line").key,
                        False,
                    ),
                ),
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
            request = controller._run_studio()

        self.assertEqual(["input", "subtitle", "files"], order)
        self.assertIs(StudioInputMode.VIDEO, request.route.input_mode)

    def test_studio_subtitle_selector_discovers_standard_and_design_before_video(self):
        controller = RunController()
        messages = []
        controller._print = messages.append
        resolver = SubtitleProfileResolver()
        design = next(
            item
            for item in resolver.discover_profiles_for_family(
                "studio", "vertical", "design",
            )
            if item.display_name == "Modo Conciencia | Podcast"
        )
        standard = resolver.discover_profiles_for_family(
            "studio", "vertical", "estandar",
        )
        controller._select_from_list = Mock(
            side_effect=("vertical", "design", design),
        )

        selected, original = controller._select_studio_subtitle_profile(
            StudioInputMode.VIDEO.value,
        )

        self.assertEqual(design.key, selected)
        self.assertFalse(original)
        self.assertIn("SUBTÍTULOS", "\n".join(messages))
        self.assertIn("1. MODO CONCIENCIA", messages)
        self.assertIn("2. ESTILO ESTÁNDAR", messages)
        self.assertIn("1. Modo Conciencia | Palabra única", messages)
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
            ("vertical", "design", "modo_conciencia_palabra_unica"),
            ("vertical", "estandar", "subtitulo_studio_vertical_linea_unica"),
            ("vertical", "estandar", "subtitulo_studio_vertical_palabra_por_palabra"),
            ("horizontal", "estandar", "subtitulo_studio_horizontal_linea_unica"),
        )
        for profile_format, family, profile_id in cases:
            with self.subTest(
                profile_format=profile_format,
                family=family,
                profile_id=profile_id,
            ):
                controller = RunController()
                messages = []
                controller._print = messages.append
                descriptor = next(
                    item
                    for item in resolver.discover_profiles_for_family(
                        "studio", profile_format, family,
                    )
                    if item.profile_id == profile_id
                )
                controller._select_from_list = Mock(
                    side_effect=(profile_format, family, descriptor),
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
        descriptor = next(
            item
            for item in SubtitleProfileResolver().discover_profiles_for_family(
                "studio", "vertical", "primado_negativo",
            )
            if item.display_name == "Primado Negativo | Marco"
        )
        controller._select_from_list = Mock(
            side_effect=("primado_negativo", descriptor),
        )

        selected = controller._select_studio_video_audio_srt_subtitle_profile(
            OperationalProfileKey("studio", "vertical", "studio_vertical"),
        )

        self.assertEqual("primado_negativo", selected.family)
        self.assertEqual(descriptor.key, selected)
        self.assertIn("1. MODO CONCIENCIA", messages)
        self.assertIn("2. ESTILO ESTÁNDAR", messages)
        self.assertIn("3. MODO MINIMALISTA", messages)
        self.assertIn("4. ESTILO KARAOKE", messages)
        self.assertIn("5. PRIMADO NEGATIVO", messages)

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
            "studio", "vertical", "estandar",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "demo" / "subtitles" / "demo.srt"
            base.parent.mkdir(parents=True)
            base.write_text(source, encoding="utf-8")
            for descriptor in descriptors:
                with self.subTest(profile_id=descriptor.profile_id), patch(
                    "app.modules.studio.execution_coordinator.SubtitleCueTransformer"
                ) as transformer:
                    rendered_path = StudioExecutionCoordinator.persist_render_subtitle(
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
            "config/profiles/studio/vertical/estandar/subtitulos/"
            "subtitulo_studio_vertical_linea_unica.json"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subtitle_dir = root / "studio/vertical/test_family/subtitulos"
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
                "studio", "vertical", "test_family",
            )
            selected_descriptor = next(
                descriptor
                for descriptor in descriptors
                if descriptor.profile_id == "test_profile_selected"
            )
            controller = RunController(subtitle_profile_resolver=resolver)
            operational_key = OperationalProfileKey(
                "studio", "vertical", "test_operational",
            )
            controller._select_from_list = Mock(
                side_effect=("vertical", "test_family", selected_descriptor),
            )

            with patch.object(
                controller,
                "_select_studio_operational_profile",
                return_value=(operational_key, Mock()),
            ) as operational:
                selection = controller._select_studio_profile_selection(
                    StudioInputMode.SRT_VIDEO.value,
                )
            operational.assert_called_once()
            profile_key = selection.operational.operational_key
            selected = selection.subtitle.subtitle_key
            original = selection.subtitle.subtitle_original

        self.assertEqual(operational_key, profile_key)
        self.assertEqual(selected_descriptor.key, selected)
        self.assertNotEqual(descriptors[0].key, selected)
        self.assertTrue(original)

    def test_design_and_standard_profiles_are_independent_by_identity(self):
        resolver = SubtitleProfileResolver()
        design = resolver.discover_profiles_for_family(
            "studio", "vertical", "design",
        )
        standard = resolver.discover_profiles_for_family(
            "studio", "vertical", "estandar",
        )

        self.assertTrue(design)
        self.assertTrue(standard)
        self.assertTrue(
            {descriptor.key for descriptor in design}.isdisjoint(
                {descriptor.key for descriptor in standard},
            )
        )
        for descriptor in (*design, *standard):
            with self.subTest(
                family=descriptor.key.family,
                profile_id=descriptor.key.profile_id,
            ):
                resolved = resolver.load(descriptor.key)
                self.assertEqual(descriptor.key, resolved.key)
                self.assertEqual(
                    descriptor.mode,
                    resolved.cue_policy["mode"],
                )

    def test_future_family_is_discovered_from_subtitles_without_root_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subtitle_dir = root / "studio/vertical/test_family/subtitulos"
            subtitle_dir.mkdir(parents=True)
            payload = json.loads(
                Path(
                    "config/profiles/studio/vertical/estandar/subtitulos/"
                    "subtitulo_studio_vertical_linea_unica.json"
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
            families = resolver.discover_families("studio", "vertical")
            descriptors = resolver.discover_profiles_for_family(
                "studio", "vertical", "test_family",
            )
            self.assertFalse(any(subtitle_dir.parent.glob("*.json")))

        self.assertIn("test_family", families)
        self.assertEqual("test_profile", descriptors[0].profile_id)

    def test_design_video_audio_srt_uses_its_autonomous_subtitle_profile(self):
        subtitle_profile = ConfigManager().get_subtitle_profile_by_key(
            self._design_subtitle_key(),
        )

        self.assertEqual("word_by_word", subtitle_profile.cue_policy["mode"])
        self.assertEqual("oswald", subtitle_profile.render_style["font"])
        self.assertEqual(22, subtitle_profile.render_style["font_size"])
        self.assertTrue(subtitle_profile.render_style["bold"])

    def test_discovery_accepts_a_future_profile_with_an_existing_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subtitle_dir = root / "studio" / "vertical" / "estandar" / "subtitulos"
            subtitle_dir.mkdir(parents=True)
            for profile_suffix, mode in (
                ("linea_unica", "single_line"),
                ("palabra_por_palabra", "word_by_word"),
                ("modo_conciencia", "word_by_word"),
            ):
                profile_id = (
                    "subtitulo_studio_vertical_"
                    + profile_suffix
                )
                (subtitle_dir / f"{profile_id}.json").write_text(
                    json.dumps({
                        "component": "studio",
                        "format": "vertical",
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

            descriptors = SubtitleProfileResolver(root).discover_profiles_for_family(
                "studio", "vertical", "estandar",
            )

        self.assertEqual(
            ("single_line", "word_by_word", "word_by_word"),
            tuple(descriptor.mode for descriptor in descriptors),
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
