import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.modules.subtitles.pipeline.cue_transformer import SubtitleCueTransformer
from app.modules.subtitles.policies.punctuation import (
    PunctuationPolicy,
    reconcile_timing_text,
    script_word_timings,
)
from app.modules.subtitles.policies.timing import SpeechSegment, SubtitleTiming, WordTiming
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


class SubtitlePunctuationTest(unittest.TestCase):

    SOURCE_TEXT = (
        "Durante siglos hemos buscado respuestas fuera de nosotros en libros, "
        "maestros, religiones, ideolog\u00edas y sistemas. Pero quiz\u00e1 hemos olvidado "
        "hacer la pregunta m\u00e1s importante: \u00bfqu\u00e9 ocurre cuando dejamos de buscar "
        "fuera y empezamos a observar dentro? \u00a1Esto es importante! \"Texto citado\"; "
        "l'arte anti-ruido \u2014solo quiz\u00e1\u2014 funcione\u2026 (correctamente)."
    )
    PUNCTUATION = {
        "remove_commas": False,
        "remove_periods": False,
        "remove_colons": False,
        "remove_semicolons": False,
        "remove_question_marks": False,
        "remove_exclamation_marks": False,
        "remove_ellipsis": False,
        "remove_hyphens": False,
        "remove_em_dashes": False,
        "remove_double_quotes": False,
        "remove_single_quotes": False,
        "remove_parentheses": False,
    }

    def test_single_line_restores_canonical_punctuation_from_tts_and_whisper(self):
        for source in ("tts", "whisper"):
            with self.subTest(source=source):
                rendered = self._transform("single_line", timing=self._timing(source))
                text = self._cue_text(rendered)
                self.assertEqual(self.SOURCE_TEXT, text)
                self.assertIn(
                    "libros, maestros, religiones, ideolog\u00edas y sistemas.", text
                )
                self.assertIn("m\u00e1s importante: \u00bfqu\u00e9 ocurre", text)
                self.assertIn("00:00:00,000 -->", rendered)

    def test_single_line_fallback_preserves_all_punctuation(self):
        rendered = self._transform("single_line")
        self.assertEqual(self.SOURCE_TEXT, self._cue_text(rendered))

    def test_word_by_word_preserves_every_sign_except_comma_and_period(self):
        policy = {**self.PUNCTUATION, "remove_commas": True, "remove_periods": True}
        for timing in (self._timing("tts"), None):
            with self.subTest(timing=timing is not None):
                text = self._cue_text(
                    self._transform("word_by_word", timing=timing, punctuation=policy)
                )
                self.assertNotIn(",", text)
                self.assertNotIn(".", text)
                for sign in (
                    ":", ";", "\u00bf", "?", "\u00a1", "!", "\u2026", "-", "\u2014", '"', "'", "(", ")"
                ):
                    self.assertIn(sign, text)

    def test_word_by_word_preserves_exclamation_marks_with_timing_and_fallback(self):
        expected = {
            "\u00a1Hola": "\u00a1Hola",
            "Hola!": "Hola!",
            "\u00a1Hola!": "\u00a1Hola!",
            "\u00bfHola?": "\u00bfHola?",
            "\u00a1\u00bfHola?!": "\u00a1\u00bfHola?!",
            "palabra normal": "palabra normal",
            "Hola,": "Hola",
            "Hola.": "Hola",
        }
        for use_timing in (True, False):
            for source, rendered_text in expected.items():
                with self.subTest(source=source, timing=use_timing):
                    rendered = self._transform_phrase(
                        source,
                        timing=self._phrase_timing(source) if use_timing else None,
                    )
                    self.assertEqual(rendered_text, self._cue_text(rendered))

    def test_word_by_word_removes_only_exclamation_marks_when_enabled(self):
        policy = {**self.PUNCTUATION, "remove_commas": True, "remove_periods": True, "remove_exclamation_marks": True}
        expected = {
            "\u00a1Hola": "Hola",
            "Hola!": "Hola",
            "\u00a1Hola!": "Hola",
            "\u00bfHola?": "\u00bfHola?",
            "\u00a1\u00bfHola?!": "\u00bfHola?",
        }
        for use_timing in (True, False):
            for source, rendered_text in expected.items():
                with self.subTest(source=source, timing=use_timing):
                    rendered = self._transform_phrase(
                        source,
                        timing=self._phrase_timing(source) if use_timing else None,
                        punctuation=policy,
                    )
                    self.assertEqual(rendered_text, self._cue_text(rendered))
    def test_authoritative_script_replaces_whisper_lexical_text_and_restores_signs(self):
        canonical = (
            "\u00a1Vamos a probarlo todo! \u00bfFunciona bien? texto: punto y coma; "
            "suspensivos\u2026 \u00abcomillas\u00bb \u201ccurvas\u201d \u2018simples\u2019 "
            "(tambien) guion - raya \u2014 Entonces probemos esto: \u00a1Hola!"
        )
        source_tokens = canonical.split()
        timed_tokens = [
            token.strip(
                "\u00a1!\u00bf?,.;:\u2026-\u2014\"'\u00ab\u00bb\u201c\u201d\u2018\u2019()"
            )
            for token in source_tokens
        ]
        timed_tokens = [token for token in timed_tokens if token]
        timed_tokens[-1] = "Glola"
        timing = self._timing_from_words(timed_tokens, source="whisper")
        rendered = SubtitleCueTransformer(
            subtitle_profile=SimpleNamespace(
                cue_policy=self._cue_policy(
                    "word_by_word",
                    {
                        **self.PUNCTUATION,
                        "remove_commas": True,
                        "remove_periods": True,
                    },
                ),
            ),
            render_fps=30,
        ).transform(
            "1\n00:00:00,000 --> 00:00:10,000\n" + " ".join(timed_tokens),
            timing=timing,
            canonical_content=canonical,
        )
        text = self._cue_text(rendered)

        self.assertNotIn(",", text)
        self.assertNotIn(".", text)
        self.assertIn("punto y coma;", text)
        self.assertIn("Entonces probemos esto: \u00a1Hola!", text)
        for sign in (
            "\u00bf", "?", "\u00a1", "!", ":", ";", "\u2026", "\u00ab", "\u00bb",
            "\u201c", "\u201d", "\u2018", "\u2019", "(", ")", "-", "\u2014",
        ):
            with self.subTest(authoritative_sign=sign):
                self.assertIn(sign, text)
        self.assertNotIn("Glola", text)

    def test_active_horizontal_word_by_word_profile_removes_only_comma_and_period(self):
        profile_path = Path(
            "config/profiles/guion/horizontal/estandar/subtitulos/"
            "subtitulo_guion_horizontal_palabra_por_palabra.json"
        )
        cue_policy = json.loads(
            profile_path.read_text(encoding="utf-8")
        )["cue_policy"]
        source = (
            "\u00bfHola? \u00a1Hola! texto: punto y coma; suspensivos\u2026 "
            "\u00abcomillas\u00bb \u201ccurvas\u201d \u2018simples\u2019 (tambien) "
            "guion - raya \u2014, punto."
        )
        rendered = SubtitleCueTransformer(
            subtitle_profile=SimpleNamespace(cue_policy=cue_policy),
            render_fps=30,
        ).transform(
            "1\n00:00:00,000 --> 00:00:10,000\n" + source,
        )
        text = self._cue_text(rendered)

        self.assertNotIn(",", text)
        self.assertNotIn(".", text)
        for sign in (
            "\u00bf", "?", "\u00a1", "!", ":", ";", "\u2026", "\u00ab", "\u00bb",
            "\u201c", "\u201d", "\u2018", "\u2019", "(", ")", "-", "\u2014",
        ):
            with self.subTest(sign=sign):
                self.assertIn(sign, text)

    @staticmethod
    def _timing_from_words(words, source="tts"):
        timed_words = tuple(
            WordTiming(
                text=word,
                start=index * 0.3,
                end=index * 0.3 + 0.2,
                source=source,
            )
            for index, word in enumerate(words)
        )
        return SubtitleTiming(
            source=source,
            segments=(
                SpeechSegment(
                    start=timed_words[0].start,
                    end=timed_words[-1].end,
                    words=timed_words,
                ),
            ),
        )
    def test_ambiguous_word_sequence_keeps_original_timing_text(self):
        timing = SubtitleTiming(
            source="whisper",
            segments=(
                SpeechSegment(
                    start=0,
                    end=1,
                    words=(WordTiming("uno", 0, 0.4), WordTiming("tres", 0.5, 1)),
                ),
            ),
        )
        reconciled = reconcile_timing_text(
            "1\n00:00:00,000 --> 00:00:01,000\nuno, dos", timing
        )
        self.assertEqual(("uno", "tres"), tuple(word.text for word in reconciled.words))

    def test_active_profiles_apply_the_product_policy_with_timing_and_fallback(self):
        source = (
            "\u00bfHola? \u00a1Hola! texto: punto y coma; texto\u2026 "
            "\u00abcomillas\u00bb \u201ccurvas\u201d \u2018simples\u2019 (parentesis) "
            "texto-guion texto\u2014raya, final."
        )
        source_srt = "1\n00:00:00,000 --> 00:00:12,000\n" + source
        timed_words = [
            token.strip(
                "\u00a1!\u00bf?,.;:\u2026-\u2014\"'\u00ab\u00bb\u201c\u201d\u2018\u2019()"
            )
            for token in source.split()
        ]
        timing = self._timing_from_words(timed_words)
        resolver = SubtitleProfileResolver()

        for path in sorted(Path("config/profiles").glob("*/*/estandar/subtitulos/*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            subtitle_profile = resolver.load(
                SubtitleProfileKey(
                    component=data["component"],
                    format=data["format"],
                    family=data["family"],
                    profile_id=data["profile_id"],
                )
            )
            for selected_timing in (None, timing):
                with self.subTest(path=path, timing=selected_timing is not None):
                    rendered = SubtitleCueTransformer(
                        subtitle_profile=subtitle_profile,
                        render_fps=30,
                    ).transform(source_srt, timing=selected_timing)
                    rendered_text = self._cue_text(rendered)
                    for field, characters in PunctuationPolicy._RULES:
                        for character in characters:
                            if character not in source:
                                continue
                            if data["cue_policy"]["punctuation"][field]:
                                self.assertNotIn(character, rendered_text)
                            else:
                                self.assertIn(character, rendered_text)

    def test_all_profiles_declare_the_explicit_policy(self):
        profiles = sorted(Path("config/profiles").glob("*/*/estandar/subtitulos/*.json"))
        self.assertGreaterEqual(len(profiles), 16)
        for path in profiles:
            with self.subTest(path=path):
                cue_policy = json.loads(path.read_text(encoding="utf-8"))["cue_policy"]
                policy = cue_policy["punctuation"]
                self.assertEqual(set(self.PUNCTUATION), set(policy))
                self.assertTrue(
                    all(isinstance(value, bool) for value in policy.values())
                )

    def _transform(self, style, timing=None, punctuation=None):
        return SubtitleCueTransformer(
            subtitle_profile=SimpleNamespace(cue_policy=self._cue_policy(style, punctuation)),
            render_fps=30,
        ).transform(self._source_srt(), timing=timing)

    def _cue_policy(self, style, punctuation):
        if style == "single_line":
            return {
                "mode": style,
                "max_chars_per_line": 500,
                "min_duration": 1.0,
                "max_duration": 60.0,
                "significant_gap_threshold": 0.35,
                "punctuation": punctuation or self.PUNCTUATION,
            }
        return {
            "mode": style,
            "min_duration": 0.30,
            "max_duration": 1.20,
            "significant_gap_threshold": 0.35,
            "micro_cues": {
                "enabled": True,
                "min_frames": 1,
                "min_display_seconds": 0.05,
                "merge_preference": "next",
            },
            "text_case": "original",
            "punctuation": punctuation or self.PUNCTUATION,
        }

    def _transform_phrase(self, phrase, timing, punctuation=None):
        punctuation = punctuation or {
            **self.PUNCTUATION,
            "remove_commas": True,
            "remove_periods": True,
        }
        return SubtitleCueTransformer(
            subtitle_profile=SimpleNamespace(
                cue_policy=self._cue_policy("word_by_word", punctuation),
            ),
            render_fps=30,
        ).transform(
            "1\n00:00:00,000 --> 00:00:02,000\n" + phrase,
            timing=timing,
        )

    @staticmethod
    def _phrase_timing(phrase):
        words = tuple(
            WordTiming(
                token.strip("\u00a1!\u00bf?.,"),
                index * 0.3,
                index * 0.3 + 0.2,
            )
            for index, token in enumerate(phrase.split())
        )
        return SubtitleTiming(
            source="tts",
            segments=(
                SpeechSegment(start=0, end=words[-1].end, words=words),
            ),
        )
    def _timing(self, source):
        words = []
        pattern = r'^[,.:;\u00bf?\u00a1!\u2026\u2014"\'()]+|[,.:;\u00bf?\u00a1!\u2026\u2014"\'()]+$'
        for index, token in enumerate(self.SOURCE_TEXT.split()):
            word = re.sub(pattern, "", token)
            words.append(WordTiming(word, index * 0.4, index * 0.4 + 0.3))
        return SubtitleTiming(
            source=source,
            segments=(
                SpeechSegment(start=words[0].start, end=words[-1].end, words=tuple(words)),
            ),
        )

    def _source_srt(self):
        return "1\n00:00:00,000 --> 00:00:30,000\n" f"{self.SOURCE_TEXT}"

    @staticmethod
    def _cue_text(content):
        return " ".join(
            line
            for block in content.split("\n\n")
            for line in block.splitlines()[2:]
        )


class ScriptAlignedTimingTest(unittest.TestCase):
    """The script's words always win over what Whisper heard."""

    @staticmethod
    def _timing(*segments, voice_pauses=()):
        return SubtitleTiming(
            source="whisper",
            segments=tuple(
                SpeechSegment(
                    start=words[0][1],
                    end=words[-1][2],
                    words=tuple(
                        WordTiming(text, start, end, confidence=0.5, source="whisper")
                        for text, start, end in words
                    ),
                )
                for words in segments
            ),
            voice_pauses=voice_pauses,
        )

    @staticmethod
    def _aligned(script, timing):
        return reconcile_timing_text(script, timing, authoritative=True)

    @staticmethod
    def _spans(timing):
        return [
            (word.text, round(word.start, 6), round(word.end, 6))
            for word in timing.words
        ]

    def test_same_number_of_words_takes_the_script_text_and_whisper_times(self):
        timing = self._timing(
            [("durante", 0.0, 0.4), ("siglos", 0.5, 0.9)],
            [("buscamos", 1.5, 2.0), ("fuera.", 2.1, 2.5)],
        )

        aligned = self._aligned("Durante siglos, «buscamos» fuera…", timing)

        self.assertEqual(
            [
                ("Durante", 0.0, 0.4),
                ("siglos,", 0.5, 0.9),
                ("«buscamos»", 1.5, 2.0),
                ("fuera…", 2.1, 2.5),
            ],
            self._spans(aligned),
        )
        self.assertEqual([2, 2], [len(segment.words) for segment in aligned.segments])
        self.assertEqual(0.5, aligned.words[0].confidence)

    def test_changed_word_keeps_its_whisper_times(self):
        timing = self._timing(
            [("Y", 0.0, 0.2), ("quizás", 0.3, 0.8), ("sea", 0.9, 1.1), ("así.", 1.2, 1.5)]
        )

        aligned = self._aligned("Y quizá sea así.", timing)

        self.assertEqual(
            [("Y", 0.0, 0.2), ("quizá", 0.3, 0.8), ("sea", 0.9, 1.1), ("así.", 1.2, 1.5)],
            self._spans(aligned),
        )

    def test_extra_whisper_word_is_left_out(self):
        timing = self._timing(
            [("de", 0.0, 0.2), ("verdad", 0.3, 0.7), ("que", 0.8, 0.9), ("aquella", 1.0, 1.5)]
        )

        aligned = self._aligned("de verdad aquella", timing)

        self.assertEqual(
            [("de", 0.0, 0.2), ("verdad", 0.3, 0.7), ("aquella", 1.0, 1.5)],
            self._spans(aligned),
        )

    def test_missing_word_shares_the_time_of_the_previous_word(self):
        timing = self._timing(
            [("empezó", 0.0, 0.5), ("luchar", 0.6, 1.0), ("con", 1.1, 1.3)]
        )

        aligned = self._aligned("empezó a luchar con", timing)

        self.assertEqual(
            [("empezó", 0.0, 0.428571), ("a", 0.428571, 0.5), ("luchar", 0.6, 1.0), ("con", 1.1, 1.3)],
            self._spans(aligned),
        )
        self.assertEqual("approximate", aligned.words[1].source)

    def test_missing_word_after_a_sentence_end_shares_the_next_word(self):
        timing = self._timing(
            [("fin.", 0.0, 0.4)],
            [("Jacob", 2.0, 2.5), ("salió.", 2.6, 3.0)],
        )

        aligned = self._aligned("fin.\n\nY Jacob salió.", timing)

        self.assertEqual(
            [("fin.", 0.0, 0.4), ("Y", 2.0, 2.083333), ("Jacob", 2.083333, 2.5), ("salió.", 2.6, 3.0)],
            self._spans(aligned),
        )
        self.assertEqual([1, 3], [len(segment.words) for segment in aligned.segments])

    def test_run_with_another_number_of_words_is_spread_by_letters_in_its_span(self):
        timing = self._timing(
            [("un", 0.0, 0.2), ("serie", 0.3, 0.8), ("misterioso", 0.9, 1.5)]
        )

        aligned = self._aligned("un ser y misterioso", timing)

        self.assertEqual(
            [("un", 0.0, 0.2), ("ser", 0.3, 0.675), ("y", 0.675, 0.8), ("misterioso", 0.9, 1.5)],
            self._spans(aligned),
        )

    def test_unequal_run_around_a_pause_is_cut_at_the_script_sentence_end(self):
        # Whisper heard "adelante. Ischopenhauer," for "delante. Y
        # Schopenhauer,"; the voice paused after the sentence.
        timing = self._timing(
            [("hacia", 9.8, 10.3), ("adelante.", 10.4, 10.99),
             ("Ischopenhauer,", 11.5, 12.34), ("se", 12.4, 12.6), ("reía.", 12.7, 13.0)],
            voice_pauses=((10.995, 11.495),),
        )

        aligned = self._aligned("hacia delante. Y Schopenhauer, se reía.", timing)

        self.assertEqual(
            [
                ("hacia", 9.8, 10.3),
                ("delante.", 10.4, 10.995),
                ("Y", 11.495, 11.555357),
                ("Schopenhauer,", 11.555357, 12.34),
                ("se", 12.4, 12.6),
                ("reía.", 12.7, 13.0),
            ],
            self._spans(aligned),
        )

    def test_unequal_run_around_a_pause_without_a_sentence_end_is_cut_by_letters(self):
        # Letters spread over the 1.0 s of voice: "dos" and "tres" fall in
        # the 0.45 s before the pause, "cuatro" after it.
        timing = self._timing(
            [("uno", 0.0, 0.4), ("dostre", 0.5, 0.9), ("scuatro", 1.4, 1.9),
             ("cinco", 2.0, 2.4)],
            voice_pauses=((0.95, 1.35),),
        )

        aligned = self._aligned("uno dos tres cuatro cinco", timing)

        self.assertEqual(
            [
                ("uno", 0.0, 0.4),
                ("dos", 0.5, 0.692857),
                ("tres", 0.692857, 0.95),
                ("cuatro", 1.35, 1.9),
                ("cinco", 2.0, 2.4),
            ],
            self._spans(aligned),
        )

    def test_unequal_run_around_two_pauses_keeps_each_sentence_on_its_side(self):
        timing = self._timing(
            [("Ben.", 0.0, 0.4), ("Mirra.", 1.0, 1.5), ("Marazul.", 2.1, 2.9)],
            voice_pauses=((0.5, 1.0), (1.6, 2.1)),
        )

        aligned = self._aligned("Ven. Mira. Mar azul.", timing)

        self.assertEqual(
            [
                ("Ven.", 0.0, 0.5),
                ("Mira.", 1.0, 1.6),
                ("Mar", 2.1, 2.4),
                ("azul.", 2.4, 2.9),
            ],
            self._spans(aligned),
        )

    def test_pause_at_the_edge_of_an_unequal_run_changes_nothing(self):
        pauses = ((0.2, 0.3), (0.8, 0.9))
        timing = self._timing(
            [("un", 0.0, 0.2), ("serie", 0.3, 0.8), ("misterioso", 0.9, 1.5)],
            voice_pauses=pauses,
        )

        aligned = self._aligned("un ser y misterioso", timing)

        self.assertEqual(
            [("un", 0.0, 0.2), ("ser", 0.3, 0.675), ("y", 0.675, 0.8), ("misterioso", 0.9, 1.5)],
            self._spans(aligned),
        )
        self.assertEqual(pauses, aligned.voice_pauses)

    def test_pauses_outside_the_runs_leave_the_alignment_as_today(self):
        script = "Un ser y misterioso.\n\nY quizá sea así."
        segments = (
            [("un", 0.0, 0.2), ("serie", 0.3, 0.8), ("misterioso.", 0.9, 1.5)],
            [("Y", 2.0, 2.2), ("quizás", 2.3, 2.8), ("sea", 2.9, 3.1), ("así.", 3.2, 3.5)],
        )

        self.assertEqual(
            self._spans(self._aligned(script, self._timing(*segments))),
            self._spans(
                self._aligned(
                    script,
                    self._timing(*segments, voice_pauses=((1.6, 1.95),)),
                )
            ),
        )

    def test_cue_transformer_shows_no_text_inside_the_pause_of_an_unequal_run(self):
        timing = self._timing(
            [("hacia", 9.8, 10.3), ("adelante.", 10.4, 10.99),
             ("Ischopenhauer,", 11.5, 12.34), ("se", 12.4, 12.6), ("reía.", 12.7, 13.0)],
            voice_pauses=((10.995, 11.495),),
        )
        transformer = SubtitleCueTransformer(
            subtitle_profile=SimpleNamespace(
                cue_policy={
                    "mode": "single_line",
                    "max_chars_per_line": 60,
                    "min_duration": 1.0,
                    "max_duration": 3.0,
                    "significant_gap_threshold": 0.35,
                    "punctuation": dict(SubtitlePunctuationTest.PUNCTUATION),
                },
            ),
            render_fps=30,
        )

        rendered = transformer.transform(
            "1\n00:00:09,800 --> 00:00:13,000\nhacia adelante. Ischopenhauer, se reía.",
            timing=timing,
            canonical_content="hacia delante. Y Schopenhauer, se reía.",
        )

        for block in rendered.split("\n\n"):
            start, end = re.findall(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", block)[:2]
            start, end = (
                int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
                for h, m, s, ms in (start, end)
            )
            self.assertFalse(start < 11.495 and end > 10.995, block)

    def test_differences_of_case_accents_and_signs_still_align(self):
        timing = self._timing(
            [("Genesis,", 0.0, 0.5), ("solo", 0.6, 0.9), ("entonces", 1.0, 1.4)]
        )

        aligned = self._aligned("Génesis: sólo entonces,", timing)

        self.assertEqual(
            [("Génesis:", 0.0, 0.5), ("sólo", 0.6, 0.9), ("entonces,", 1.0, 1.4)],
            self._spans(aligned),
        )

    def test_paragraph_of_three_lines_is_read_whole(self):
        timing = self._timing(
            [("uno", 0.0, 0.2), ("dos", 0.3, 0.5), ("tres", 0.6, 0.8), ("cuatro", 0.9, 1.1)]
        )

        aligned = self._aligned("Uno,\ndos,\ntres\ncuatro.", timing)

        self.assertEqual(
            ["Uno,", "dos,", "tres", "cuatro."],
            [word.text for word in aligned.words],
        )

    def test_empty_script_keeps_the_whisper_timing(self):
        timing = self._timing([("hola", 0.0, 0.4)])

        for script in ("", "   \n\n "):
            with self.subTest(script=script):
                self.assertIs(timing, self._aligned(script, timing))

    def test_script_word_timings_keep_every_script_word_and_its_sentence_end(self):
        timing = self._timing(
            [("fin", 0.0, 0.4)],
            [("Jacob", 2.0, 2.5), ("salió", 2.6, 3.0), ("hoy", 3.1, 3.3)],
        )

        words = script_word_timings(
            "Fin.\n\nY Jacob salió, «tarde»",
            timing,
        )

        self.assertEqual(
            [
                ("Fin.", 0.0, 0.4, True),
                ("Y", 2.0, 2.083333, False),
                ("Jacob", 2.083333, 2.5, False),
                ("salió,", 2.6, 3.0, False),
                ("«tarde»", 3.1, 3.3, True),
            ],
            [
                (word.text, round(word.start, 6), round(word.end, 6), closes)
                for word, closes in words
            ],
        )

    def test_script_word_timings_are_empty_without_script_or_timing(self):
        timing = self._timing([("hola", 0.0, 0.4)])

        self.assertEqual((), script_word_timings("   ", timing))
        self.assertEqual((), script_word_timings("Hola.", None))
        self.assertEqual(
            (),
            script_word_timings(
                "Hola.",
                SubtitleTiming(source="whisper", segments=()),
            ),
        )

    def test_cue_transformer_renders_exactly_the_script_words(self):
        script = "Pero quizá, ¿solo entonces? ¡Sí!"
        timing = self._timing(
            [("Pero", 0.0, 0.3), ("quizás", 0.4, 0.8), ("sólo", 0.9, 1.2),
             ("que", 1.25, 1.3), ("entonces", 1.3, 1.8), ("sí", 1.9, 2.2)]
        )
        transformer = SubtitleCueTransformer(
            subtitle_profile=SimpleNamespace(
                cue_policy={
                    "mode": "single_line",
                    "max_chars_per_line": 60,
                    "min_duration": 1.0,
                    "max_duration": 3.0,
                    "significant_gap_threshold": 0.35,
                    "punctuation": dict(SubtitlePunctuationTest.PUNCTUATION),
                },
            ),
            render_fps=30,
        )

        rendered = transformer.transform(
            "1\n00:00:00,000 --> 00:00:02,200\nPero quizás sólo que entonces sí",
            timing=timing,
            canonical_content=script,
        )

        self.assertEqual(script, SubtitlePunctuationTest._cue_text(rendered))


if __name__ == "__main__":
    unittest.main()
