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

    def test_video_runtime_passes_real_timing_and_cleans_all_derivatives(self):
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
        renderer.render.return_value = "rendered"
        resolver = Mock(resolve=Mock(return_value=Path("output/demo/video/demo.mp4")))

        result = ejecutar_studio(
            subtitle_style="word_by_word",
            input_mode="video",
            preparation_service=Mock(return_value=preparation),
            external_subtitle_preparation_service=subtitle_service,
            render_service=renderer,
            output_path_resolver=resolver,
            project=Mock(),
        )

        self.assertEqual("rendered", result)
        kwargs = renderer.render.call_args.kwargs
        self.assertEqual("whisper", kwargs["subtitle_timing"].source)
        self.assertFalse(subtitle_service.subtitle_path.exists())
        self.assertFalse(subtitle_service.audio_path.exists())
        self.assertFalse(subtitle_service.subtitle_path.parent.exists())

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
            controller, "select_studio_subtitle_config",
            side_effect=lambda _: order.append("subtitle") or "single_line",
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

        self.assertEqual(["profile", "input", "subtitle"], order)
        self.assertEqual("video", options["studio_input_mode"])


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
