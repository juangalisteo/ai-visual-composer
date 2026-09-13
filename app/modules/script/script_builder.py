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
from app.providers.ollama_provider import OllamaProvider
from app.shared.progress_logger import ProgressLogger


class ScriptBuilder:

    def __init__(
        self,
        ai_config,
        provider=None,
        max_attempts=2,
    ):
        self.model = ai_config[
            "model"
        ]
        self.provider = (
            provider
            or OllamaProvider(
                self.model
            )
        )
        self.max_attempts = max(
            1,
            int(
                max_attempts
            ),
        )

    def build(
        self,
        prompt
    ):
        ProgressLogger.start(
            "GENERANDO GUION"
        )

        start = time.perf_counter()

        result = self.generate_result(
            prompt
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
        prompt
    ) -> ScriptGenerationResult:
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
        length_reference = _length_reference_from_prompt(
            prompt
        )
        validator = ScriptOutputValidator()
        last_response = ""
        last_report = None

        for attempt in range(
            1,
            self.max_attempts + 1
        ):
            response = self.provider.generate(
                _attempt_prompt(
                    prompt,
                    attempt,
                    last_report,
                    length_reference,
                )
            )
            last_response = str(
                response
                or ""
            )
            candidate = last_response.strip()
            report = validator.validate(
                candidate
            )
            report = _validate_length(
                report=report,
                script=candidate,
                minimum=length_reference["recommended_min_words"],
                maximum=length_reference["recommended_max_words"],
            )
            last_report = report

            if report.valid:
                actual_words = count_script_words(
                    candidate
                )
                return ScriptGenerationResult(
                    script=candidate,
                    word_count=actual_words,
                    metadata=ScriptGenerationMetadata(
                        model=self.model,
                        prompt_id=prompt_id,
                        parser_id=validator.parser_id,
                        attempt=attempt,
                        raw_response=last_response,
                        target_words=(
                            length_reference[
                                "target_words"
                            ]
                        ),
                        recommended_min_words=(
                            length_reference[
                                "recommended_min_words"
                            ]
                        ),
                        recommended_max_words=(
                            length_reference[
                                "recommended_max_words"
                            ]
                        ),
                        actual_words=actual_words,
                        deviation_percentage=(
                            _deviation_percentage(
                                actual_words=actual_words,
                                target_words=length_reference[
                                    "target_words"
                                ],
                            )
                        ),
                    ),
                )

        first_issue = (
            last_report.issues[0]
            if last_report
            and last_report.issues
            else None
        )
        raise InvalidScriptOutputError(
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
            original_response=last_response,
            parser_id=validator.parser_id,
            model=self.model,
            prompt_id=prompt_id,
        )


def _attempt_prompt(
    prompt: str,
    attempt: int,
    previous_report=None,
    length_reference=None,
) -> str:
    if attempt <= 1:
        return prompt
    previous_reason = _previous_reason(
        previous_report
    )
    topic = _topic_from_prompt(
        prompt
    )
    length_reference = length_reference or {}
    minimum = int(length_reference.get("recommended_min_words", 0) or 0)
    maximum = int(length_reference.get("recommended_max_words", 0) or 0)
    length_instruction = ""
    if minimum > 0 and maximum >= minimum:
        length_instruction = (
            f" Debe contener entre {minimum} y {maximum} palabras "
            "para respetar la duración solicitada."
        )
    return (
        "La respuesta anterior incumple el formato requerido. "
        f"Motivo: {previous_reason}. "
        f"Tema: {topic}. "
        "Devuelve únicamente el guion final válido, sin encabezados, "
        "sin comentarios, sin markdown, sin JSON y sin metadatos."
        + length_instruction
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


def _validate_length(*, report, script, minimum, maximum):
    """Enforce the duration-derived word range without truncating content."""
    if not report.valid or minimum <= 0 or maximum <= 0:
        return report

    word_count = count_script_words(script)
    if minimum <= word_count <= maximum:
        return report

    reason = (
        "script_too_short_for_duration"
        if word_count < minimum
        else "script_too_long_for_duration"
    )
    return ScriptValidationReport(
        valid=False,
        issues=(
            ScriptValidationIssue(
                reason=reason,
                field="script",
                value=str(word_count),
            ),
        ),
    )


def _topic_from_prompt(
    prompt: str
) -> str:
    lines = prompt.splitlines()
    for index, line in enumerate(
        lines
    ):
        if line.strip().lower().rstrip(":") == "tema":
            for candidate in lines[
                index + 1:
            ]:
                candidate = candidate.strip()
                if candidate:
                    return candidate
    return "tema solicitado"


def _prompt_id(
    prompt: str
) -> str:
    return hashlib.sha256(
        prompt.encode(
            "utf-8"
        )
    ).hexdigest()


def _length_reference_from_prompt(
    prompt: str
) -> dict:
    recommended_min_words = _extract_number_after(
        prompt,
        "aproximadamente entre"
    )
    recommended_max_words = _extract_number_after_y(
        prompt
    )
    target_words = _extract_number_after(
        prompt,
        "objetivo aproximado de"
    )

    if (
        target_words <= 0
        and recommended_min_words > 0
        and recommended_max_words > 0
    ):
        target_words = int(
            round(
                (
                    recommended_min_words
                    + recommended_max_words
                )
                / 2
            )
        )

    return {
        "target_words": target_words,
        "recommended_min_words": recommended_min_words,
        "recommended_max_words": recommended_max_words,
    }


def _extract_number_after(
    text: str,
    marker: str
) -> int:
    lower_text = text.lower()
    marker_index = lower_text.find(
        marker
    )
    if marker_index < 0:
        return 0

    suffix = lower_text[
        marker_index + len(marker):
    ]
    return _leading_number(
        suffix
    )


def _extract_number_after_y(
    text: str
) -> int:
    lower_text = text.lower()
    marker = "aproximadamente entre"
    marker_index = lower_text.find(
        marker
    )
    if marker_index < 0:
        return 0

    suffix = lower_text[
        marker_index + len(marker):
    ]
    if " y " not in suffix:
        return 0

    return _leading_number(
        suffix.split(
            " y ",
            1
        )[1]
    )


def _leading_number(
    text: str
) -> int:
    digits = ""

    for character in text:
        if character.isdigit():
            digits += character
            continue
        if digits:
            break

    return int(
        digits
        or 0
    )


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
