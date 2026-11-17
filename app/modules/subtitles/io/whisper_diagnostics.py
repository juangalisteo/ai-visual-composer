from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
import json
import math
from pathlib import Path

from app.modules.subtitles.io.whisper_transcription_config import (
    WhisperTranscriptionConfig,
)


@dataclass(frozen=True)
class WhisperSegmentDiagnostics:
    """Backend metadata for one native Whisper segment."""

    segment_id: int | None
    seek: int | None
    start: float
    end: float
    no_speech_prob: float | None
    avg_logprob: float | None
    compression_ratio: float | None
    temperature: float | None

    def __post_init__(self):
        self._require_optional_int("segment_id", self.segment_id)
        self._require_optional_int("seek", self.seek)
        start = self._require_finite("start", self.start)
        end = self._require_finite("end", self.end)
        if start < 0:
            raise ValueError("start cannot be negative")
        if end < start:
            raise ValueError("end cannot be before start")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        for name in (
            "no_speech_prob",
            "avg_logprob",
            "compression_ratio",
            "temperature",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, self._require_finite(name, value))

    @staticmethod
    def _require_optional_int(name: str, value: object) -> None:
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int)
        ):
            raise TypeError(f"{name} must be an int or None")

    @staticmethod
    def _require_finite(name: str, value: object) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a number")
        result = float(value)
        if not math.isfinite(result):
            raise ValueError(f"{name} must be finite")
        return result


@dataclass(frozen=True)
class WhisperDiscardedSegmentDiagnostics:
    """A native Whisper segment removed after transcription, and why."""

    segment: WhisperSegmentDiagnostics
    reason: str

    def __post_init__(self):
        if not isinstance(self.segment, WhisperSegmentDiagnostics):
            raise TypeError("segment must be WhisperSegmentDiagnostics")
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("reason must be a non-empty string")


@dataclass(frozen=True)
class WhisperTranscriptionDiagnostics:
    """Auxiliary native-Whisper metadata, separate from subtitle timing."""

    backend: str
    backend_version: str | None
    transcription_config: WhisperTranscriptionConfig
    segments: tuple[WhisperSegmentDiagnostics, ...]
    discarded_segments: tuple[WhisperDiscardedSegmentDiagnostics, ...] = ()

    def __post_init__(self):
        if not isinstance(self.backend, str) or not self.backend:
            raise ValueError("backend must be a non-empty string")
        if self.backend_version is not None and not isinstance(
            self.backend_version,
            str,
        ):
            raise TypeError("backend_version must be a string or None")
        if not isinstance(self.transcription_config, WhisperTranscriptionConfig):
            raise TypeError(
                "transcription_config must be WhisperTranscriptionConfig"
            )
        if not isinstance(self.segments, tuple) or not all(
            isinstance(segment, WhisperSegmentDiagnostics)
            for segment in self.segments
        ):
            raise TypeError(
                "segments must be a tuple of WhisperSegmentDiagnostics"
            )
        if not isinstance(self.discarded_segments, tuple) or not all(
            isinstance(segment, WhisperDiscardedSegmentDiagnostics)
            for segment in self.discarded_segments
        ):
            raise TypeError(
                "discarded_segments must be a tuple of "
                "WhisperDiscardedSegmentDiagnostics"
            )


class WhisperDiagnosticsParser:
    """Read only diagnostic metadata from native Whisper JSON output."""

    def __init__(self, backend_version_resolver=None):
        self.backend_version_resolver = (
            backend_version_resolver
            or resolve_openai_whisper_version
        )

    def parse(
        self,
        path,
        transcription_config: WhisperTranscriptionConfig,
    ) -> WhisperTranscriptionDiagnostics:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"No existe metadata Whisper: {path}")
        if not isinstance(transcription_config, WhisperTranscriptionConfig):
            raise TypeError(
                "Whisper diagnostics requiere WhisperTranscriptionConfig"
            )

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("Metadata Whisper inválida.") from error

        raw_segments = data.get("segments", [])
        if not isinstance(raw_segments, list):
            raise ValueError("Metadata Whisper sin segments válido.")

        segments = tuple(
            self._parse_segment(raw_segment)
            for raw_segment in raw_segments
            if isinstance(raw_segment, dict)
        )
        raw_discarded = data.get("discarded_segments", [])
        if not isinstance(raw_discarded, list):
            raise ValueError("Metadata Whisper sin discarded_segments válido.")

        discarded_segments = tuple(
            self._parse_discarded(raw_entry)
            for raw_entry in raw_discarded
            if isinstance(raw_entry, dict)
        )
        try:
            backend_version = self.backend_version_resolver()
        except (OSError, ValueError):
            backend_version = None

        return WhisperTranscriptionDiagnostics(
            backend="openai-whisper",
            backend_version=backend_version,
            transcription_config=transcription_config,
            segments=segments,
            discarded_segments=discarded_segments,
        )

    @staticmethod
    def _parse_segment(raw_segment) -> WhisperSegmentDiagnostics:
        try:
            return WhisperSegmentDiagnostics(
                segment_id=raw_segment.get("id"),
                seek=raw_segment.get("seek"),
                start=raw_segment["start"],
                end=raw_segment["end"],
                no_speech_prob=raw_segment.get("no_speech_prob"),
                avg_logprob=raw_segment.get("avg_logprob"),
                compression_ratio=raw_segment.get("compression_ratio"),
                temperature=raw_segment.get("temperature"),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Segment diagnostics Whisper inválido.") from error

    @classmethod
    def _parse_discarded(cls, raw_entry) -> WhisperDiscardedSegmentDiagnostics:
        raw_segment = raw_entry.get("segment")
        if not isinstance(raw_segment, dict):
            raise ValueError("Segmento descartado Whisper inválido.")
        try:
            return WhisperDiscardedSegmentDiagnostics(
                segment=cls._parse_segment(raw_segment),
                reason=raw_entry.get("reason"),
            )
        except (TypeError, ValueError) as error:
            raise ValueError("Segmento descartado Whisper inválido.") from error


def resolve_openai_whisper_version() -> str | None:
    """Return installed backend version when packaging metadata is available."""
    try:
        return version("openai-whisper")
    except (PackageNotFoundError, OSError, ValueError):
        return None
