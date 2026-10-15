import json
from pathlib import Path

from app.modules.subtitles.io.whisper_diagnostics import (
    WhisperTranscriptionDiagnostics,
)


class WhisperDiagnosticsWriter:
    """Persist explicitly requested Whisper diagnostics as deterministic JSON."""

    SCHEMA_VERSION = 1

    def write(
        self,
        diagnostics: WhisperTranscriptionDiagnostics,
        output_path,
    ) -> Path:
        if not isinstance(diagnostics, WhisperTranscriptionDiagnostics):
            raise TypeError(
                "diagnostics must be WhisperTranscriptionDiagnostics"
            )

        output_path = Path(output_path)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "backend": diagnostics.backend,
            "backend_version": diagnostics.backend_version,
            "transcription_config": {
                "model": diagnostics.transcription_config.model,
                "device": diagnostics.transcription_config.device,
                "language": diagnostics.transcription_config.language,
                "task": diagnostics.transcription_config.task,
                "word_timestamps": diagnostics.transcription_config.word_timestamps,
                "condition_on_previous_text": (
                    diagnostics.transcription_config.condition_on_previous_text
                ),
                "no_speech_threshold": (
                    diagnostics.transcription_config.no_speech_threshold
                ),
                "logprob_threshold": (
                    diagnostics.transcription_config.logprob_threshold
                ),
                "compression_ratio_threshold": (
                    diagnostics.transcription_config.compression_ratio_threshold
                ),
                "hallucination_silence_threshold": (
                    diagnostics.transcription_config.hallucination_silence_threshold
                ),
                "temperature": diagnostics.transcription_config.temperature,
                "temperature_increment_on_fallback": (
                    diagnostics.transcription_config.temperature_increment_on_fallback
                ),
                "fp16": diagnostics.transcription_config.fp16,
                "output_format": diagnostics.transcription_config.output_format,
            },
            "segments": [
                {
                    "segment_id": segment.segment_id,
                    "seek": segment.seek,
                    "start": segment.start,
                    "end": segment.end,
                    "no_speech_prob": segment.no_speech_prob,
                    "avg_logprob": segment.avg_logprob,
                    "compression_ratio": segment.compression_ratio,
                    "temperature": segment.temperature,
                }
                for segment in diagnostics.segments
            ],
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        return output_path
