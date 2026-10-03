import hashlib
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.modules.studio import StudioProfileLoader, StudioRenderService
from app.modules.subtitles.pipeline.cue_transformer import SubtitleCueTransformer
from app.shared.media_probe import MediaInfo, MediaProbe
from app.shared.profile_identity import OperationalProfileKey, ProfileKey
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


class StudioSubtitleAdaptationTest(unittest.TestCase):

    SOURCE_SRT = (
        "1\n"
        "00:00:00,000 --> 00:00:00,600\n"
        "Hola mundo.\n\n"
        "2\n"
        "00:00:00,800 --> 00:00:04,800\n"
        "¿Cómo observa la conciencia el océano? Con atención serena; "
        "sin perder nunca su direccion interior.\n\n"
        "3\n"
        "00:00:05,000 --> 00:00:07,000\n"
        "Después integra símbolos, energía y transformación.\n"
    )

    def setUp(self):
        self.profile_key = OperationalProfileKey(
            "studio", "instagram", "studio_instagram"
        )
        self.subtitle_parent_key = ProfileKey.for_component("studio", "instagram")
        self.profile = _load_studio_profile(self.profile_key)

    def _subtitle_profile(self, style):
        if style == "three_two_words":
            return SubtitleProfileResolver().load(
                SubtitleProfileKey(
                    "studio", "instagram",
                    "subtitulo_studio_instagram_linea_unica", "estandar",
                )
            )
        return SubtitleProfileResolver().load(
            SubtitleProfileKey.for_profile(self.subtitle_parent_key, style)
        )

    def _transform(self, style, content=None):
        return SubtitleCueTransformer(
            subtitle_profile=self._subtitle_profile(style),
            render_fps=self.profile.fps,
        ).transform(content or self.SOURCE_SRT)

    def test_same_source_produces_distinct_temporal_cue_structures(self):
        three_two_words = self._transform("three_two_words")
        word_by_word = self._transform("word_by_word")
        single_cues = self._parse(three_two_words)
        word_cues = self._parse(word_by_word)

        self.assertNotEqual(three_two_words, word_by_word)
        self.assertGreater(len(single_cues), 3)
        self.assertGreater(len(word_cues), len(single_cues))
        self.assertTrue(all(len(text) <= 60 for _, _, text in single_cues))
        self.assertTrue(all(len(text.split()) == 1 for _, _, text in word_cues))

        for cues in (single_cues, word_cues):
            self.assertEqual(0, cues[0][0])
            self.assertEqual(7000, cues[-1][1])
            self._assert_valid_timeline(cues)

        expected_text = self._source_text(self.SOURCE_SRT).replace(";", "")
        self.assertEqual(
            expected_text,
            " ".join(text for _, _, text in single_cues),
        )
        self.assertEqual(
            expected_text.replace(",", "").replace(".", ""),
            " ".join(text for _, _, text in word_cues),
        )
        rendered_word_text = " ".join(text for _, _, text in word_cues)
        self.assertNotIn(",", rendered_word_text)
        self.assertNotIn(".", rendered_word_text)
        self.assertIn("¿Cómo", word_by_word)
        self.assertIn("símbolos", word_by_word)

    def test_render_uses_the_supplied_persisted_subtitle_and_preserves_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ruta con espacios y acentos"
            root.mkdir()
            video_path = root / "video fuente.mp4"
            subtitle_path = root / "subtitulos fuente.srt"
            output_path = root / "resultado.mp4"
            video_path.write_bytes(b"source-video")
            subtitle_path.write_text(self.SOURCE_SRT, encoding="utf-8")
            source_video = video_path.read_bytes()
            source_subtitle = subtitle_path.read_bytes()
            captured = {}
            runner = Mock()

            def run(command):
                captured["command"] = tuple(command)
                Path(command[-1]).write_bytes(b"rendered")

            runner.run.side_effect = run
            validator = Mock()
            validator.validate.return_value = 7.0
            service = StudioRenderService(
                runner=runner,
                probe=self._probe(7.0),
                output_validator=validator,
            )
            result = service.render(
                video_path=video_path,
                subtitle_path=subtitle_path,
                profile_key=self.profile_key,
                profile=self.profile,
                subtitle_profile=self._subtitle_profile("word_by_word"),
                output_path=output_path,
            )

            self.assertEqual(output_path, result.output_path)
            self.assertIn(subtitle_path.name, " ".join(captured["command"]))
            self.assertEqual(source_video, video_path.read_bytes())
            self.assertEqual(source_subtitle, subtitle_path.read_bytes())

    def test_render_error_preserves_the_supplied_persisted_subtitle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video_path = root / "source.mp4"
            subtitle_path = root / "source.srt"
            output_path = root / "result.mp4"
            video_path.write_bytes(b"source-video")
            subtitle_path.write_text(self.SOURCE_SRT, encoding="utf-8")
            runner = Mock()
            runner.run.side_effect = RuntimeError("render failed")
            service = StudioRenderService(
                runner=runner,
                probe=self._probe(7.0),
                output_validator=Mock(),
            )
            with self.assertRaisesRegex(RuntimeError, "render failed"):
                service.render(
                    video_path=video_path,
                    subtitle_path=subtitle_path,
                    profile_key=self.profile_key,
                    profile=self.profile,
                    subtitle_profile=self._subtitle_profile("three_two_words"),
                    output_path=output_path,
                )

            self.assertEqual(self.SOURCE_SRT, subtitle_path.read_text(encoding="utf-8"))
            self.assertFalse(output_path.exists())

    @staticmethod
    def _probe(duration):
        probe = Mock()
        probe.inspect.return_value = MediaInfo(
            duration=duration,
            width=640,
            height=360,
            fps=30.0,
            pixel_format="yuv420p",
            video_codec="h264",
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
        )
        return probe

    @staticmethod
    def _parse(content):
        cues = []
        for block in re.split(r"\n\s*\n", content.strip()):
            lines = block.splitlines()
            match = re.fullmatch(
                r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*"
                r"(\d{2}:\d{2}:\d{2},\d{3})",
                lines[1],
            )
            if match is None:
                raise AssertionError(f"Cue invalido: {block}")
            cues.append((
                StudioSubtitleAdaptationTest._milliseconds(match.group(1)),
                StudioSubtitleAdaptationTest._milliseconds(match.group(2)),
                " ".join(lines[2:]).strip(),
            ))
        return cues

    @staticmethod
    def _milliseconds(value):
        hours, minutes, rest = value.split(":")
        seconds, milliseconds = rest.split(",")
        return (
            int(hours) * 3_600_000
            + int(minutes) * 60_000
            + int(seconds) * 1_000
            + int(milliseconds)
        )

    @staticmethod
    def _source_text(content):
        blocks = re.split(r"\n\s*\n", content.strip())
        return " ".join(
            " ".join(block.splitlines()[2:]).strip()
            for block in blocks
        )

    def _assert_valid_timeline(self, cues):
        previous_end = -1
        for start, end, text in cues:
            self.assertGreater(end, start)
            self.assertGreaterEqual(start, previous_end)
            self.assertTrue(text)
            previous_end = end


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "FFmpeg y FFprobe son obligatorios para la prueba real STUDIO.",
)
class StudioSubtitleAdaptationRealFFmpegTest(unittest.TestCase):

    def test_same_sources_render_distinct_valid_styles_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "prueba con espacios"
            root.mkdir()
            source = root / "video fuente.mp4"
            subtitle = root / "subtitulos fuente.srt"
            subtitle.write_text(
                "1\n"
                "00:00:00,200 --> 00:00:02,800\n"
                "La conciencia observa el océano y cambia con serenidad.\n",
                encoding="utf-8",
            )
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "lavfi", "-i",
                    "color=c=black:s=320x180:r=30:d=3",
                    "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=3",
                    "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(source),
                ],
                capture_output=True,
                check=True,
            )
            source_hash = hashlib.sha256(source.read_bytes()).digest()
            subtitle_hash = hashlib.sha256(subtitle.read_bytes()).digest()
            key = OperationalProfileKey("studio", "instagram", "studio_instagram")
            subtitle_parent_key = ProfileKey.for_component("studio", "instagram")
            profile = _load_studio_profile(key)
            resolver = SubtitleProfileResolver()
            outputs = []
            transformed = []

            for style in ("single_line", "word_by_word"):
                subtitle_profile = resolver.load(
                    SubtitleProfileKey.for_profile(subtitle_parent_key, style)
                )
                rendered_subtitle = root / f"{style}.srt"
                rendered_subtitle.write_text(
                    SubtitleCueTransformer(
                        subtitle_profile,
                        profile.fps,
                    ).transform(subtitle.read_text(encoding="utf-8")),
                    encoding="utf-8",
                )
                transformed.append(rendered_subtitle.read_text(encoding="utf-8"))
                result = StudioRenderService().render(
                    video_path=source,
                    subtitle_path=rendered_subtitle,
                    profile_key=key,
                    profile=profile,
                    subtitle_profile=subtitle_profile,
                    output_path=root / f"{style}.mp4",
                )
                outputs.append(result.output_path)
                info = MediaProbe().inspect(result.output_path)
                self.assertEqual((1080, 1920), (info.width, info.height))
                self.assertTrue(info.has_audio)
                subprocess.run(
                    [
                        "ffmpeg", "-v", "error", "-i", str(result.output_path),
                        "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-",
                    ],
                    capture_output=True,
                    check=True,
                )

            self.assertNotEqual(transformed[0], transformed[1])
            self.assertNotEqual(
                hashlib.sha256(outputs[0].read_bytes()).digest(),
                hashlib.sha256(outputs[1].read_bytes()).digest(),
            )
            self.assertEqual(source_hash, hashlib.sha256(source.read_bytes()).digest())
            self.assertEqual(subtitle_hash, hashlib.sha256(subtitle.read_bytes()).digest())


if __name__ == "__main__":
    unittest.main()
