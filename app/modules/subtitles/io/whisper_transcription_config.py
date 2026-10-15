from dataclasses import dataclass
import math


@dataclass(frozen=True)
class WhisperTranscriptionConfig:
    """Immutable technical baseline for a Whisper CLI transcription."""

    model: str = "medium"
    device: str = "cuda"
    language: str = "Spanish"
    task: str = "transcribe"
    word_timestamps: bool = True
    condition_on_previous_text: bool = True
    no_speech_threshold: float = 0.6
    logprob_threshold: float = -1.0
    compression_ratio_threshold: float = 2.4
    hallucination_silence_threshold: float | None = None
    temperature: float = 0.0
    temperature_increment_on_fallback: float = 0.2
    fp16: bool = True
    output_format: str = "all"

    def __post_init__(self):
        self._require_non_empty_string("model", self.model)
        self._require_non_empty_string("device", self.device)
        self._require_non_empty_string("language", self.language)
        self._require_non_empty_string("task", self.task)
        self._require_non_empty_string("output_format", self.output_format)
        self._require_bool("word_timestamps", self.word_timestamps)
        self._require_bool(
            "condition_on_previous_text",
            self.condition_on_previous_text,
        )
        self._require_bool("fp16", self.fp16)
        self._require_range(
            "no_speech_threshold",
            self.no_speech_threshold,
            minimum=0.0,
            maximum=1.0,
        )
        self._require_finite("logprob_threshold", self.logprob_threshold)
        self._require_range(
            "compression_ratio_threshold",
            self.compression_ratio_threshold,
            minimum=0.0,
            exclusive_minimum=True,
        )
        self._require_range(
            "temperature",
            self.temperature,
            minimum=0.0,
        )
        self._require_range(
            "temperature_increment_on_fallback",
            self.temperature_increment_on_fallback,
            minimum=0.0,
            exclusive_minimum=True,
        )

        if self.hallucination_silence_threshold is not None:
            self._require_range(
                "hallucination_silence_threshold",
                self.hallucination_silence_threshold,
                minimum=0.0,
                exclusive_minimum=True,
            )

    def cli_arguments(self) -> tuple[str, ...]:
        """Translate this configuration once into Whisper CLI arguments."""
        arguments = (
            "--model",
            self.model,
            "--task",
            self.task,
            "--language",
            self.language,
            "--word_timestamps",
            str(self.word_timestamps),
            "--condition_on_previous_text",
            str(self.condition_on_previous_text),
            "--no_speech_threshold",
            str(self.no_speech_threshold),
            "--logprob_threshold",
            str(self.logprob_threshold),
            "--compression_ratio_threshold",
            str(self.compression_ratio_threshold),
            "--temperature",
            str(self.temperature),
            "--temperature_increment_on_fallback",
            str(self.temperature_increment_on_fallback),
            "--fp16",
            str(self.fp16),
            "--output_format",
            self.output_format,
            "--device",
            self.device,
        )

        if self.hallucination_silence_threshold is None:
            return arguments

        return arguments + (
            "--hallucination_silence_threshold",
            str(self.hallucination_silence_threshold),
        )

    @staticmethod
    def _require_non_empty_string(name: str, value: object) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError(f"{name} must be a non-empty string")

    @staticmethod
    def _require_bool(name: str, value: object) -> None:
        if not isinstance(value, bool):
            raise TypeError(f"{name} must be a bool")

    @staticmethod
    def _require_finite(name: str, value: object) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a number")
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")

    @classmethod
    def _require_range(
        cls,
        name: str,
        value: object,
        *,
        minimum: float,
        maximum: float | None = None,
        exclusive_minimum: bool = False,
    ) -> None:
        cls._require_finite(name, value)
        if value < minimum or (exclusive_minimum and value == minimum):
            raise ValueError(f"{name} is below its supported range")
        if maximum is not None and value > maximum:
            raise ValueError(f"{name} is above its supported range")
