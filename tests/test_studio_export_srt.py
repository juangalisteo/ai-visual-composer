import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import main
from app.cli import studio_summary
from app.controllers.interaction.contracts import (
    StudioOperationalSelection,
    StudioProfileSelection,
    StudioSubtitleSelection,
)
from app.controllers.run_controller import RunController
from app.core.execution_request import (
    ApplicationExecutionRequest,
    StudioExecutionRequest,
)
from app.modules.studio.execution_coordinator import StudioExecutionCoordinator
from app.managers.project_manager import ProjectManager
from app.modules.studio import (
    StudioProfileLoader,
    StudioInputMode,
    StudioSubtitleExportInputError,
    StudioSubtitleExportInputService,
    StudioSubtitleExportMode,
    StudioSubtitleExportPlan,
    StudioSubtitleExportResult,
    StudioSubtitleExportService,
)
from app.modules.subtitles.io.external_media_subtitles import (
    ExternalMediaSubtitlePreparationService,
)
from app.modules.subtitles.policies.timing import whisper_timing_path
from app.shared.operational_error import OperationalError
from app.shared.profile_identity import OperationalProfileKey, ProfileComponent
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


SRT_CONTENT = (
    "1\n"
    "00:00:00,000 --> 00:00:02,000\n"
    "Hola mundo sereno.\n\n"
    "2\n"
    "00:00:03,000 --> 00:00:05,000\n"
    "La conciencia observa.\n"
)


STUDIO_PROFILE_IDS = {
    "vertical": "studio_vertical",
    "horizontal": "studio_horizontal",
}


def _studio_selection(profile_key, subtitle_key, studio_profile=None):
    return StudioProfileSelection(
        operational=StudioOperationalSelection(
            profile_key,
            studio_profile or Mock(),
        ),
        subtitle=StudioSubtitleSelection(subtitle_key, False),
    )


class _WhisperBuilder:

    def __init__(self):
        self.calls = []

    def build(self, audio_path, output_path):
        self.calls.append((Path(audio_path), Path(output_path)))
        output_path = Path(output_path)
        output_path.write_text(SRT_CONTENT, encoding="utf-8")
        whisper_timing_path(output_path).write_text(
            json.dumps({
                "segments": [{
                    "start": 0.0,
                    "end": 1.0,
                    "words": [
                        {"word": "Hola", "start": 0.0, "end": 0.4},
                        {"word": "mundo", "start": 0.5, "end": 1.0},
                    ],
                }],
            }),
            encoding="utf-8",
        )
        return output_path


class _ExtractionRunner:

    def __init__(self):
        self.calls = []

    def run(self, command):
        self.calls.append(tuple(command))
        Path(command[-1]).write_bytes(b"audio")


class StudioSubtitleExportInputTest(unittest.TestCase):

    def test_transcribir_discovers_mp4_and_mp3_in_deterministic_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "studio"
            source = root / "exportar_srt" / "transcribir"
            source.mkdir(parents=True)
            (source / "zeta.mp3").write_bytes(b"mp3")
            (source / "alfa.mp4").write_bytes(b"mp4")
            (source / "captions.srt").write_text(
                SRT_CONTENT,
                encoding="utf-8",
            )
            (source / "ignored.wav").write_bytes(b"wav")
            service = StudioSubtitleExportInputService(root)

            candidates = service.discover("transcribir")

            self.assertEqual(
                ("alfa.mp4", "zeta.mp3"),
                tuple(path.name for path in candidates.sources),
            )
            self.assertEqual(StudioSubtitleExportMode.TRANSCRIBIR, candidates.mode)

    def test_convertir_discovers_only_valid_srt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "studio"
            source = root / "exportar_srt" / "convertir"
            source.mkdir(parents=True)
            (source / "fuente.srt").write_text(SRT_CONTENT, encoding="utf-8")
            (source / "video.mp4").write_bytes(b"mp4")
            (source / "audio.mp3").write_bytes(b"mp3")
            service = StudioSubtitleExportInputService(root)

            candidates = service.discover(StudioSubtitleExportMode.CONVERTIR)
            plan = service.prepare("convertir")

            self.assertEqual(("fuente.srt",), tuple(
                path.name for path in candidates.sources
            ))
            self.assertEqual(source / "fuente.srt", plan.source_path)

    def test_export_discovery_fails_clearly_without_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "studio"
            source = root / "exportar_srt"
            (source / "transcribir").mkdir(parents=True)
            (source / "convertir").mkdir(parents=True)
            service = StudioSubtitleExportInputService(root)

            with self.assertRaisesRegex(
                StudioSubtitleExportInputError,
                "MP4 o MP3",
            ):
                service.discover("transcribir")
            with self.assertRaisesRegex(StudioSubtitleExportInputError, "SRT"):
                service.discover("convertir")

    def test_multiple_candidates_require_explicit_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "studio"
            source = root / "exportar_srt" / "transcribir"
            source.mkdir(parents=True)
            (source / "uno.mp4").write_bytes(b"one")
            (source / "dos.mp3").write_bytes(b"two")
            service = StudioSubtitleExportInputService(root)

            with self.assertRaisesRegex(ValueError, "ambigua"):
                service.prepare("transcribir")
            selected = service.prepare("transcribir", source / "dos.mp3")
            self.assertEqual(source / "dos.mp3", selected.source_path)

    def test_export_discovery_never_falls_back_to_flat_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "studio"
            export_root = root / "exportar_srt"
            transcribir = export_root / "transcribir"
            convertir = export_root / "convertir"
            transcribir.mkdir(parents=True)
            convertir.mkdir()
            (export_root / "legacy.mp4").write_bytes(b"mp4")
            (export_root / "legacy.srt").write_text(
                SRT_CONTENT,
                encoding="utf-8",
            )
            service = StudioSubtitleExportInputService(root)

            with self.assertRaisesRegex(
                StudioSubtitleExportInputError,
                "MP4 o MP3",
            ):
                service.discover("transcribir")
            with self.assertRaisesRegex(StudioSubtitleExportInputError, "SRT"):
                service.discover("convertir")


class ExternalMediaSubtitlePreparationTest(unittest.TestCase):

    def test_mp4_extracts_audio_before_one_whisper_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            source.write_bytes(b"source-mp4")
            runner = _ExtractionRunner()
            builder = _WhisperBuilder()
            service = ExternalMediaSubtitlePreparationService(
                runner=runner,
                subtitle_builder=builder,
            )

            prepared = service.prepare(source, root / "work")

            self.assertEqual(1, len(runner.calls))
            self.assertIn("-map", runner.calls[0])
            self.assertEqual(1, len(builder.calls))
            self.assertEqual(root / "work" / "source_audio.wav", prepared.audio_path)
            self.assertEqual(b"source-mp4", source.read_bytes())

    def test_mp3_reaches_whisper_directly_without_audio_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp3"
            source.write_bytes(b"source-mp3")
            runner = _ExtractionRunner()
            builder = _WhisperBuilder()
            service = ExternalMediaSubtitlePreparationService(
                runner=runner,
                subtitle_builder=builder,
            )

            prepared = service.prepare(media_path=source, working_directory=root / "work")

            self.assertEqual([], runner.calls)
            self.assertEqual([(source, root / "work" / "whisper.srt")], builder.calls)
            self.assertTrue(prepared.timing.is_usable())
            self.assertEqual(b"source-mp3", source.read_bytes())

    def test_mp4_without_readable_audio_is_an_input_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            source.write_bytes(b"no es video")
            runner = Mock()
            runner.run.side_effect = subprocess.CalledProcessError(
                1,
                ["ffmpeg"],
                stderr="Invalid data found when processing input",
            )
            builder = _WhisperBuilder()
            service = ExternalMediaSubtitlePreparationService(
                runner=runner,
                subtitle_builder=builder,
            )

            with self.assertRaises(OperationalError) as raised:
                service.prepare(media_path=source, working_directory=root / "work")

            context = raised.exception.context
            self.assertEqual("FFMPEG", context.family)
            self.assertEqual(
                f"No se pudo sacar el audio de {source} para transcribirlo.",
                context.user_message,
            )
            self.assertEqual(
                "Comprueba que el archivo sea un vídeo válido y que tenga sonido.",
                context.recommended_action,
            )
            self.assertEqual(
                "Invalid data found when processing input",
                context.technical_metadata["stderr_summary"],
            )
            self.assertEqual([], builder.calls)


class StudioSubtitleExportServiceTest(unittest.TestCase):

    def setUp(self):
        self.operational_key = OperationalProfileKey(
            "studio", "vertical", "studio_vertical"
        )
        self.profile = StudioProfileLoader().load(
            ProfileResolver().load_operational(self.operational_key),
            self.operational_key,
        )

    def _subtitle_profile(self, style):
        if style == "three_two_words":
            return SubtitleProfileResolver().load(
                SubtitleProfileKey(
                    "studio", "vertical",
                    "subtitulo_studio_vertical_linea_unica", "estandar",
                )
            )
        profile_id = {
            "single_line": "subtitulo_studio_vertical_linea_unica",
            "word_by_word": "subtitulo_studio_vertical_palabra_por_palabra",
        }[style]
        return SubtitleProfileResolver().load(
            SubtitleProfileKey("studio", "vertical", profile_id, "estandar")
        )

    def _project(self, root, name="exportacion"):
        project = ProjectManager(project_name=name)
        project.base_path = root / "output" / project.project_name
        project.setup()
        return project

    def test_transcribir_persists_canonical_srt_once_without_render(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp3"
            source.write_bytes(b"source")
            project = self._project(root)
            prepared = Mock()
            prepared.subtitle_path = root / "whisper.srt"
            prepared.subtitle_path.write_text(SRT_CONTENT, encoding="utf-8")
            preparer = Mock()
            preparer.prepare.return_value = prepared
            service = StudioSubtitleExportService(preparer)

            result = service.export(
                StudioSubtitleExportPlan(
                    StudioSubtitleExportMode.TRANSCRIBIR,
                    source,
                ),
                project,
            )

            self.assertEqual(
                project.subtitles_dir() / "exportacion.srt",
                result.output_path,
            )
            self.assertEqual(SRT_CONTENT, result.output_path.read_text(encoding="utf-8"))
            preparer.prepare.assert_called_once()
            self.assertEqual(b"source", source.read_bytes())

    def test_convertir_reuses_existing_models_without_whisper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "human.srt"
            source.write_text(SRT_CONTENT, encoding="utf-8")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            project = self._project(root, "convertido")
            preparer = Mock()
            service = StudioSubtitleExportService(preparer)

            outputs = []
            for style in ("three_two_words", "word_by_word"):
                result = service.export(
                    StudioSubtitleExportPlan(
                        StudioSubtitleExportMode.CONVERTIR,
                        source,
                    ),
                    project,
                    profile=self.profile,
                    subtitle_profile=self._subtitle_profile(style),
                )
                outputs.append(result.output_path)
                self._assert_within_source_intervals(
                    result.output_path.read_text(encoding="utf-8"),
                    SRT_CONTENT,
                )

            self.assertEqual([], preparer.prepare.call_args_list)
            self.assertEqual(source_hash, hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(
                ("convertido_three_two_words.srt", "convertido_word_by_word.srt"),
                tuple(path.name for path in outputs),
            )

    def _assert_within_source_intervals(self, content, source):
        source_ranges = self._ranges(source)
        for start, end in self._ranges(content):
            self.assertTrue(
                any(left <= start < end <= right for left, right in source_ranges)
            )

    @staticmethod
    def _ranges(content):
        ranges = []
        for block in content.strip().split("\n\n"):
            _, timestamp, *_ = block.splitlines()
            start, end = timestamp.split(" --> ")
            ranges.append((
                StudioSubtitleExportServiceTest._milliseconds(start),
                StudioSubtitleExportServiceTest._milliseconds(end),
            ))
        return ranges

    @staticmethod
    def _milliseconds(value):
        hours, minutes, tail = value.split(":")
        seconds, milliseconds = tail.split(",")
        return (
            int(hours) * 3_600_000
            + int(minutes) * 60_000
            + int(seconds) * 1_000
            + int(milliseconds)
        )


class StudioSubtitleExportControllerTest(unittest.TestCase):

    def test_controller_lists_studio_inputs_in_the_expected_order(self):
        controller = RunController()
        messages = []
        controller._print = messages.append
        controller._select_from_list = Mock(
            return_value=StudioInputMode.VIDEO.value
        )

        selected = controller.select_studio_input_mode()

        self.assertEqual(StudioInputMode.VIDEO.value, selected)
        self.assertEqual(
            [
                "\nENTRADA\n",
                "1. SOLO VIDEO",
                "2. SRT + VIDEO",
                "3. INTRO / OUTRO",
                "4. MONTAJE VÍDEOS",
                "5. VIDEO + AUDIO | SRT",
                "6. EXPORTAR SRT ➜  VIDEO",
            ],
            messages,
        )

    def test_controller_maps_each_studio_input_position_to_its_mode(self):
        modes = (
            StudioInputMode.VIDEO.value,
            StudioInputMode.SRT_VIDEO.value,
            StudioInputMode.INTRO_OUTRO.value,
            StudioInputMode.MONTAJE_VIDEOS.value,
            StudioInputMode.VIDEO_AUDIO_SRT.value,
            StudioInputMode.EXPORTAR_SRT.value,
        )
        for selected_mode in modes:
            with self.subTest(selected_mode=selected_mode):
                controller = RunController()
                controller._print = Mock()
                controller._select_from_list = Mock(
                    return_value=selected_mode
                )

                selected = controller.select_studio_input_mode()

                self.assertEqual(selected_mode, selected)
                controller._select_from_list.assert_called_once_with(modes)

    def test_controller_convertir_uses_the_selected_key_without_second_selector(self):
        plan = StudioSubtitleExportPlan(
            StudioSubtitleExportMode.CONVERTIR,
            Path("input/studio/exportar_srt/source.srt"),
        )
        controller = RunController()
        profile_key = OperationalProfileKey(
            "studio", "vertical", "studio_vertical"
        )
        subtitle_key = SubtitleProfileResolver().discover_profiles_for_family(
            "studio", "vertical", "estandar",
        )[0].key
        with patch.object(controller, "_select_studio_profile_selection", return_value=_studio_selection(
            profile_key,
            subtitle_key,
        )), patch.object(controller, "select_studio_input_mode", return_value="exportar_srt"), patch.object(
            controller, "select_studio_subtitle_export_mode",
            return_value=StudioSubtitleExportMode.CONVERTIR,
        ), patch.object(
            controller, "select_studio_subtitle_export_plan", return_value=plan,
        ), patch.object(controller, "select_studio_music") as music, patch.object(
            controller, "select_studio_intro_outro",
        ) as intro_outro, patch.object(controller, "ask_project_name", return_value="demo"), patch.object(
            controller, "ask_clear_output", return_value=False,
        ):
            request = controller._run_studio()

        self.assertIs(StudioInputMode.EXPORTAR_SRT, request.route.input_mode)
        self.assertNotIn("subtitle_config", vars(request))
        self.assertNotIn("subtitle_config", vars(request.route))
        self.assertEqual(subtitle_key, request.subtitle_profile_key)
        self.assertIs(plan, request.route.plan)
        self.assertIs(
            ProfileComponent.STUDIO,
            request.operational_profile_key.component,
        )
        music.assert_not_called()
        intro_outro.assert_not_called()

    def test_controller_convertir_uses_mode_from_each_real_selected_profile(self):
        plan = StudioSubtitleExportPlan(
            StudioSubtitleExportMode.CONVERTIR,
            Path("input/studio/exportar_srt/source.srt"),
        )
        resolver = SubtitleProfileResolver()
        cases = (
            ("vertical", "design", "word_by_word"),
            ("vertical", "estandar", "three_two_words"),
            ("vertical", "estandar", "word_by_word"),
            ("horizontal", "estandar", "single_line"),
            ("horizontal", "estandar", "word_by_word"),
        )
        for profile_format, family, expected_mode in cases:
            with self.subTest(profile_format=profile_format, family=family, mode=expected_mode):
                descriptor = next(
                    item
                    for item in resolver.discover_profiles_for_family(
                        "studio", profile_format, family,
                    )
                    if resolver.load(item.key).cue_policy["mode"] == expected_mode
                )
                controller = RunController()
                profile_key = OperationalProfileKey(
                    "studio", profile_format, STUDIO_PROFILE_IDS[profile_format]
                )
                with patch.object(
                    controller,
                    "_select_studio_profile_selection",
                    return_value=_studio_selection(profile_key, descriptor.key),
                ), patch.object(
                    controller,
                    "select_studio_input_mode",
                    return_value="exportar_srt",
                ), patch.object(
                    controller,
                    "select_studio_subtitle_export_mode",
                    return_value=StudioSubtitleExportMode.CONVERTIR,
                ), patch.object(
                    controller,
                    "select_studio_subtitle_export_plan",
                    return_value=plan,
                ), patch.object(
                    controller,
                    "ask_project_name",
                    return_value="demo",
                ), patch.object(
                    controller,
                    "ask_clear_output",
                    return_value=False,
                ):
                    request = controller._run_studio()

                self.assertEqual(descriptor.key, request.subtitle_profile_key)
                self.assertNotIn("subtitle_config", vars(request))
                self.assertNotIn("subtitle_config", vars(request.route))
                self.assertEqual(
                    expected_mode,
                    resolver.load(request.subtitle_profile_key).cue_policy["mode"],
                )

    def test_controller_convertir_transports_a_dynamic_subtitle_profile_key(self):
        plan = StudioSubtitleExportPlan(
            StudioSubtitleExportMode.CONVERTIR,
            Path("input/studio/exportar_srt/source.srt"),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = Path(
                "config/profiles/studio/vertical/estandar/subtitulos/"
                "subtitulo_studio_vertical_linea_unica.json"
            )
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload.update({
                "component": "studio",
                "format": "test_format",
                "family": "test_family",
                "profile_id": "test_profile",
                "display_name": "Test profile",
            })
            path = (
                root / "studio" / "test_format" / "test_family"
                / "subtitulos" / "test_profile.json"
            )
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(payload), encoding="utf-8")
            resolver = SubtitleProfileResolver(root)
            descriptor = resolver.discover_profiles_for_family(
                "studio", "test_format", "test_family",
            )[0]
            mode = resolver.load(descriptor.key).cue_policy["mode"]
            controller = RunController(subtitle_profile_resolver=resolver)
            profile_key = OperationalProfileKey(
                "studio", "test_format", "test_operational",
            )
            with patch.object(
                controller,
                "_select_studio_profile_selection",
                return_value=_studio_selection(profile_key, descriptor.key),
            ), patch.object(
                controller,
                "select_studio_input_mode",
                return_value="exportar_srt",
            ), patch.object(
                controller,
                "select_studio_subtitle_export_mode",
                return_value=StudioSubtitleExportMode.CONVERTIR,
            ), patch.object(
                controller,
                "select_studio_subtitle_export_plan",
                return_value=plan,
            ), patch.object(
                controller,
                "ask_project_name",
                return_value="demo",
            ), patch.object(
                controller,
                "ask_clear_output",
                return_value=False,
            ):
                request = controller._run_studio()

        self.assertEqual(descriptor.key, request.subtitle_profile_key)
        self.assertEqual("three_two_words", mode)

    def test_controller_transcribir_never_selects_a_profile(self):
        plan = StudioSubtitleExportPlan(
            StudioSubtitleExportMode.TRANSCRIBIR,
            Path("input/studio/exportar_srt/source.mp3"),
        )
        controller = RunController()
        with patch.object(
            controller,
            "select_studio_input_mode",
            return_value=StudioInputMode.EXPORTAR_SRT.value,
        ), patch.object(
            controller,
            "select_studio_subtitle_export_mode",
            return_value=StudioSubtitleExportMode.TRANSCRIBIR,
        ), patch.object(
            controller,
            "select_studio_subtitle_export_plan",
            return_value=plan,
        ), patch.object(controller, "select_profile") as profile, patch.object(
            controller,
            "ask_project_name",
            return_value="demo",
        ), patch.object(
            controller,
            "ask_clear_output",
            return_value=False,
        ):
            request = controller._run_studio()

        profile.assert_not_called()
        self.assertIsNone(request.operational_profile_key)
        self.assertIs(plan, request.route.plan)


class StudioSubtitleExportStartTest(unittest.TestCase):

    def test_start_transcribe_does_not_require_a_profile_or_subtitle_style(self):
        service = Mock()
        expected = StudioSubtitleExportResult(
            StudioSubtitleExportMode.TRANSCRIBIR,
            Path("source.mp3"),
            Path("output/demo/subtitles/demo.srt"),
            None,
            1.0,
        )
        service.export.return_value = expected
        plan = StudioSubtitleExportPlan(
            StudioSubtitleExportMode.TRANSCRIBIR,
            Path("source.mp3"),
        )

        with tempfile.TemporaryDirectory() as directory:
            project = ProjectManager()
            project.base_path = Path(directory) / "output" / "demo"
            result = StudioExecutionCoordinator().run_subtitle_export(
                plan,
                project=project,
                export_service=service,
            )

        self.assertIs(expected, result)
        self.assertNotIn("profile", service.export.call_args.kwargs)
        self.assertNotIn("subtitle_profile", service.export.call_args.kwargs)

    def test_start_convertir_requires_an_explicit_studio_profile(self):
        plan = StudioSubtitleExportPlan(
            StudioSubtitleExportMode.CONVERTIR,
            Path("source.srt"),
        )
        config = Mock()
        config.get_operational_profile_key.return_value = None

        with self.assertRaisesRegex(
            ValueError,
            "CONVERTIR requiere una identidad STUDIO estructurada",
        ):
            StudioExecutionCoordinator().run_subtitle_export(
                plan,
                subtitle_profile_key=SubtitleProfileKey(
                    "studio",
                    "vertical",
                    "subtitulo_studio_vertical_linea_unica",
                    "estandar",
                ),
                config_manager=config,
            )

    def test_start_convertir_resolves_the_selected_key_not_a_legacy_style(self):
        plan = StudioSubtitleExportPlan(
            StudioSubtitleExportMode.CONVERTIR,
            Path("source.srt"),
        )
        profile_key = OperationalProfileKey(
            "studio", "vertical", "studio_vertical"
        )
        resolver = SubtitleProfileResolver()
        selected_key = next(
            descriptor.key
            for descriptor in resolver.discover_profiles_for_family(
                "studio", "vertical", "estandar",
            )
            if resolver.load(descriptor.key).cue_policy["mode"] == "word_by_word"
        )
        selected_profile = resolver.load(selected_key)
        config = Mock()
        config.get_operational_profile_key.return_value = profile_key
        config.get_profile_config.return_value = {}
        config.get_subtitle_profile_by_key.return_value = selected_profile
        service = Mock()

        StudioExecutionCoordinator().run_subtitle_export(
            plan,
            subtitle_profile_key=selected_key,
            project=Mock(),
            config_manager=config,
            profile_loader=Mock(load=Mock(return_value=Mock())),
            export_service=service,
        )

        config.get_subtitle_profile_by_key.assert_called_once_with(selected_key)
        self.assertEqual(
            "word_by_word",
            service.export.call_args.kwargs["subtitle_profile"].cue_policy["mode"],
        )

    def test_run_application_dispatches_export_without_render_arguments(self):
        from app.core.execution_request import (
            ApplicationExecutionRequest,
            StudioExecutionRequest,
        )
        from app.core.start import run_application

        plan = StudioSubtitleExportPlan(
            StudioSubtitleExportMode.TRANSCRIBIR,
            Path("source.mp3"),
        )
        request = ApplicationExecutionRequest(
            project_name="demo",
            clear_output=False,
            operational_profile_key=None,
            subtitle_profile_key=None,
            route=StudioExecutionRequest(
                input_mode=StudioInputMode.EXPORTAR_SRT,
                plan=plan,
            ),
        )
        expected = Mock()
        with patch(
            "app.core.start.ProjectManager"
        ) as projects, patch.object(
            StudioExecutionCoordinator,
            "run_subtitle_export",
            return_value=expected,
        ) as exporter:
            result = run_application(request=request)

        self.assertIs(expected, result)
        self.assertEqual((plan,), exporter.call_args.args)
        self.assertEqual(
            {"config_manager", "project"},
            set(exporter.call_args.kwargs),
        )
        self.assertIs(projects.return_value, exporter.call_args.kwargs["project"])
        projects.assert_called_once_with(project_name="demo")

    def test_main_transcribe_sends_no_operational_profile_key(self):
        plan = StudioSubtitleExportPlan(
            StudioSubtitleExportMode.TRANSCRIBIR,
            Path("input/studio/exportar_srt/source.mp3"),
        )
        controller_request = ApplicationExecutionRequest(
            project_name="demo",
            clear_output=False,
            operational_profile_key=None,
            subtitle_profile_key=None,
            route=StudioExecutionRequest(
                input_mode="exportar_srt",
                plan=plan,
                music_path=None,
            ),
        )
        with patch.dict(os.environ, {}, clear=True), patch(
            "main.RunController"
        ) as controller, patch(
            "main.run_application",
            return_value=Mock(),
        ) as run_application_mock, patch(
            "app.cli.studio_summary._print_subtitle_export_summary"
        ):
            controller.return_value.run.return_value = controller_request
            self.assertEqual(0, main.main())
        run_application_mock.assert_called_once()
        request = run_application_mock.call_args.kwargs["request"]
        self.assertIs(plan, request.route.plan)
        self.assertEqual("exportar_srt", request.route.input_mode.value)
        self.assertIsNone(request.operational_profile_key)


class StudioSubtitleExportSummaryTest(unittest.TestCase):

    def test_summary_describes_export_without_video_render_details(self):
        plan = StudioSubtitleExportPlan(
            StudioSubtitleExportMode.CONVERTIR,
            Path("input/studio/exportar_srt/source.srt"),
        )
        result = StudioSubtitleExportResult(
            mode=StudioSubtitleExportMode.CONVERTIR,
            source_path=plan.source_path,
            output_path=Path("output/demo/subtitles/demo_word_by_word.srt"),
            subtitle_style="word_by_word",
            operation_duration=1.5,
        )
        request = ApplicationExecutionRequest(
            project_name="demo",
            clear_output=False,
            operational_profile_key=OperationalProfileKey(
                "studio",
                "vertical",
                "studio_vertical",
            ),
            subtitle_profile_key=SubtitleProfileKey(
                component="studio",
                format="vertical",
                family="minimalista",
                profile_id="subtitulo_studio_vertical_cumulative_line",
            ),
            route=StudioExecutionRequest(
                input_mode=StudioInputMode.EXPORTAR_SRT,
                plan=plan,
            ),
        )
        summary = Mock()
        with patch.object(studio_summary, "PipelineSummary", return_value=summary):
            studio_summary.print_studio_summary(request, result, 2.0)

        details = [call.args for call in summary.add_detail.call_args_list]
        self.assertIn(("Entrada", "EXPORTAR SRT ➜  VIDEO"), details)
        self.assertIn(("Modo", "CONVERTIR"), details)
        self.assertIn(("Perfil de subtítulos", "Palabra por palabra"), details)
        self.assertIn(("SRT generado", result.output_path), details)

    def test_transcribe_summary_does_not_invent_a_profile(self):
        plan = StudioSubtitleExportPlan(
            StudioSubtitleExportMode.TRANSCRIBIR,
            Path("input/studio/exportar_srt/source.mp3"),
        )
        result = StudioSubtitleExportResult(
            mode=plan.mode,
            source_path=plan.source_path,
            output_path=Path("output/demo/subtitles/demo.srt"),
            subtitle_style=None,
            operation_duration=1.5,
        )
        request = ApplicationExecutionRequest(
            project_name="demo",
            clear_output=False,
            operational_profile_key=None,
            subtitle_profile_key=None,
            route=StudioExecutionRequest(
                input_mode=StudioInputMode.EXPORTAR_SRT,
                plan=plan,
            ),
        )
        summary = Mock()
        with patch.object(studio_summary, "PipelineSummary", return_value=summary):
            studio_summary.print_studio_summary(request, result, 2.0)

        details = [call.args for call in summary.add_detail.call_args_list]
        self.assertNotIn(("Perfil / formato", ""), details)
        self.assertFalse(
            any(name == "Perfil / formato" for name, _ in details)
        )


if __name__ == "__main__":
    unittest.main()
