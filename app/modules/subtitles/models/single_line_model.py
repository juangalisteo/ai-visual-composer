import math
import re
from functools import lru_cache

from app.modules.subtitles.models.base_subtitle_model import BaseSubtitleModel
from app.modules.subtitles.punctuation import PunctuationPolicy
from app.shared.config_contract import require_float, require_int


class SingleLineModel(BaseSubtitleModel):

    WEAK_STARTS = {
        "a", "al", "ante", "bajo", "con", "contra",
        "de", "del", "desde", "durante", "en", "entre",
        "hacia", "hasta", "mediante", "para", "por",
        "según", "sin", "sobre", "tras",
        "y", "e", "o", "u",
        "el", "la", "los", "las",
        "un", "una", "unos", "unas",
        "que"
    }

    WEAK_ENDS = {
        "a", "ante", "bajo", "con", "contra",
        "de", "desde", "durante", "en", "entre",
        "hacia", "hasta", "mediante", "para", "por",
        "según", "sin", "sobre", "tras",
        "y", "e", "o", "u",
        "que"
    }

    NATURAL_ENDINGS = {
        "a la", "a las", "a los", "al",
        "de la", "de las", "de los", "del",
        "en la", "en las", "en los", "en el",
        "para la", "para las", "para los", "para el",
        "por la", "por las", "por los", "por el",
        "con la", "con las", "con los", "con el"
    }

    def __init__(self, config):
        self.punctuation = PunctuationPolicy(config)
        self.max_chars_per_line = require_int(
            config,
            "max_chars_per_line",
            "cue_policy.max_chars_per_line"
        )

        self.min_duration = require_float(
            config,
            "min_duration",
            "cue_policy.min_duration"
        )

        self.max_duration = require_float(
            config,
            "max_duration",
            "cue_policy.max_duration"
        )

        self.significant_gap_threshold = require_float(
            config,
            "significant_gap_threshold",
            "cue_policy.significant_gap_threshold"
        )

        if self.max_chars_per_line <= 0:
            raise ValueError(
                "cue_policy.max_chars_per_line debe ser "
                "superior a cero."
            )
        if self.min_duration <= 0 or self.max_duration <= 0:
            raise ValueError(
                "Las duraciones de cue_policy deben ser "
                "superiores a cero."
            )
        if self.max_duration < self.min_duration:
            raise ValueError(
                "cue_policy.max_duration no puede ser menor "
                "que cue_policy.min_duration."
            )
        if self.significant_gap_threshold <= 0:
            raise ValueError(
                "cue_policy.significant_gap_threshold debe ser "
                "superior a cero."
            )

    def optimize(self, blocks, timing=None):
        if timing is not None and timing.is_usable():
            optimized_blocks = self._optimize_with_timing(
                timing
            )

            if optimized_blocks:
                return optimized_blocks

        optimized_blocks = []
        new_index = 1

        for block in blocks:
            parsed = self._parse_block(block)

            if not parsed:
                continue

            start_ms, end_ms, text = parsed
            duration_ms = end_ms - start_ms

            if duration_ms <= 0:
                continue

            chunks = self._split_text_by_sense(text)
            chunks = self._avoid_orphan_words(chunks)

            time_ranges = self._distribute_time_by_text_length(
                start_ms=start_ms,
                end_ms=end_ms,
                chunks=chunks
            )

            for chunk, (chunk_start, chunk_end) in zip(
                chunks,
                time_ranges
            ):
                optimized_blocks.append(
                    f"{new_index}\n"
                    f"{self._ms_to_time(chunk_start)} --> "
                    f"{self._ms_to_time(chunk_end)}\n"
                    f"{self.punctuation.apply(chunk)}"
                )

                new_index += 1

        return optimized_blocks

    def _optimize_with_timing(self, timing):
        optimized_blocks = []
        new_index = 1

        for segment in timing.segments:
            for word_group in self._split_words_by_gap(
                segment.words
            ):
                chunks = self._split_timed_words_by_sense(
                    word_group
                )

                for chunk_words in chunks:
                    text = self.punctuation.apply(
                        self._clean_text(
                            " ".join(
                                word.text
                                for word in chunk_words
                            )
                        )
                    )

                    if not text:
                        continue

                    optimized_blocks.append(
                        f"{new_index}\n"
                        f"{self._seconds_to_time(chunk_words[0].start)} --> "
                        f"{self._seconds_to_time(chunk_words[-1].end)}\n"
                        f"{text}"
                    )

                    new_index += 1

        return optimized_blocks

    def _split_words_by_gap(self, words):
        groups = []
        current_group = []

        for word in words:
            if (
                current_group
                and word.start - current_group[-1].end
                >= self.significant_gap_threshold
            ):
                groups.append(
                    tuple(
                        current_group
                    )
                )
                current_group = []

            if word.end > word.start:
                current_group.append(
                    word
                )

        if current_group:
            groups.append(
                tuple(
                    current_group
                )
            )

        return groups

    def _split_timed_words_by_sense(self, words):
        text = self._clean_text(
            " ".join(
                word.text
                for word in words
            )
        )

        if not text:
            return []

        chunks = self._split_text_by_sense(
            text
        )
        chunks = self._avoid_orphan_words(
            chunks
        )

        timed_chunks = []
        cursor = 0

        for chunk in chunks:
            word_count = len(
                chunk.split()
            )

            if word_count <= 0:
                continue

            chunk_words = tuple(
                words[cursor:cursor + word_count]
            )

            if chunk_words:
                timed_chunks.append(
                    chunk_words
                )

            cursor += word_count

        if cursor < len(words):
            remaining = tuple(
                words[cursor:]
            )

            if remaining:
                timed_chunks.append(
                    remaining
                )

        return timed_chunks

    def _split_text_by_sense(self, text):
        text = self._clean_text(text)

        if not text:
            return []

        if len(text) <= self.max_chars_per_line:
            return [text]

        return self._find_best_segmentation(text)

    def _find_best_segmentation(self, text):
        words = text.split()

        if not words:
            return []

        minimum_chunks = max(
            1,
            math.ceil(
                len(text) / self.max_chars_per_line
            )
        )

        maximum_chunks = min(
            len(words),
            minimum_chunks + 2
        )

        best_chunks = None
        best_score = float("inf")

        for chunk_count in range(
            minimum_chunks,
            maximum_chunks + 1
        ):
            result = self._optimize_for_chunk_count(
                words=words,
                chunk_count=chunk_count
            )

            if result is None:
                continue

            score, chunks = result

            # Se favorece usar el menor número posible de bloques,
            # salvo que añadir uno mejore claramente la lectura.
            extra_chunks = chunk_count - minimum_chunks
            score += extra_chunks * 8

            if score < best_score:
                best_score = score
                best_chunks = chunks

        if best_chunks:
            return best_chunks

        return self._fallback_split(words)

    def _optimize_for_chunk_count(
        self,
        words,
        chunk_count
    ):
        total_characters = len(
            " ".join(words)
        )

        target_length = (
            total_characters / chunk_count
        )

        @lru_cache(maxsize=None)
        def solve(start_index, remaining_chunks):
            remaining_words = len(words) - start_index

            if remaining_words < remaining_chunks:
                return None

            if remaining_chunks == 1:
                final_chunk = " ".join(
                    words[start_index:]
                )

                if (
                    not final_chunk
                    or len(final_chunk)
                    > self.max_chars_per_line
                ):
                    return None

                score = self._score_chunk(
                    chunk=final_chunk,
                    next_chunk=None,
                    target_length=target_length,
                    is_last=True
                )

                return score, [final_chunk]

            best_result = None
            best_score = float("inf")

            maximum_end = (
                len(words)
                - remaining_chunks
                + 1
            )

            for end_index in range(
                start_index + 1,
                maximum_end + 1
            ):
                chunk = " ".join(
                    words[start_index:end_index]
                )

                if len(chunk) > self.max_chars_per_line:
                    break

                next_word = words[end_index]

                following_result = solve(
                    end_index,
                    remaining_chunks - 1
                )

                if following_result is None:
                    continue

                following_score, following_chunks = (
                    following_result
                )

                next_chunk_preview = next_word

                local_score = self._score_chunk(
                    chunk=chunk,
                    next_chunk=next_chunk_preview,
                    target_length=target_length,
                    is_last=False
                )

                total_score = (
                    local_score
                    + following_score
                )

                if total_score < best_score:
                    best_score = total_score
                    best_result = (
                        total_score,
                        [chunk] + following_chunks
                    )

            return best_result

        return solve(0, chunk_count)

    def _score_chunk(
        self,
        chunk,
        next_chunk,
        target_length,
        is_last
    ):
        words = chunk.split()

        if not words:
            return float("inf")

        chunk_length = len(chunk)

        # Equilibrio general respecto a la longitud ideal.
        difference = abs(
            chunk_length - target_length
        )

        score = difference * 1.15

        score += (
            difference * difference
            / max(1, target_length)
        ) * 0.65

        minimum_desirable_length = max(
            12,
            int(self.max_chars_per_line * 0.38)
        )

        # Penalización fuerte para líneas excesivamente cortas.
        if chunk_length < minimum_desirable_length:
            score += (
                minimum_desirable_length
                - chunk_length
            ) * 2.2

        if len(words) == 1:
            score += 45

        if len(words) == 2:
            score += 10

        if not is_last:
            score += self._score_boundary(
                chunk=chunk,
                next_chunk=next_chunk
            )

        return score

    def _score_boundary(
        self,
        chunk,
        next_chunk
    ):
        score = 0

        stripped_chunk = chunk.strip()

        normalized_chunk = stripped_chunk.lower().rstrip(
            "¿¡.,;:!?"
        )

        last_word = (
            stripped_chunk
            .split()[-1]
            .lower()
            .strip("¿¡.,;:!?")
        )

        next_word = ""

        if next_chunk:
            next_word = (
                next_chunk
                .split()[0]
                .lower()
                .strip("¿¡.,;:!?")
            )

        # Prioridad de los cortes naturales.
        if re.search(r"[.!?]$", stripped_chunk):
            score -= 22

        elif re.search(r"[;:]$", stripped_chunk):
            score -= 16

        elif re.search(r",$", stripped_chunk):
            score -= 13

        # No se castigan expresiones naturales como:
        # "a la", "de la", "en el", "para los"...
        if any(
            normalized_chunk.endswith(ending)
            for ending in self.NATURAL_ENDINGS
        ):
            score -= 3

        elif last_word in self.WEAK_ENDS:
            score += 13

        # Empezar con artículo o preposición no es incorrecto,
        # pero se penaliza ligeramente cuando existe otra opción.
        if next_word in self.WEAK_STARTS:
            score += 4

        # Se penalizan cortes que separen negaciones.
        if last_word in {
            "no",
            "ni",
            "nunca",
            "jamás"
        }:
            score += 18

        # Se penalizan cortes justo después de auxiliares
        # o verbos copulativos frecuentes.
        if last_word in {
            "es", "son", "era", "eran",
            "está", "están", "fue", "fueron",
            "ha", "han", "he", "hemos",
            "puede", "pueden", "debe", "deben"
        }:
            score += 12

        return score

    def _fallback_split(self, words):
        chunks = []
        current = ""

        for word in words:
            candidate = f"{current} {word}".strip()

            if len(candidate) <= self.max_chars_per_line:
                current = candidate
            else:
                if current:
                    chunks.append(current)

                current = word

        if current:
            chunks.append(current)

        return chunks

    def _avoid_orphan_words(self, chunks):
        if len(chunks) <= 1:
            return chunks

        fixed = chunks.copy()

        if len(fixed[-1].split()) != 1:
            return fixed

        orphan = fixed[-1]
        previous = fixed[-2]

        candidate = f"{previous} {orphan}".strip()

        if len(candidate) <= self.max_chars_per_line:
            fixed[-2] = candidate
            fixed.pop()

        return fixed

    def _distribute_time_by_text_length(
        self,
        start_ms,
        end_ms,
        chunks
    ):
        duration_ms = end_ms - start_ms

        if not chunks:
            return []

        if len(chunks) == 1:
            return [
                (
                    start_ms,
                    end_ms
                )
            ]

        weights = [
            max(
                1,
                len(chunk)
            )
            for chunk in chunks
        ]

        total_weight = sum(
            weights
        )

        min_ms = int(
            self.min_duration * 1000
        )

        max_ms = int(
            self.max_duration * 1000
        )

        durations = []

        for weight in weights:
            chunk_duration = int(
                duration_ms
                * (
                    weight
                    / total_weight
                )
            )

            chunk_duration = max(
                min_ms,
                chunk_duration
            )

            chunk_duration = min(
                max_ms,
                chunk_duration
            )

            durations.append(
                chunk_duration
            )

        total_duration = sum(
            durations
        )

        if total_duration != duration_ms:
            factor = (
                duration_ms
                / total_duration
            )

            durations = [
                int(
                    duration
                    * factor
                )
                for duration in durations
            ]

        diff = (
            duration_ms
            - sum(durations)
        )

        if durations:
            durations[-1] += diff

        ranges = []
        current_start = start_ms

        for duration in durations:
            current_end = (
                current_start
                + duration
            )

            if current_end > end_ms:
                current_end = end_ms

            ranges.append(
                (
                    current_start,
                    current_end
                )
            )

            current_start = current_end

        if ranges:
            ranges[-1] = (
                ranges[-1][0],
                end_ms
            )

        return ranges

    def _parse_block(self, block):
        lines = block.strip().splitlines()

        if len(lines) < 3:
            return None

        timestamp = lines[1].strip()

        text = self._clean_text(
            " ".join(
                lines[2:]
            )
        )

        match = re.match(
            r"(\d{2}:\d{2}:\d{2},\d{3})"
            r"\s*-->\s*"
            r"(\d{2}:\d{2}:\d{2},\d{3})",
            timestamp
        )

        if not match:
            return None

        start_ms = self._time_to_ms(
            match.group(1)
        )

        end_ms = self._time_to_ms(
            match.group(2)
        )

        return (
            start_ms,
            end_ms,
            text
        )

    def _clean_text(self, text):
        return " ".join(
            text.split()
        ).strip()

    def _time_to_ms(self, time_text):
        hours, minutes, rest = (
            time_text.split(":")
        )

        seconds, milliseconds = (
            rest.split(",")
        )

        return (
            int(hours) * 3600000
            + int(minutes) * 60000
            + int(seconds) * 1000
            + int(milliseconds)
        )

    def _ms_to_time(self, total_ms):
        total_ms = max(
            0,
            int(total_ms)
        )

        hours = total_ms // 3600000
        total_ms %= 3600000

        minutes = total_ms // 60000
        total_ms %= 60000

        seconds = total_ms // 1000
        milliseconds = total_ms % 1000

        return (
            f"{hours:02}:"
            f"{minutes:02}:"
            f"{seconds:02},"
            f"{milliseconds:03}"
        )

    def _seconds_to_time(self, seconds):
        return self._ms_to_time(
            round(
                float(seconds)
                * 1000
            )
        )
