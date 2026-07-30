import hashlib
import re
import time

from app.modules.script.models import (
    InvalidScriptOutputError,
    ScriptGenerationMetadata,
    ScriptGenerationResult,
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
                "El prompt del guion esta vacio."
            )

        prompt_id = _prompt_id(
            prompt
        )
        min_words, max_words = _word_range_from_prompt(
            prompt
        )
        validator = ScriptOutputValidator(
            min_words=min_words,
            max_words=max_words,
        )
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
                    min_words,
                    max_words,
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
            last_report = report

            if report.valid:
                return ScriptGenerationResult(
                    script=candidate,
                    word_count=count_script_words(
                        candidate
                    ),
                    metadata=ScriptGenerationMetadata(
                        model=self.model,
                        prompt_id=prompt_id,
                        parser_id=validator.parser_id,
                        attempt=attempt,
                        raw_response=last_response,
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
    min_words: int = 3,
    max_words: int = 600,
) -> str:
    if attempt <= 1:
        return prompt
    previous_reason = _previous_reason(
        previous_report
    )
    topic = _topic_from_prompt(
        prompt
    )
    return (
        "La respuesta anterior incumple el formato requerido. "
        f"Motivo: {previous_reason}. "
        f"Tema: {topic}. "
        f"El guion debe contener entre {min_words} y {max_words} palabras. "
        f"Objetivo exacto: {_target_words(min_words, max_words)} palabras. "
        "Devuelve unicamente el guion final valido, sin encabezados, "
        "sin comentarios, sin markdown, sin JSON y sin metadatos."
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


def _target_words(
    min_words: int,
    max_words: int,
) -> int:
    return int(
        round(
            (
                min_words
                + max_words
            )
            / 2
        )
    )


def _prompt_id(
    prompt: str
) -> str:
    return hashlib.sha256(
        prompt.encode(
            "utf-8"
        )
    ).hexdigest()


def _word_range_from_prompt(
    prompt: str
) -> tuple[int, int]:
    match = re.search(
        r"entre\s+(\d+)\s+y\s+(\d+)\s+palabras",
        prompt,
        flags=re.IGNORECASE,
    )
    if not match:
        return (
            3,
            600,
        )
    return (
        int(
            match.group(
                1
            )
        ),
        int(
            match.group(
                2
            )
        ),
    )
