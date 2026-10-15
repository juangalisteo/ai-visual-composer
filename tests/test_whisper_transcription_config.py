from dataclasses import FrozenInstanceError
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from app.modules.subtitles.io.subtitle_builder import SubtitleBuilder
from app.modules.subtitles.io.whisper_transcription_config import (
    WhisperTranscriptionConfig,
)


def test_whisper_transcription_config_declares_the_b0_baseline_immutably():
    config = WhisperTranscriptionConfig()

    assert config.model == "medium"
    assert config.device == "cuda"
    assert config.language == "Spanish"
    assert config.task == "transcribe"
    assert config.word_timestamps is True
    assert config.condition_on_previous_text is True
    assert config.no_speech_threshold == 0.6
    assert config.logprob_threshold == -1.0
    assert config.compression_ratio_threshold == 2.4
    assert config.hallucination_silence_threshold is None
    assert config.temperature == 0.0
    assert config.temperature_increment_on_fallback == 0.2
    assert config.fp16 is True

    with pytest.raises(FrozenInstanceError):
        config.model = "other"


def test_whisper_transcription_config_translates_b0_to_explicit_cli_arguments():
    arguments = WhisperTranscriptionConfig().cli_arguments()

    assert arguments == (
        "--model", "medium",
        "--task", "transcribe",
        "--language", "Spanish",
        "--word_timestamps", "True",
        "--condition_on_previous_text", "True",
        "--no_speech_threshold", "0.6",
        "--logprob_threshold", "-1.0",
        "--compression_ratio_threshold", "2.4",
        "--temperature", "0.0",
        "--temperature_increment_on_fallback", "0.2",
        "--fp16", "True",
        "--output_format", "all",
        "--device", "cuda",
    )
    assert "--hallucination_silence_threshold" not in arguments


def test_non_none_hallucination_silence_threshold_is_translatable_but_not_default():
    arguments = WhisperTranscriptionConfig(
        hallucination_silence_threshold=1.0,
    ).cli_arguments()

    threshold_index = arguments.index("--hallucination_silence_threshold")
    assert arguments[threshold_index + 1] == "1.0"


def test_subtitle_builder_uses_the_injected_transcription_config():
    config = WhisperTranscriptionConfig(
        model="test_model",
        condition_on_previous_text=False,
        hallucination_silence_threshold=1.0,
    )
    commands = []

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        audio_path = root / "source.mp3"
        output_path = root / "captions.srt"
        audio_path.write_bytes(b"audio")

        def fake_run(command, check):
            commands.append(command)
            output_directory = Path(command[command.index("--output_dir") + 1])
            (output_directory / "source.srt").write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nHola\n",
                encoding="utf-8",
            )

        with patch(
            "app.modules.subtitles.io.subtitle_builder.subprocess.run",
            side_effect=fake_run,
        ):
            SubtitleBuilder(transcription_config=config).build(
                audio_path=audio_path,
                output_path=output_path,
            )

    command = commands[0]
    assert command[:4] == ["python", "-m", "whisper", str(audio_path)]
    assert command[4:-2] == list(config.cli_arguments())
    assert command[-2] == "--output_dir"
