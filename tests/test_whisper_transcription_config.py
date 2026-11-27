from dataclasses import FrozenInstanceError
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from app.modules.subtitles.io.subtitle_builder import SubtitleBuilder
from app.modules.subtitles.io.whisper_settings import (
    whisper_transcription_config,
)
from app.modules.subtitles.io.whisper_transcription_config import (
    WhisperTranscriptionConfig,
)
from app.shared.operational_error import OperationalError


REAL_CONFIG = Path(__file__).resolve().parents[1] / "config" / "whisper.json"

# Model, device and language have no value in the code (config/whisper.json).
TEST_TRANSCRIPTION = {
    "model": "test_model",
    "device": "test_device",
    "language": "test_language",
}

# The Whisper command arguments before config/whisper.json existed, when
# model, device and language were written in WhisperTranscriptionConfig.
B0_CLI_ARGUMENTS = (
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


def test_model_device_and_language_have_no_value_in_the_code():
    with pytest.raises(TypeError):
        WhisperTranscriptionConfig()


def test_whisper_transcription_config_keeps_the_rest_of_the_b0_baseline_immutably():
    config = WhisperTranscriptionConfig(**TEST_TRANSCRIPTION)

    assert config.model == "test_model"
    assert config.device == "test_device"
    assert config.language == "test_language"
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


def test_the_project_config_gives_the_same_whisper_arguments_as_before():
    config = whisper_transcription_config(REAL_CONFIG)

    assert config == WhisperTranscriptionConfig(
        model="medium",
        device="cuda",
        language="Spanish",
    )
    assert config.cli_arguments() == B0_CLI_ARGUMENTS
    assert "--hallucination_silence_threshold" not in config.cli_arguments()


def test_non_none_hallucination_silence_threshold_is_translatable_but_not_default():
    arguments = WhisperTranscriptionConfig(
        **TEST_TRANSCRIPTION,
        hallucination_silence_threshold=1.0,
    ).cli_arguments()

    threshold_index = arguments.index("--hallucination_silence_threshold")
    assert arguments[threshold_index + 1] == "1.0"


def _run_builder(builder, root):
    commands = []
    audio_path = root / "source.mp3"
    output_path = root / "captions.srt"
    audio_path.write_bytes(b"audio")

    def fake_run(command, check, **_options):
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
        builder.build(
            audio_path=audio_path,
            output_path=output_path,
        )

    return commands, audio_path


def test_subtitle_builder_uses_the_injected_transcription_config():
    config = WhisperTranscriptionConfig(
        **TEST_TRANSCRIPTION,
        condition_on_previous_text=False,
        hallucination_silence_threshold=1.0,
    )

    with tempfile.TemporaryDirectory() as directory:
        commands, audio_path = _run_builder(
            SubtitleBuilder(transcription_config=config),
            Path(directory),
        )

    command = commands[0]
    assert command[:4] == ["python", "-m", "whisper", str(audio_path)]
    assert command[4:-2] == list(config.cli_arguments())
    assert command[-2] == "--output_dir"


def _write_config(root, content):
    config = Path(root) / "config"
    config.mkdir(exist_ok=True)
    (config / "whisper.json").write_text(content, encoding="utf-8")


def test_subtitle_builder_reads_config_whisper_json_without_an_injected_config(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    _write_config(
        tmp_path,
        '{"model": " test_model ", "device": "test_device", '
        '"language": "test_language"}',
    )
    builder = SubtitleBuilder()

    commands, _ = _run_builder(builder, tmp_path)

    expected = WhisperTranscriptionConfig(**TEST_TRANSCRIPTION)
    assert commands[0][4:-2] == list(expected.cli_arguments())
    assert builder.transcription_config == expected


def test_the_project_subtitle_builder_runs_whisper_as_before(tmp_path):
    commands, _ = _run_builder(SubtitleBuilder(), tmp_path)

    assert tuple(commands[0][4:-2]) == B0_CLI_ARGUMENTS


@pytest.mark.parametrize("key", ["model", "device", "language"])
def test_missing_key_is_a_config_error_before_running_whisper(
    tmp_path,
    monkeypatch,
    key,
):
    monkeypatch.chdir(tmp_path)
    values = dict(TEST_TRANSCRIPTION)
    del values[key]
    _write_config(
        tmp_path,
        "{" + ", ".join(f'"{name}": "{value}"' for name, value in values.items()) + "}",
    )

    audio_path = tmp_path / "source.mp3"
    audio_path.write_bytes(b"audio")

    with patch(
        "app.modules.subtitles.io.subtitle_builder.subprocess.run",
    ) as run, pytest.raises(OperationalError) as context:
        SubtitleBuilder().build(
            audio_path=audio_path,
            output_path=tmp_path / "captions.srt",
        )

    run.assert_not_called()
    assert context.value.context.family == "CONFIG"
    assert context.value.context.resource == "config/whisper.json"
    assert (
        context.value.context.user_message
        == f"«config/whisper.json» no declara «{key}»."
    )


@pytest.mark.parametrize("value", ['""', '"  "', "3", "null", "true", '["x"]'])
@pytest.mark.parametrize("key", ["model", "device", "language"])
def test_invalid_value_is_a_config_error(tmp_path, monkeypatch, key, value):
    monkeypatch.chdir(tmp_path)
    values = {
        name: f'"{text}"'
        for name, text in TEST_TRANSCRIPTION.items()
    }
    values[key] = value
    _write_config(
        tmp_path,
        "{" + ", ".join(f'"{name}": {text}' for name, text in values.items()) + "}",
    )

    with pytest.raises(OperationalError) as context:
        whisper_transcription_config()

    assert context.value.context.family == "CONFIG"
    assert context.value.context.resource == "config/whisper.json"
    assert (
        context.value.context.user_message
        == f"En «config/whisper.json», «{key}» debe ser un texto no vacío."
    )


def test_missing_file_is_a_config_error_with_the_relative_path(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(OperationalError) as context:
        SubtitleBuilder().transcription_config

    assert context.value.context.family == "CONFIG"
    assert context.value.context.resource == "config/whisper.json"
    assert "«config/whisper.json»" in context.value.context.user_message
