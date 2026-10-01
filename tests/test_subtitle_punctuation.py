import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.modules.subtitles.pipeline.cue_transformer import SubtitleCueTransformer
from app.modules.subtitles.policies.punctuation import reconcile_timing_text
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

    def test_single_line_restores_canonical_punctuation_from_edge_and_whisper(self):
        for source in ("edge_tts", "whisper"):
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
        for timing in (self._timing("edge_tts"), None):
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

    def test_active_youtube_word_by_word_profile_removes_only_comma_and_period(self):
        profile_path = Path(
            "config/profiles/guion/youtube/estandar/subtitulos/"
            "subtitulo_guion_youtube_palabra_por_palabra.json"
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
    def _timing_from_words(words, source="edge_tts"):
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
                    platform=data["platform"],
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
                    if data["cue_policy"]["mode"] == "single_line":
                        self.assertEqual(source, rendered_text)
                    else:
                        self.assertNotIn(",", rendered_text)
                        self.assertNotIn(".", rendered_text)
                        for sign in (
                            "\u00bf", "?", "\u00a1", "!", ":", ";", "\u2026",
                            "\u00ab", "\u00bb", "\u201c", "\u201d", "\u2018", "\u2019",
                            "(", ")", "-", "\u2014",
                        ):
                            self.assertIn(sign, rendered_text)

    def test_all_profiles_declare_the_explicit_policy(self):
        profiles = sorted(Path("config/profiles").glob("*/*/estandar/subtitulos/*.json"))
        self.assertGreaterEqual(len(profiles), 16)
        for path in profiles:
            with self.subTest(path=path):
                cue_policy = json.loads(path.read_text(encoding="utf-8"))["cue_policy"]
                policy = cue_policy["punctuation"]
                self.assertEqual(set(self.PUNCTUATION), set(policy))
                if cue_policy["mode"] == "single_line":
                    self.assertEqual(self.PUNCTUATION, policy)
                else:
                    self.assertTrue(policy["remove_commas"])
                    self.assertTrue(policy["remove_periods"])
                    self.assertTrue(
                        all(
                            not value
                            for key, value in policy.items()
                            if key not in {"remove_commas", "remove_periods"}
                        )
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
            "uppercase": False,
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
            source="edge_tts",
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


if __name__ == "__main__":
    unittest.main()
