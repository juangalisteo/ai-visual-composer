import hashlib
import time

from app.modules.script.models import (
    InvalidScriptOutputError,
    ScriptGenerationMetadata,
    ScriptGenerationResult,
    ScriptValidationIssue,
    ScriptValidationReport,
)
from app.modules.script.validator import (
    ScriptOutputValidator,
    count_script_words,
)
from app.providers.ollama_provider import (
    OllamaProvider,
    OllamaRequestPolicy,
)
from app.providers.ollama_settings import ollama_call_settings
from app.shared.progress_logger import ProgressLogger


# Section of config/ai.json with the script's model, think and options.
SCRIPT_AI_TASK = "script"


class ScriptBuilder:

    def __init__(
        self,
        ai_config,
        provider=None,
        max_attempts=2,
    ):
        settings = ollama_call_settings(
            ai_config,
            SCRIPT_AI_TASK,
        )
        self.model = settings.model
        self.provider = (
            provider
            or OllamaProvider.from_settings(
                settings
            )
        )
        # Only what config/ai.json declares travels with each call; with
        # nothing declared the request stays the historical free-text one.
        self._call_options = (
            {}
            if settings.think is None and settings.options is None
            else {
                "policy": OllamaRequestPolicy(
                    think=settings.think,
                    options=settings.options,
                )
            }
        )
        self.max_attempts = max(
            1,
            int(
                max_attempts
            ),
        )

    def build(
        self,
        prompt,
        *,
        length=None,
    ):
        ProgressLogger.start(
            "GENERANDO GUION"
        )

        start = time.perf_counter()

        result = self.generate_result(
            prompt,
            length=length,
        )

        elapsed = (
            time.perf_counter()
            - start
        )

        ProgressLogger.finish(
            "Finalizado",
            elapsed
        )

        return result.script

    def generate_result(
        self,
        prompt,
        *,
        length=None,
    ) -> ScriptGenerationResult:
        """Generate one script.

        ``length`` is the ``ScriptLengthBudget`` the prompt was written with,
        passed as data; ``None`` means free text without a length check.
        When every attempt is well formed but out of range, the closest one
        is returned instead of failing.
        """
        prompt = str(
            prompt
            or ""
        ).strip()

        if not prompt:
            raise ValueError(
                "El prompt del guion está vacío."
            )

        prompt_id = _prompt_id(
            prompt
        )
        validator = ScriptOutputValidator()
        last_response = ""
        last_report = None
        previous_script = ""
        closest = None

        for attempt in range(
            1,
            self.max_attempts + 1
        ):
            response = self.provider.generate(
                _attempt_prompt(
                    prompt,
                    attempt,
                    last_report,
                    length,
                    previous_script,
                ),
                **self._call_options,
            )
            last_response = str(
                response
                or ""
            )
            candidate = last_response.strip()
            report = validator.validate(
                candidate
            )
            if report.valid:
                result = self._result(
                    script=candidate,
                    attempt=attempt,
                    raw_response=last_response,
                    prompt_id=prompt_id,
                    parser_id=validator.parser_id,
                    length=length,
                )
                report = _validate_length(
                    report=report,
                    script=candidate,
                    length=length,
                )
                if report.valid:
                    return result
                if closest is None or _distance(
                    length, candidate
                ) < _distance(length, closest.script):
                    closest = result
                previous_script = candidate
                if attempt < self.max_attempts:
                    ProgressLogger.info(
                        f"El guion tiene {result.word_count} palabras: "
                        "leído duraría unos "
                        f"{_seconds(length.estimate_seconds(candidate))} s "
                        f"y se piden {_seconds(length.duration_seconds)} s. "
                        "Se pide a Ollama que lo ajuste."
                    )
            last_report = report

        if closest is not None:
            return closest

        raise self._invalid_output(
            report=last_report,
            response=last_response,
            parser_id=validator.parser_id,
            prompt_id=prompt_id,
        )

    def adjust(
        self,
        prompt,
        *,
        length,
        previous_script,
        measured_seconds,
    ):
        """Ask once for ``previous_script`` rewritten to fit ``length``.

        ``measured_seconds`` is how long the voice really took to read it.
        There is exactly one request: a malformed answer raises
        ``InvalidScriptOutputError`` and the caller keeps the first script.
        """
        ProgressLogger.start(
            "AJUSTANDO GUION"
        )
        start = time.perf_counter()
        prompt = str(
            prompt
            or ""
        ).strip()
        if not prompt:
            raise ValueError(
                "El prompt del guion está vacío."
            )
        validator = ScriptOutputValidator()
        response = str(
            self.provider.generate(
                _length_correction_prompt(
                    prompt,
                    length=length,
                    previous_script=str(previous_script).strip(),
                    measured_seconds=measured_seconds,
                ),
                **self._call_options,
            )
            or ""
        )
        candidate = response.strip()
        report = validator.validate(
            candidate
        )
        if not report.valid:
            raise self._invalid_output(
                report=report,
                response=response,
                parser_id=validator.parser_id,
                prompt_id=_prompt_id(prompt),
            )
        ProgressLogger.finish(
            "Finalizado",
            time.perf_counter() - start
        )
        return candidate

    def _invalid_output(
        self,
        *,
        report,
        response,
        parser_id,
        prompt_id,
    ) -> InvalidScriptOutputError:
        first_issue = (
            report.issues[0]
            if report
            and report.issues
            else None
        )
        return InvalidScriptOutputError(
            reason=(
                first_issue.reason
                if first_issue
                else "unknown_validation_failure"
            ),
            field=(
                first_issue.field
                if first_issue
                else "script"
            ),
            original_response=response,
            parser_id=parser_id,
            model=self.model,
            prompt_id=prompt_id,
        )

    def _result(
        self,
        *,
        script,
        attempt,
        raw_response,
        prompt_id,
        parser_id,
        length,
    ) -> ScriptGenerationResult:
        actual_words = count_script_words(
            script
        )
        target_words = length.target_words if length else 0
        return ScriptGenerationResult(
            script=script,
            word_count=actual_words,
            metadata=ScriptGenerationMetadata(
                model=self.model,
                prompt_id=prompt_id,
                parser_id=parser_id,
                attempt=attempt,
                raw_response=raw_response,
                target_words=target_words,
                recommended_min_words=(
                    length.min_words if length else 0
                ),
                recommended_max_words=(
                    length.max_words if length else 0
                ),
                actual_words=actual_words,
                deviation_percentage=_deviation_percentage(
                    actual_words=actual_words,
                    target_words=target_words,
                ),
            ),
        )


_LENGTH_REASONS = frozenset(
    {
        "script_too_short_for_duration",
        "script_too_long_for_duration",
    }
)


def _attempt_prompt(
    prompt: str,
    attempt: int,
    previous_report=None,
    length=None,
    previous_script: str = "",
) -> str:
    """Prompt of one attempt: the original prompt plus, on retries, a correction."""
    if attempt <= 1:
        return prompt
    previous_reason = _previous_reason(
        previous_report
    )
    if (
        previous_reason in _LENGTH_REASONS
        and length is not None
        and previous_script
    ):
        return _length_correction_prompt(
            prompt,
            length=length,
            previous_script=previous_script,
        )
    length_instruction = ""
    if length is not None:
        length_instruction = (
            f"\n- Debe contener entre {length.min_words} y "
            f"{length.max_words} palabras para respetar la duración "
            "solicitada."
        )
    return (
        f"{prompt}\n\n"
        "CORRECCIÓN:\n"
        "- La respuesta anterior incumple el formato requerido. "
        f"Motivo: {previous_reason}.\n"
        "- Devuelve únicamente el guion final válido, sin encabezados, "
        "sin comentarios, sin markdown, sin JSON y sin metadatos."
        + length_instruction
    )


def _length_correction_prompt(
    prompt: str,
    *,
    length,
    previous_script: str,
    measured_seconds=None,
) -> str:
    """Original prompt, the previous script and then a strict word limit.

    The limit is rescaled by what that very script lasted: measured by the
    voice when ``measured_seconds`` is given, estimated in letters otherwise.
    Measured with qwen3:14b (I1): with the script last, Ollama copied it back;
    with a range it removed about half of what was asked. The script first and
    a strict maximum (or minimum) at the end is what it follows best.
    """
    words = count_script_words(
        previous_script
    )
    if measured_seconds is None:
        observed_seconds = length.estimate_seconds(
            previous_script
        )
        observation = (
            f"- Leído en voz alta, el guion anterior ({words} palabras) "
            f"duraría unos {_seconds(observed_seconds)} segundos y debe "
            f"durar {_seconds(length.duration_seconds)}.\n"
        )
    else:
        observed_seconds = float(measured_seconds)
        observation = (
            f"- La voz leyó el guion anterior ({words} palabras) en "
            f"{_seconds(observed_seconds)} segundos y debe durar "
            f"{_seconds(length.duration_seconds)}.\n"
        )
    rewrite = length.rescaled(
        words=words,
        observed_seconds=observed_seconds,
    )
    limit = (
        "como máximo"
        if observed_seconds > length.duration_seconds
        else "como mínimo"
    )
    return (
        f"{prompt}\n\n"
        "GUION ANTERIOR:\n"
        f"{previous_script}\n\n"
        "CORRECCIÓN DE EXTENSIÓN:\n"
        f"{observation}"
        f"- Reescríbelo con {rewrite.target_words} palabras {limit}; es un "
        "límite estricto que sustituye a la extensión indicada en "
        "DURACIÓN.\n"
        "- Conserva el tono, la idea principal y el cierre. Devuelve "
        "únicamente el guion reescrito."
    )


def _previous_reason(
    previous_report
) -> str:
    if (
        previous_report is None
        or not previous_report.issues
    ):
        return "formato invalido"
    return previous_report.issues[0].reason


def _validate_length(*, report, script, length):
    """Enforce the budget's duration, estimated in letters, without truncating."""
    if not report.valid or length is None:
        return report

    estimated_seconds = length.estimate_seconds(
        script
    )
    if length.fits(estimated_seconds):
        return report

    reason = (
        "script_too_short_for_duration"
        if estimated_seconds < length.duration_seconds
        else "script_too_long_for_duration"
    )
    return ScriptValidationReport(
        valid=False,
        issues=(
            ScriptValidationIssue(
                reason=reason,
                field="script",
                value=_seconds(estimated_seconds),
            ),
        ),
    )


def _distance(length, script) -> float:
    """How far ``script`` is estimated to be from the requested duration."""
    return abs(
        length.deviation(
            length.estimate_seconds(
                script
            )
        )
    )


def _seconds(value) -> str:
    """Seconds for the terminal and prompts, with a decimal comma."""
    return f"{float(value):.1f}".replace(".", ",")


def _prompt_id(
    prompt: str
) -> str:
    return hashlib.sha256(
        prompt.encode(
            "utf-8"
        )
    ).hexdigest()


def _deviation_percentage(
    *,
    actual_words: int,
    target_words: int,
) -> float:
    if target_words <= 0:
        return 0.0

    return (
        (
            actual_words
            - target_words
        )
        / target_words
    ) * 100
