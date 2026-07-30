import json
import re

from app.modules.script.models import (
    ScriptValidationIssue,
    ScriptValidationReport,
)


class ScriptOutputValidator:
    parser_id = "script_generation_contract_v1"

    def __init__(
        self,
        *,
        min_words: int = 3,
        max_words: int = 600,
        tolerance_ratio: float = 0.20,
    ) -> None:
        self.min_words = min_words
        self.max_words = max_words
        self.tolerance_ratio = tolerance_ratio

    def validate(
        self,
        script: str
    ) -> ScriptValidationReport:
        text = str(
            script
            or ""
        ).strip()
        issues = []

        if not text:
            return ScriptValidationReport(
                valid=False,
                issues=(
                    _issue(
                        "empty_script",
                        "script",
                    ),
                ),
            )

        try:
            text.encode(
                "utf-8"
            ).decode(
                "utf-8"
            )
        except UnicodeError:
            issues.append(
                _issue(
                    "invalid_utf8",
                    "script",
                )
            )

        word_count = count_script_words(
            text
        )
        effective_min_words = max(
            1,
            int(
                self.min_words
                * (
                    1
                    - self.tolerance_ratio
                )
            ),
        )
        effective_max_words = max(
            self.max_words,
            int(
                self.max_words
                * (
                    1
                    + self.tolerance_ratio
                )
            ),
        )
        if word_count < effective_min_words:
            issues.append(
                _issue(
                    "too_short",
                    "script",
                    str(
                        word_count
                    ),
                )
            )
        if word_count > effective_max_words:
            issues.append(
                _issue(
                    "too_long",
                    "script",
                    str(
                        word_count
                    ),
                )
            )

        for check in (
            self._markdown_issue,
            self._code_fence_issue,
            self._assistant_heading_issue,
            self._word_count_issue,
            self._model_comment_issue,
            self._json_issue,
            self._xml_issue,
        ):
            issue = check(
                text
            )
            if issue is not None:
                issues.append(
                    issue
                )

        return ScriptValidationReport(
            valid=not issues,
            issues=tuple(
                issues
            ),
        )

    def _markdown_issue(
        self,
        text: str
    ) -> ScriptValidationIssue | None:
        for line in text.splitlines():
            stripped = line.strip()
            if (
                stripped.startswith(
                    "#"
                )
                or stripped.startswith(
                    "- "
                )
                or stripped.startswith(
                    "* "
                )
                or stripped.startswith(
                    "> "
                )
                or "**" in stripped
                or "__" in stripped
            ):
                return _issue(
                    "markdown_not_allowed",
                    "script",
                    stripped,
                )
        return None

    def _code_fence_issue(
        self,
        text: str
    ) -> ScriptValidationIssue | None:
        if "```" in text:
            return _issue(
                "code_block_not_allowed",
                "script",
                "```",
            )
        return None

    def _assistant_heading_issue(
        self,
        text: str
    ) -> ScriptValidationIssue | None:
        headings = {
            "answer",
            "response",
            "output",
            "final answer",
        }
        for line in text.splitlines():
            label = line.strip().strip(
                "*_ "
            ).rstrip(
                ":"
            ).lower()
            if label in headings:
                return _issue(
                    "assistant_heading_not_allowed",
                    "script",
                    line.strip(),
                )
        return None

    def _word_count_issue(
        self,
        text: str
    ) -> ScriptValidationIssue | None:
        if re.search(
            r"\bword\s+count\b|\brecuento\s+de\s+palabras\b",
            text,
            flags=re.IGNORECASE,
        ):
            return _issue(
                "word_count_metadata_not_allowed",
                "script",
                "word count",
            )
        return None

    def _model_comment_issue(
        self,
        text: str
    ) -> ScriptValidationIssue | None:
        patterns = (
            r"\bthis response\b",
            r"\besta respuesta\b",
            r"\bas an ai\b",
            r"\bcomo modelo\b",
            r"\bhere is\b",
            r"\ba continuacion\b",
            r"\baqui tienes\b",
        )
        for pattern in patterns:
            if re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):
                return _issue(
                    "model_comment_not_allowed",
                    "script",
                    pattern,
                )
        return None

    def _json_issue(
        self,
        text: str
    ) -> ScriptValidationIssue | None:
        stripped = text.strip()
        if not (
            stripped.startswith(
                "{"
            )
            or stripped.startswith(
                "["
            )
        ):
            return None
        try:
            json.loads(
                stripped
            )
        except json.JSONDecodeError:
            return None
        return _issue(
            "json_not_allowed",
            "script",
            stripped[:40],
        )

    def _xml_issue(
        self,
        text: str
    ) -> ScriptValidationIssue | None:
        stripped = text.strip()
        if re.match(
            r"^<([A-Za-z][\w.-]*)(\s[^>]*)?>.*</\1>$",
            stripped,
            flags=re.DOTALL,
        ):
            return _issue(
                "xml_not_allowed",
                "script",
                stripped[:40],
            )
        return None


def count_script_words(
    text: str
) -> int:
    return len(
        re.findall(
            r"\b[\wÁÉÍÓÚÜÑáéíóúüñ]+\b",
            text,
        )
    )


def _issue(
    reason: str,
    field: str,
    value: str = "",
) -> ScriptValidationIssue:
    return ScriptValidationIssue(
        reason=reason,
        field=field,
        value=value,
    )
