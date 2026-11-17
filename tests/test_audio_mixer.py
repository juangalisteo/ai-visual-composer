import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.modules.audio.audio_mixer import AudioMixer


def _tone(path, *, sample_rate, channels, seconds):
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", "-f", "lavfi",
            "-i", f"sine=frequency=300:duration={seconds}:sample_rate={sample_rate}",
            "-ac", str(channels), "-c:a", "libmp3lame", "-q:a", "0", str(path),
        ],
        check=True,
    )


def _probe(path):
    output = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate:format=duration",
            "-of", "json", str(path),
        ],
        capture_output=True, text=True, check=True,
    ).stdout
    document = json.loads(output)
    return (
        int(document["streams"][0]["sample_rate"]),
        float(document["format"]["duration"]),
    )


class AudioMixerSampleRateTest(unittest.TestCase):

    def test_mix_command_requests_44100_hz(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            voice_path = root / "voice.mp3"
            music_path = root / "music.mp3"
            voice_path.write_bytes(b"voice")
            music_path.write_bytes(b"music")
            output_path = root / "mixed.mp3"
            commands = []

            def run(command):
                commands.append(command)
                output_path.write_bytes(b"mixed")

            with patch.object(AudioMixer, "_run_command", side_effect=run), patch.object(
                AudioMixer, "_validate_output"
            ), patch(
                "app.modules.audio.audio_mixer.MediaProbe.get_duration", return_value=2.0
            ):
                AudioMixer().build(
                    voice_path=voice_path,
                    music_path=music_path,
                    output_path=output_path,
                )

        command = commands[0]
        self.assertEqual("libmp3lame", command[command.index("-c:a") + 1])
        self.assertEqual("44100", command[command.index("-ar") + 1])

    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"),
        "FFmpeg y FFprobe son obligatorios para la mezcla real.",
    )
    def test_real_mix_of_a_22050_hz_voice_is_44100_hz_and_keeps_its_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            voice_path = root / "voice.mp3"
            music_path = root / "music.mp3"
            output_path = root / "mixed.mp3"
            _tone(voice_path, sample_rate=22_050, channels=1, seconds=3)
            _tone(music_path, sample_rate=48_000, channels=2, seconds=1)

            AudioMixer().build(
                voice_path=voice_path,
                music_path=music_path,
                output_path=output_path,
            )

            sample_rate, duration = _probe(output_path)
            _, voice_duration = _probe(voice_path)

        self.assertEqual(44_100, sample_rate)
        self.assertLess(abs(duration - voice_duration), 0.05)


if __name__ == "__main__":
    unittest.main()
