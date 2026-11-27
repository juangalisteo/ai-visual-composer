"""Estimated word times inside an SRT block that has no time per word (A1).

Without the voice (CONVERTIR, or a block that Whisper did not time), the time
of a block is shared among its words by their letters: a long word takes
longer to say than a short one. Sharing it equally put the words up to 1.1 s
away from the voice (PRUEBA-GS, fallo 7). These times are an estimate; exact
ones come from Whisper (TRANSCRIBIR or SOLO VIDEO).
"""


def letter_count(word) -> int:
    """Letters and digits of ``word`` (a text or an object with ``text``); at least 1."""
    text = word.text if hasattr(word, "text") else str(word)
    return max(1, sum(character.isalnum() for character in text))


def distribute_by_letters(start_ms, end_ms, words) -> tuple[tuple[int, int], ...]:
    """(start, end) in ms of each word; they follow each other and fill the block."""
    if not words:
        return ()
    weights = [letter_count(word) for word in words]
    total = sum(weights)
    duration = end_ms - start_ms
    bounds = [start_ms]
    reached = 0
    for weight in weights:
        reached += weight
        bounds.append(start_ms + round(duration * reached / total))
    return tuple(zip(bounds, bounds[1:]))
