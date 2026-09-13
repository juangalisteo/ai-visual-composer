from __future__ import annotations

from dataclasses import replace

import re
import unicodedata

from app.modules.subtitles.timing import SubtitleTiming
from app.shared.config_contract import require_bool, require_mapping


class PunctuationPolicy:

    _RULES = (
        ("remove_commas", ","),
        ("remove_periods", "."),
        ("remove_colons", ":"),
        ("remove_semicolons", ";"),
        ("remove_question_marks", "\u00bf?"),
        ("remove_exclamation_marks", "\u00a1!"),
        ("remove_ellipsis", "\u2026"),
        ("remove_hyphens", "-"),
        ("remove_em_dashes", "\u2014"),
        ("remove_double_quotes", "\"\u00ab\u00bb\u201c\u201d"),
        ("remove_single_quotes", "'\u2018\u2019"),
        ("remove_parentheses", "()"),
    )
    def __init__(self, config):

        policy = require_mapping(
            config,
            "punctuation",
            "cue_policy.punctuation",
        )

        self._removals = tuple(
            characters
            for field, characters in self._RULES
            if require_bool(
                policy,
                field,
                f"cue_policy.punctuation.{field}"
            )
        )

    def apply(self, text):

        for characters in self._removals:
            text = text.translate(
                str.maketrans("", "", characters)
            )

        return text


_RECONCILABLE_PUNCTUATION = frozenset(
    ",.:;\u00bf?\u00a1!\u2026-\u2014\"'\u00ab\u00bb\u201c\u201d\u2018\u2019()"
)


def reconcile_timing_text(content, timing, authoritative=False):
    """Restore canonical punctuation while preserving timed words."""

    if not isinstance(timing, SubtitleTiming) or not timing.is_usable():
        return timing

    canonical_tokens = _canonical_tokens(content)
    timed_words = timing.words

    if len(canonical_tokens) != len(timed_words):
        return timing

    reconciled_text = []

    for canonical, timed in zip(canonical_tokens, timed_words):

        if (
            not authoritative
            and _word_core(canonical) != _word_core(timed.text)
        ):
            return timing

        reconciled_text.append(
            canonical
            if authoritative
            else _with_canonical_punctuation(
                canonical=canonical,
                timed=timed.text
            )
        )

    cursor = 0
    segments = []

    for segment in timing.segments:

        count = len(segment.words)

        words = tuple(
            replace(
                word,
                text=reconciled_text[index]
            )
            for index, word in enumerate(
                segment.words,
                start=cursor
            )
        )

        segments.append(
            replace(
                segment,
                words=words
            )
        )

        cursor += count

    return replace(
        timing,
        segments=tuple(segments)
    )


def _canonical_tokens(content):

    raw_tokens = []

    for block in re.split(
        r"\n\s*\n",
        str(content).strip()
    ):

        lines = block.strip().splitlines()

        if len(lines) >= 3:
            raw_tokens.extend(
                " ".join(lines[2:]).split()
            )

    if not raw_tokens:
        raw_tokens = str(content).split()

    tokens = []
    prefix = ""

    for token in raw_tokens:
        if _word_core(token):
            tokens.append(prefix + token)
            prefix = ""
        elif tokens:
            # Edge does not emit a separate WordBoundary for isolated marks.
            tokens[-1] += token
        else:
            prefix += token

    return tuple(tokens)


def _with_canonical_punctuation(canonical, timed):

    prefix, _, suffix = _punctuation_parts(canonical)
    _, timed_core, _ = _punctuation_parts(timed)

    return f"{prefix}{timed_core}{suffix}"


def _word_core(text):

    _, core, _ = _punctuation_parts(text)

    return unicodedata.normalize(
        "NFC",
        core
    ).casefold()


def _punctuation_parts(text):

    text = str(text)

    start = 0
    end = len(text)

    while (
        start < end
        and text[start] in _RECONCILABLE_PUNCTUATION
    ):
        start += 1

    while (
        end > start
        and text[end - 1] in _RECONCILABLE_PUNCTUATION
    ):
        end -= 1

    return (
        text[:start],
        text[start:end],
        text[end:]
    )