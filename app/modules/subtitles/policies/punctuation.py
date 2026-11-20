from __future__ import annotations

from dataclasses import replace
from difflib import SequenceMatcher

import re
import unicodedata

from app.modules.subtitles.policies.timing import (
    SubtitleTiming,
    approximate_voiced_word_timings,
)
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
    """Restore canonical punctuation while preserving timed words.

    With ``authoritative``, ``content`` is the script and its words always
    replace the timed ones (``_script_aligned_timing``). Otherwise only the
    punctuation of ``content`` is restored, and only when its words are the
    timed words.
    """

    if not isinstance(timing, SubtitleTiming) or not timing.is_usable():
        return timing

    if authoritative:
        return _script_aligned_timing(content, timing)

    canonical_tokens = _canonical_tokens(content)
    timed_words = timing.words

    if len(canonical_tokens) != len(timed_words):
        return timing

    reconciled_text = []

    for canonical, timed in zip(canonical_tokens, timed_words):

        if _word_core(canonical) != _word_core(timed.text):
            return timing

        reconciled_text.append(
            _with_canonical_punctuation(
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

    return _word_tokens(raw_tokens)


def _word_tokens(raw_tokens):

    tokens = []
    prefix = ""

    for token in raw_tokens:
        if _word_core(token):
            tokens.append(prefix + token)
            prefix = ""
        elif tokens:
            # Timed-word sources may not emit a separate token for isolated marks.
            tokens[-1] += token
        else:
            prefix += token

    return tuple(tokens)


def _script_aligned_timing(script, timing):
    """Put the script's words on Whisper's word times.

    The script and the timed words are aligned word by word, ignoring case,
    accents and punctuation. Equal words, and replaced runs with as many
    words on both sides, keep each timed word's times with the script's text.
    A replaced run with a different number of words spreads the script words
    over its own time span in proportion to their letters, outside the voice
    pauses inside it (``approximate_voiced_word_timings``). Script words that
    were not heard join the previous run, or the next one when the previous
    word closes a sentence or a paragraph. Timed words that are not in the
    script are left out. An empty script leaves the timing unchanged.
    """

    tokens = script_tokens(script)

    if not tokens:
        return timing

    timed_words = timing.words
    segment_of = tuple(
        index
        for index, segment in enumerate(timing.segments)
        for _ in segment.words
    )
    matcher = SequenceMatcher(
        None,
        [_alignment_key(text) for text, _ in tokens],
        [_alignment_key(word.text) for word in timed_words],
        autojunk=False,
    )
    runs = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal" or i2 - i1 == j2 - j1:
            runs.extend(
                ([token], [word])
                for token, word in zip(range(i1, i2), range(j1, j2))
            )
        elif i1 < i2:
            runs.append(
                (list(range(i1, i2)), list(range(j1, j2)))
            )

    segment_words = [[] for _ in timing.segments]

    for token_indexes, word_indexes in _attach_unheard_words(runs, tokens):
        texts = [tokens[index][0] for index in token_indexes]
        words = [timed_words[index] for index in word_indexes]

        if len(texts) == len(words):
            aligned = [
                replace(word, text=text)
                for word, text in zip(words, texts)
            ]
        else:
            aligned = approximate_voiced_word_timings(
                words[0].start,
                words[-1].end,
                texts,
                timing.voice_pauses,
                [tokens[index][1] for index in token_indexes]
            )

        segment_words[segment_of[word_indexes[0]]].extend(aligned)

    return replace(
        timing,
        segments=tuple(
            replace(segment, words=tuple(words))
            for segment, words in zip(timing.segments, segment_words)
            if words
        )
    )


def script_word_timings(script, timing):
    """Return the script's words on Whisper's word times, in order.

    Each item is ``(WordTiming, closes)``: the word, with the script's text
    and the times ``_script_aligned_timing`` gives it, and whether it closes
    a sentence or a paragraph. Every script word is kept, heard or not.
    Without usable timing or script words the result is empty.
    """

    tokens = script_tokens(script)

    if (
        not tokens
        or not isinstance(timing, SubtitleTiming)
        or not timing.is_usable()
    ):
        return ()

    words = _script_aligned_timing(script, timing).words

    if len(words) != len(tokens):
        raise ValueError(
            "La alineación del guion con Whisper perdió palabras."
        )

    return tuple(
        (word, closes)
        for word, (_, closes) in zip(words, tokens)
    )


def _attach_unheard_words(runs, tokens):

    attached = []
    pending = []

    for token_indexes, word_indexes in runs:
        if word_indexes:
            attached.append((pending + token_indexes, word_indexes))
            pending = []
        elif attached and not tokens[attached[-1][0][-1]][1]:
            attached[-1][0].extend(token_indexes)
        else:
            pending.extend(token_indexes)

    if pending and attached:
        attached[-1][0].extend(pending)

    return attached


def script_tokens(script):
    """Return the script's words, each with whether it closes a sentence
    or a paragraph (one or more blank lines)."""

    tokens = []

    for paragraph in re.split(r"\n\s*\n", str(script).strip()):
        words = _word_tokens(paragraph.split())
        tokens.extend(
            (
                word,
                index == len(words) - 1
                or word.rstrip(_CLOSING_MARKS).endswith(_SENTENCE_ENDS)
            )
            for index, word in enumerate(words)
        )

    return tuple(tokens)


_SENTENCE_ENDS = (".", "?", "!", "…")
_CLOSING_MARKS = "\"'»”’)"


def _alignment_key(text):

    return "".join(
        character
        for character in unicodedata.normalize("NFD", _word_core(text))
        if not unicodedata.combining(character)
    )


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
