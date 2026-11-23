"""Generic capability: synthesize speech in a separate Python process.

Some voice engines need their own Python environment (their own torch and
dependencies), declared in the voice document. Their backend runs a worker
script with that environment's interpreter as a child process: the worker
loads the model, writes one WAV per text segment and a result document, and
exits, which frees the GPU for the next stages. There is no time limit
(AGENTS.md §8).

This module holds what every such backend shares: reading the declared
runtime, splitting the text into segments with their pauses, running the
process and joining the segment WAVs with the declared silences. A backend
only adds its worker script and its own options.

Worker protocol (version 1):

* command: ``<python> -I -X utf8 <worker.py> <request.json>``;
* the request document carries ``protocol``, ``device``, ``seed``,
  ``segments`` (``text`` and ``output`` WAV path) and ``result`` (path of the
  result document), plus the backend's own keys;
* the worker prints ``AIVC_PROGRESS <done> <total>`` lines on stdout after each
  segment; anything else goes to its log;
* the result document is ``{"status": "ok", "sample_rate": <hz>}`` or
  ``{"status": "error", "kind": <kind>, "message": <Spanish text>}`` with
  ``kind`` in ``configuration``, ``resource_unavailable`` or ``synthesis``.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import subprocess
import wave

from app.modules.audio.tts_contracts import (
    TtsBackendDiagnostic,
    TtsBackendError,
    TtsBackendErrorKind,
    TtsPause,
    TtsVoiceConfigurationError,
)
from app.shared.progress_logger import ProgressLogger


WORKER_PROTOCOL_VERSION = 1
PROGRESS_PREFIX = "AIVC_PROGRESS"
REQUEST_FILE_NAME = "tts_request.json"
RESULT_FILE_NAME = "tts_result.json"
LOG_FILE_NAME = "tts_worker.log"
SETUP_HINT = (
    "Monta el entorno de la voz (docs/INSTALL.md, apartado 10) o corrige la "
    "ruta en el documento de la voz."
)

_RUNTIME_FIELDS = frozenset({"python_path", "cache_dir", "device"})
_SEGMENTATION_FIELDS = frozenset({"max_characters"})
_DEVICES = ("cuda", "cpu")
_RESULT_ERROR_KINDS = {
    "resource_unavailable": TtsBackendErrorKind.RESOURCE_UNAVAILABLE,
    "synthesis": TtsBackendErrorKind.SYNTHESIS,
}
_PARAGRAPH_BREAK = re.compile(r"\n[^\S\n]*\n\s*")
# A sentence end (. ! ? … and runs of them) plus closing quotes or brackets,
# followed by whitespace.
_SENTENCE_END = re.compile(r"[.!?…]+[\"'”’»)\]]*(?=\s)")
_LOG_LINE_LIMIT = 300

ProcessLauncher = Callable[..., int]
ProgressReporter = Callable[[int, int], None]


@dataclass(frozen=True)
class SpeechSegment:
    """One piece of text read in one call, and the silence written after it."""

    text: str
    pause_after_seconds: float


@dataclass(frozen=True)
class ExternalTtsRuntime:
    """Declared environment of a voice that runs in its own process."""

    python_path: Path
    cache_dir: Path
    device: str


def parse_external_tts_runtime(
    options: Mapping[str, object],
    project_root: Path,
) -> ExternalTtsRuntime:
    """Read ``backend_options.runtime``; every path stays inside the project."""
    runtime = require_options_mapping(options, "runtime", "backend_options")
    reject_unknown_options(runtime, _RUNTIME_FIELDS, "backend_options.runtime")
    device = runtime.get("device")
    if device not in _DEVICES:
        raise TtsVoiceConfigurationError(
            "backend_options.runtime.device debe ser "
            + " o ".join(f"«{name}»" for name in _DEVICES)
            + f"; se recibió {device!r}."
        )
    return ExternalTtsRuntime(
        python_path=resolve_project_path(
            runtime.get("python_path"),
            project_root,
            "backend_options.runtime.python_path",
            must_be="file",
        ),
        cache_dir=resolve_project_path(
            runtime.get("cache_dir"),
            project_root,
            "backend_options.runtime.cache_dir",
            must_be=None,
        ),
        device=device,
    )


def resolve_project_path(
    value: object,
    project_root: Path,
    label: str,
    *,
    must_be: str | None,
) -> Path:
    """Resolve a declared path relative to the project root.

    ``must_be`` is ``"file"``, ``"dir"`` or None (the path may not exist yet).
    A missing resource gives a CONFIG error that names its relative path.
    The declared text must stay inside the project folder (no ``..`` out of
    it, no absolute path); links inside the folder are followed as they are,
    so a ``models`` folder linked elsewhere still works.
    """
    if not isinstance(value, str) or not value.strip():
        raise TtsVoiceConfigurationError(
            f"{label} debe ser una ruta relativa a la carpeta del proyecto; "
            f"se recibió {value!r}."
        )
    declared = Path(value.strip())
    root = Path(os.path.abspath(project_root))
    candidate = Path(os.path.normpath(root / declared))
    if declared.is_absolute() or not candidate.is_relative_to(root):
        raise TtsVoiceConfigurationError(
            f"{label} debe ser una ruta relativa dentro de la carpeta del "
            f"proyecto; se recibió «{declared.as_posix()}»."
        )
    exists = {
        "file": candidate.is_file,
        "dir": candidate.is_dir,
        None: lambda: True,
    }[must_be]()
    if not exists:
        raise TtsVoiceConfigurationError(
            f"no existe «{declared.as_posix()}» ({label}). {SETUP_HINT}"
        )
    return candidate


def require_options_mapping(
    document: Mapping[str, object],
    name: str,
    parent_label: str,
) -> Mapping[str, object]:
    value = document.get(name)
    if not isinstance(value, Mapping):
        raise TtsVoiceConfigurationError(
            f"{parent_label}.{name} debe ser un objeto; se recibió {value!r}."
        )
    return value


def reject_unknown_options(
    document: Mapping[str, object],
    allowed: frozenset[str],
    label: str,
) -> None:
    unknown = sorted(str(name) for name in document if name not in allowed)
    if unknown:
        raise TtsVoiceConfigurationError(
            f"{label} no admite las claves: {', '.join(unknown)}. "
            f"Claves válidas: {', '.join(sorted(allowed))}."
        )


def require_non_negative_number(value: object, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise TtsVoiceConfigurationError(
            f"{label} debe ser un número mayor o igual que 0; se recibió "
            f"{value!r}."
        )
    return float(value)


def parse_segmentation(options: Mapping[str, object]) -> int:
    """Read ``backend_options.segmentation.max_characters`` (whole number ≥ 1)."""
    segmentation = require_options_mapping(options, "segmentation", "backend_options")
    reject_unknown_options(
        segmentation,
        _SEGMENTATION_FIELDS,
        "backend_options.segmentation",
    )
    value = segmentation.get("max_characters")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise TtsVoiceConfigurationError(
            "backend_options.segmentation.max_characters debe ser un número "
            f"entero mayor que 0; se recibió {value!r}."
        )
    return value


def split_speech_segments(
    text: str,
    *,
    sentence_pause_seconds: float,
    paragraph_pause_seconds: float,
    max_characters: int,
) -> tuple[SpeechSegment, ...]:
    """Split text into segments of whole sentences, each read in one call.

    Consecutive sentences of one paragraph share a segment while it stays
    within ``max_characters``; a longer sentence goes alone. Paragraphs are
    separated by one or more blank lines and never share a segment. The
    sentence pause is written between segments of a paragraph, the paragraph
    pause replaces it at a paragraph break, and nothing follows the last
    segment. A piece without letters or digits (a stray mark) joins the
    previous one.
    """
    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [
        [
            " ".join(sentence.split())
            for sentence in _split_sentences(paragraph)
        ]
        for paragraph in _PARAGRAPH_BREAK.split(normalized)
        if paragraph.strip()
    ]
    pieces: list[tuple[str, bool]] = []
    for paragraph in paragraphs:
        starts_paragraph = True
        for sentence in paragraph:
            if not any(character.isalnum() for character in sentence):
                if pieces:
                    previous_text, previous_start = pieces[-1]
                    pieces[-1] = (f"{previous_text} {sentence}", previous_start)
                continue
            if not starts_paragraph:
                previous_text, previous_start = pieces[-1]
                joined = f"{previous_text} {sentence}"
                if len(joined) <= max_characters:
                    pieces[-1] = (joined, previous_start)
                    continue
            pieces.append((sentence, starts_paragraph))
            starts_paragraph = False

    segments = []
    for index, (piece, _) in enumerate(pieces):
        if index + 1 == len(pieces):
            pause = 0.0
        elif pieces[index + 1][1]:
            pause = paragraph_pause_seconds
        else:
            pause = sentence_pause_seconds
        segments.append(SpeechSegment(text=piece, pause_after_seconds=pause))
    return tuple(segments)


def _split_sentences(paragraph: str) -> tuple[str, ...]:
    pieces = []
    start = 0
    for match in _SENTENCE_END.finditer(paragraph):
        pieces.append(paragraph[start : match.end()])
        start = match.end()
    pieces.append(paragraph[start:])
    return tuple(piece.strip() for piece in pieces if piece.strip())


class ExternalTtsProcess:
    """Run one worker script in its voice environment and read its result."""

    def __init__(
        self,
        *,
        launcher: ProcessLauncher | None = None,
        progress: ProgressReporter | None = None,
        base_environment: Mapping[str, str] | None = None,
    ):
        self._launcher = launcher or launch_worker_process
        self._progress = progress or _report_progress
        self._base_environment = base_environment

    def run(
        self,
        *,
        engine_label: str,
        runtime: ExternalTtsRuntime,
        worker_path: Path,
        workspace: Path,
        segments: Sequence[SpeechSegment],
        seed: int | None,
        engine_request: Mapping[str, object],
    ) -> tuple[tuple[Path, ...], int]:
        """Synthesize every segment; return their WAV paths and sample rate."""
        workspace = Path(workspace)
        segment_paths = tuple(
            workspace / f"segment_{index:03d}.wav"
            for index in range(1, len(segments) + 1)
        )
        result_path = workspace / RESULT_FILE_NAME
        request_path = workspace / REQUEST_FILE_NAME
        request = {
            **engine_request,
            "protocol": WORKER_PROTOCOL_VERSION,
            "device": runtime.device,
            "seed": seed,
            "segments": [
                {"text": segment.text, "output": str(path)}
                for segment, path in zip(segments, segment_paths)
            ],
            "result": str(result_path),
        }
        request_path.write_text(
            json.dumps(request, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log_path = workspace / LOG_FILE_NAME
        command = [
            str(runtime.python_path),
            "-I",
            "-X",
            "utf8",
            str(worker_path),
            str(request_path),
        ]
        ProgressLogger.info(
            f"Cargando {engine_label} ({runtime.device}) en su propio proceso…"
        )
        try:
            exit_code = self._launcher(
                command,
                env=self._environment(runtime),
                cwd=workspace,
                log_path=log_path,
                on_line=self._line_handler(len(segments)),
            )
        except OSError as error:
            raise _backend_error(
                TtsBackendErrorKind.RESOURCE_UNAVAILABLE,
                f"no se pudo lanzar el proceso de {engine_label}: {error}",
            ) from error
        sample_rate = self._read_result(
            engine_label=engine_label,
            result_path=result_path,
            log_path=log_path,
            exit_code=exit_code,
        )
        return segment_paths, sample_rate

    def _environment(self, runtime: ExternalTtsRuntime) -> dict[str, str]:
        """Child environment: no downloads and every cache inside the project."""
        environment = dict(
            os.environ if self._base_environment is None else self._base_environment
        )
        cache = runtime.cache_dir
        environment.update(
            {
                "HF_HOME": str(cache / "huggingface"),
                "HF_HUB_OFFLINE": "1",
                "HF_HUB_DISABLE_TELEMETRY": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "TORCH_HOME": str(cache / "torch"),
                "XDG_CACHE_HOME": str(cache / "xdg"),
            }
        )
        return environment

    def _line_handler(self, total: int) -> Callable[[str], None]:
        def handle(line: str) -> None:
            parts = line.split()
            if len(parts) == 3 and parts[0] == PROGRESS_PREFIX:
                try:
                    done = int(parts[1])
                except ValueError:
                    return
                self._progress(done, total)

        return handle

    @staticmethod
    def _read_result(
        *,
        engine_label: str,
        result_path: Path,
        log_path: Path,
        exit_code: int,
    ) -> int:
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            result = None
        if not isinstance(result, Mapping):
            raise _backend_error(
                TtsBackendErrorKind.SYNTHESIS,
                f"el proceso de {engine_label} terminó (código {exit_code}) "
                f"sin dejar su resultado.{_log_tail(log_path)}",
            )

        if result.get("status") == "error":
            message = str(result.get("message") or "error sin detalle")
            if result.get("kind") == "configuration":
                raise TtsVoiceConfigurationError(f"{engine_label}: {message}")
            raise _backend_error(
                _RESULT_ERROR_KINDS.get(
                    result.get("kind"),
                    TtsBackendErrorKind.SYNTHESIS,
                ),
                f"{engine_label} falló: {message}",
            )

        sample_rate = result.get("sample_rate")
        if (
            result.get("status") != "ok"
            or exit_code != 0
            or isinstance(sample_rate, bool)
            or not isinstance(sample_rate, int)
            or sample_rate <= 0
        ):
            raise _backend_error(
                TtsBackendErrorKind.SYNTHESIS,
                f"el proceso de {engine_label} terminó (código {exit_code}) "
                f"con un resultado no válido.{_log_tail(log_path)}",
            )
        return sample_rate


def launch_worker_process(
    command: Sequence[str],
    *,
    env: Mapping[str, str],
    cwd: Path,
    log_path: Path,
    on_line: Callable[[str], None],
) -> int:
    """Run the worker without a time limit; stderr goes to its log file."""
    with log_path.open("w", encoding="utf-8", errors="replace") as log_file:
        process = subprocess.Popen(
            list(command),
            cwd=str(cwd),
            env=dict(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=log_file,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for line in process.stdout:
            on_line(line.rstrip("\n"))
            log_file.write(line)
        return process.wait()


def join_segment_wavs(
    *,
    segment_paths: Sequence[Path],
    segments: Sequence[SpeechSegment],
    output_path: Path,
    workspace: Path,
    sample_rate_hz: int,
) -> tuple[TtsPause, ...]:
    """Join 16-bit mono segment WAVs with each segment's pause after it.

    Returns where each written silence starts and ends, in seconds.
    """
    if len(segment_paths) != len(segments) or not segments:
        raise _backend_error(
            TtsBackendErrorKind.AUDIO_INVALID,
            "El número de audios de las frases no cuadra con el texto.",
        )
    workspace_root = Path(workspace).resolve(strict=False)
    pauses = []
    written_frames = 0
    try:
        with wave.open(str(output_path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(sample_rate_hz)
            for path, segment in zip(segment_paths, segments):
                frames = _read_segment_frames(path, workspace_root, sample_rate_hz)
                output.writeframes(frames)
                written_frames += len(frames) // 2
                pause_frames = round(segment.pause_after_seconds * sample_rate_hz)
                if pause_frames:
                    output.writeframes(bytes(pause_frames * 2))
                    pauses.append(
                        TtsPause(
                            start_seconds=written_frames / sample_rate_hz,
                            end_seconds=(written_frames + pause_frames)
                            / sample_rate_hz,
                        )
                    )
                    written_frames += pause_frames
    except TtsBackendError:
        raise
    except Exception as error:
        raise _backend_error(
            TtsBackendErrorKind.AUDIO_INVALID,
            "No se pudo unir el audio de las frases.",
        ) from error
    return tuple(pauses)


def _read_segment_frames(
    path: Path,
    workspace_root: Path,
    sample_rate_hz: int,
) -> bytes:
    resolved = Path(path).resolve(strict=False)
    if not resolved.is_relative_to(workspace_root) or not resolved.is_file():
        raise _backend_error(
            TtsBackendErrorKind.AUDIO_INVALID,
            f"Falta el audio de una frase: {Path(path).name}.",
        )
    with wave.open(str(resolved), "rb") as segment:
        if (
            segment.getcomptype() != "NONE"
            or segment.getsampwidth() != 2
            or segment.getnchannels() != 1
            or segment.getframerate() != sample_rate_hz
            or segment.getnframes() <= 0
        ):
            raise _backend_error(
                TtsBackendErrorKind.AUDIO_INVALID,
                f"El audio de una frase no es un WAV mono de 16 bits a "
                f"{sample_rate_hz} Hz: {Path(path).name}.",
            )
        return segment.readframes(segment.getnframes())


def _report_progress(done: int, total: int) -> None:
    ProgressLogger.info(f"  Parte {done} de {total}")


def _log_tail(log_path: Path) -> str:
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        line = line.strip()
        if line:
            return f" Última línea de su registro: «{line[:_LOG_LINE_LIMIT]}»."
    return ""


def _backend_error(kind: TtsBackendErrorKind, detail: str) -> TtsBackendError:
    return TtsBackendError(TtsBackendDiagnostic(kind=kind, detail=detail))
