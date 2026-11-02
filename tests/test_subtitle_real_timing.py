import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.modules.subtitles.io.subtitle_builder import SubtitleBuilder
from app.modules.subtitles.modes.single_line import SingleLineModel
from app.modules.subtitles.modes.word_by_word import WordByWordModel
from app.modules.subtitles.policies.timing import (
    SpeechSegment,
    SubtitleTiming,
    SubtitleTimingResolver,
    WhisperTimingParser,
    WordTiming,
    approximate_voiced_word_timings,
    approximate_word_timings,
    fit_words_to_voice_pauses,
    whisper_timing_path,
)


class SubtitleRealTimingTest(unittest.TestCase):

    def test_whisper_timing_parser_reads_word_timestamps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata_path = Path(temp_dir) / "subtitulos_whisper.json"
            metadata_path.write_text(
                json.dumps(
                    {
                        "segments": [
                            {
                                "start": 0.0,
                                "end": 0.8,
                                "words": [
                                    {
                                        "word": "Hola",
                                        "start": 0.0,
                                        "end": 0.3,
                                        "probability": 0.93,
                                    },
                                    {
                                        "word": "mundo",
                                        "start": 0.35,
                                        "end": 0.8,
                                        "probability": 0.91,
                                    },
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            timing = WhisperTimingParser().parse(metadata_path)

        self.assertEqual(timing.source, "whisper")
        self.assertEqual(timing.reliability, "secondary")
        self.assertEqual(timing.word_count, 2)
        self.assertEqual(timing.words[0].confidence, 0.93)

    def test_timing_rejects_invalid_order(self):
        with self.assertRaises(ValueError):
            SpeechSegment(
                start=0.0,
                end=1.0,
                words=(
                    WordTiming("uno", 0.4, 0.8),
                    WordTiming("dos", 0.7, 1.0),
                ),
            )

    def test_resolver_uses_whisper_when_usable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            audio_path = temp_path / "voz.mp3"
            subtitle_path = temp_path / "subtitulos.srt"
            audio_path.write_bytes(b"audio")
            subtitle_path.write_text("", encoding="utf-8")

            whisper_timing_path(subtitle_path).write_text(
                json.dumps(
                    {
                        "segments": [
                            {
                                "words": [
                                    {
                                        "word": "Whisper",
                                        "start": 0.0,
                                        "end": 1.0,
                                    }
                                ]
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            timing = SubtitleTimingResolver().resolve(
                subtitle_path=subtitle_path,
                audio_path=audio_path,
            )

        self.assertEqual(timing.source, "whisper")
        self.assertIsNone(timing.fallback_reason)

    def test_resolver_returns_none_when_whisper_metadata_is_invalid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            audio_path = temp_path / "voz.mp3"
            subtitle_path = temp_path / "subtitulos.srt"
            audio_path.write_bytes(b"audio")
            subtitle_path.write_text("", encoding="utf-8")

            whisper_timing_path(subtitle_path).write_text(
                "{invalid",
                encoding="utf-8",
            )

            timing = SubtitleTimingResolver().resolve(
                subtitle_path=subtitle_path,
                audio_path=audio_path,
            )

        self.assertIsNone(timing)

    def test_resolver_returns_none_when_no_timing_sidecar_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            subtitle_path = Path(temp_dir) / "subtitulos.srt"
            subtitle_path.write_text("", encoding="utf-8")

            timing = SubtitleTimingResolver().resolve(
                subtitle_path=subtitle_path
            )

        self.assertIsNone(timing)

    def test_word_by_word_uses_real_word_timing_and_preserves_gap(self):
        model = self._word_by_word_model(
            fps=30
        )
        timing = SubtitleTiming(
            source="tts",
            segments=(
                SpeechSegment(
                    start=0.0,
                    end=1.0,
                    words=(
                        WordTiming("Hola,", 0.0, 0.2),
                        WordTiming("mundo", 0.7, 1.0),
                    ),
                ),
            ),
        )

        blocks = model.optimize([], timing=timing)

        self.assertIn("00:00:00,000 --> 00:00:00,200", blocks[0])
        self.assertIn("Hola", blocks[0])
        self.assertNotIn("Hola,", blocks[0])
        self.assertNotIn(".", blocks[0])
        self.assertIn("00:00:00,700 --> 00:00:01,000", blocks[1])

    def test_word_by_word_removes_render_dots_with_extra_commas_policy(self):
        model = self._word_by_word_model(fps=30)

        blocks = model.optimize(
            [
                "1\n"
                "00:00:00,000 --> 00:00:01,000\n"
                "Hola, mundo."
            ]
        )

        self.assertEqual(["Hola", "mundo"], [
            self._block_text(block)
            for block in blocks
        ])

    def test_word_by_word_preserves_legacy_distribution_without_timing(self):
        model = self._word_by_word_model(
            fps=30
        )
        blocks = model.optimize(
            [
                "1\n"
                "00:00:00,000 --> 00:00:02,000\n"
                "Hola mundo"
            ]
        )

        self.assertEqual(len(blocks), 2)
        self.assertIn("00:00:00,000 --> 00:00:01,000", blocks[0])
        self.assertIn("00:00:01,000 --> 00:00:02,000", blocks[1])

    def test_single_line_uses_real_word_timing_and_preserves_gap(self):
        model = SingleLineModel(
            {
                "max_chars_per_line": 60,
                "min_duration": 1.0,
                "max_duration": 3.0,
                "significant_gap_threshold": 0.35,
                "punctuation": {
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
                },
            }
        )
        timing = SubtitleTiming(
            source="tts",
            segments=(
                SpeechSegment(
                    start=0.0,
                    end=1.2,
                    words=(
                        WordTiming("Durante", 0.0, 0.2),
                        WordTiming("siglos", 0.22, 0.5),
                        WordTiming("buscamos", 1.0, 1.2),
                    ),
                ),
            ),
        )

        blocks = model.optimize([], timing=timing)

        self.assertEqual(len(blocks), 2)
        self.assertIn("00:00:00,000 --> 00:00:00,500", blocks[0])
        self.assertIn("Durante siglos", blocks[0])
        self.assertIn("00:00:01,000 --> 00:00:01,200", blocks[1])
        self.assertIn("buscamos", blocks[1])

    def test_single_line_preserves_legacy_behavior_without_timing(self):
        model = SingleLineModel(
            {
                "max_chars_per_line": 60,
                "min_duration": 1.0,
                "max_duration": 3.0,
                "significant_gap_threshold": 0.35,
                "punctuation": {
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
                },
            }
        )
        blocks = model.optimize(
            [
                "1\n"
                "00:00:00,000 --> 00:00:02,000\n"
                "Durante siglos buscamos respuestas"
            ]
        )

        self.assertEqual(len(blocks), 1)
        self.assertIn("00:00:00,000 --> 00:00:02,000", blocks[0])

    def test_subtitle_builder_requests_single_whisper_pass_with_json_sidecar(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            audio_path = temp_path / "voz.mp3"
            output_path = temp_path / "subtitulos.srt"
            audio_path.write_bytes(b"audio")
            calls = []

            def fake_run(command, check):
                calls.append(command)
                output_dir = Path(command[-1])
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "voz.srt").write_text(
                    "1\n00:00:00,000 --> 00:00:01,000\nHola\n",
                    encoding="utf-8",
                )
                (output_dir / "voz.json").write_text(
                    json.dumps({"segments": []}),
                    encoding="utf-8",
                )

            with patch(
                "app.modules.subtitles.io.subtitle_builder.subprocess.run",
                side_effect=fake_run,
            ):
                SubtitleBuilder().build(
                    audio_path=audio_path,
                    output_path=output_path,
                )

            command = calls[0]
            self.assertIn("--word_timestamps", command)
            self.assertIn("True", command)
            self.assertIn("--output_format", command)
            self.assertIn("all", command)
            self.assertTrue(output_path.exists())
            self.assertTrue(whisper_timing_path(output_path).exists())

    def test_real_micro_cue_merges_with_next_word(self):
        original_words = (
            WordTiming("y", 9.063, 9.089, source="tts"),
            WordTiming("la", 9.103, 9.208, source="tts"),
        )
        model = self._word_by_word_model(
            fps=30
        )

        blocks = model.optimize(
            [],
            timing=self._timing(
                original_words
            ),
        )

        self.assertEqual(len(blocks), 1)
        self.assertIn("y la", blocks[0])
        self.assertIn("00:00:09,063 --> 00:00:09,208", blocks[0])
        self.assertEqual(original_words[0].start, 9.063)
        self.assertEqual(original_words[0].end, 9.089)
        self.assertEqual(original_words[1].start, 9.103)
        self.assertEqual(original_words[1].end, 9.208)
        self.assertEqual(model.last_micro_cue_stats.detected, 1)
        self.assertEqual(model.last_micro_cue_stats.merged, 1)

    def test_normal_word_is_not_modified_by_micro_cue_policy(self):
        model = self._word_by_word_model(
            fps=30
        )

        blocks = model.optimize(
            [],
            timing=self._timing(
                (
                    WordTiming("conciencia", 8.063, 8.761),
                )
            ),
        )

        self.assertEqual(len(blocks), 1)
        self.assertIn("conciencia", blocks[0])
        self.assertIn("00:00:08,063 --> 00:00:08,761", blocks[0])
        self.assertEqual(model.last_micro_cue_stats.detected, 0)

    def test_final_micro_cue_merges_with_previous_when_safe(self):
        model = self._word_by_word_model(
            fps=30
        )

        blocks = model.optimize(
            [],
            timing=self._timing(
                (
                    WordTiming("la", 9.103, 9.208),
                    WordTiming("y", 9.221, 9.247),
                )
            ),
        )

        self.assertEqual(len(blocks), 1)
        self.assertIn("la y", blocks[0])
        self.assertIn("00:00:09,103 --> 00:00:09,247", blocks[0])

    def test_micro_cue_does_not_merge_across_significant_silence(self):
        model = self._word_by_word_model(
            fps=30
        )

        blocks = model.optimize(
            [],
            timing=self._timing(
                (
                    WordTiming("y", 1.000, 1.026),
                    WordTiming("la", 1.500, 1.650),
                )
            ),
        )

        self.assertEqual(len(blocks), 2)
        self.assertIn("y", blocks[0])
        self.assertNotIn("y la", blocks[0])
        self.assertIn("00:00:01,000 --> 00:00:01,050", blocks[0])
        self.assertIn("00:00:01,500 --> 00:00:01,650", blocks[1])

    def test_two_consecutive_micro_cues_are_consumed_without_duplication(self):
        model = self._word_by_word_model(
            fps=30
        )

        blocks = model.optimize(
            [],
            timing=self._timing(
                (
                    WordTiming("y", 1.000, 1.020),
                    WordTiming("la", 1.030, 1.055),
                    WordTiming("voz", 1.065, 1.300),
                )
            ),
        )

        text = " ".join(self._block_text(block) for block in blocks)

        self.assertEqual(text.split(), ["y", "la", "voz"])
        self.assertEqual(len(blocks), 2)
        self.assertIn("y la", blocks[0])
        self.assertIn("voz", blocks[1])

    def test_three_consecutive_micro_cues_are_deterministic(self):
        model = self._word_by_word_model(
            fps=30
        )

        blocks = model.optimize(
            [],
            timing=self._timing(
                (
                    WordTiming("a", 1.000, 1.015),
                    WordTiming("la", 1.025, 1.045),
                    WordTiming("luz", 1.055, 1.080),
                    WordTiming("interior", 1.090, 1.350),
                )
            ),
        )

        text = " ".join(self._block_text(block) for block in blocks)

        self.assertEqual(text.split(), ["a", "la", "luz", "interior"])
        self.assertEqual(len(blocks), 2)
        self.assertIn("a la luz", blocks[0])
        self.assertIn("interior", blocks[1])

    def test_micro_cue_policy_preserves_punctuation_order(self):
        model = self._word_by_word_model(
            fps=30,
            remove_commas=False,
            remove_periods=False,
        )

        blocks = model.optimize(
            [],
            timing=self._timing(
                (
                    WordTiming("y,", 2.000, 2.026),
                    WordTiming("entonces", 2.040, 2.300),
                )
            ),
        )

        self.assertEqual(len(blocks), 1)
        self.assertIn("y, entonces", blocks[0])

    def test_micro_cue_policy_uses_24_fps_frame_threshold(self):
        model = self._word_by_word_model(
            fps=24,
            min_display_seconds=0.01,
        )

        blocks = model.optimize(
            [],
            timing=self._timing(
                (
                    WordTiming("y", 1.000, 1.030),
                    WordTiming("la", 1.035, 1.200),
                )
            ),
        )

        self.assertEqual(len(blocks), 1)
        self.assertIn("y la", blocks[0])

    def test_micro_cue_policy_uses_30_fps_frame_threshold(self):
        model = self._word_by_word_model(
            fps=30,
            min_display_seconds=0.01,
        )

        blocks = model.optimize(
            [],
            timing=self._timing(
                (
                    WordTiming("y", 1.000, 1.026),
                    WordTiming("la", 1.035, 1.200),
                )
            ),
        )

        self.assertEqual(len(blocks), 1)
        self.assertIn("y la", blocks[0])

    def test_micro_cue_policy_does_not_flag_same_duration_at_60_fps(self):
        model = self._word_by_word_model(
            fps=60,
            min_display_seconds=0.01,
        )

        blocks = model.optimize(
            [],
            timing=self._timing(
                (
                    WordTiming("y", 1.000, 1.030),
                    WordTiming("la", 1.040, 1.200),
                )
            ),
        )

        self.assertEqual(len(blocks), 2)
        self.assertIn("00:00:01,000 --> 00:00:01,030", blocks[0])
        self.assertEqual(model.last_micro_cue_stats.detected, 0)

    def test_micro_cue_policy_applies_to_neutral_timing(self):
        model = self._word_by_word_model(
            fps=30
        )

        blocks = model.optimize(
            [],
            timing=SubtitleTiming(
                source="tts",
                segments=(
                    SpeechSegment(
                        start=1.0,
                        end=1.2,
                        words=(
                            WordTiming("y", 1.0, 1.026, source="tts"),
                            WordTiming("la", 1.04, 1.2, source="tts"),
                        ),
                    ),
                ),
            ),
        )

        self.assertEqual(len(blocks), 1)
        self.assertIn("y la", blocks[0])

    def test_micro_cue_policy_applies_to_whisper_fallback_timing(self):
        model = self._word_by_word_model(
            fps=30
        )

        blocks = model.optimize(
            [],
            timing=SubtitleTiming(
                source="whisper",
                segments=(
                    SpeechSegment(
                        start=1.0,
                        end=1.2,
                        words=(
                            WordTiming("y", 1.0, 1.026, source="whisper"),
                            WordTiming("la", 1.04, 1.2, source="whisper"),
                        ),
                    ),
                ),
            ),
        )

        self.assertEqual(len(blocks), 1)
        self.assertIn("y la", blocks[0])

    def test_legacy_srt_behavior_is_preserved_without_rich_timing(self):
        model = self._word_by_word_model(
            fps=30
        )

        blocks = model.optimize(
            [
                "1\n"
                "00:00:00,000 --> 00:00:02,000\n"
                "y la"
            ]
        )

        self.assertEqual(len(blocks), 2)
        self.assertIn("00:00:00,000 --> 00:00:01,000", blocks[0])
        self.assertIn("00:00:01,000 --> 00:00:02,000", blocks[1])

    def test_micro_cues_can_be_disabled_by_configuration(self):
        model = self._word_by_word_model(
            fps=30,
            micro_cues_enabled=False,
        )

        blocks = model.optimize(
            [],
            timing=self._timing(
                (
                    WordTiming("y", 9.063, 9.089),
                    WordTiming("la", 9.103, 9.208),
                )
            ),
        )

        self.assertEqual(len(blocks), 2)
        self.assertIn("00:00:09,063 --> 00:00:09,089", blocks[0])
        self.assertIn("00:00:09,103 --> 00:00:09,208", blocks[1])

    def _word_by_word_model(
        self,
        fps,
        min_display_seconds=0.05,
        remove_commas=True,
        remove_periods=True,
        micro_cues_enabled=True
    ):
        return WordByWordModel(
            {
                "min_duration": 0.3,
                "max_duration": 1.2,
                "text_case": "original",
                "punctuation": {
                    "remove_commas": remove_commas,
                    "remove_periods": remove_periods,
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
                },
                "render_fps": fps,
                "significant_gap_threshold": 0.35,
                "micro_cues": {
                    "enabled": micro_cues_enabled,
                    "min_frames": 1,
                    "min_display_seconds": min_display_seconds,
                    "merge_preference": "next",
                },
            }
        )

    def _timing(
        self,
        words,
        source="tts"
    ):
        return SubtitleTiming(
            source=source,
            segments=(
                SpeechSegment(
                    start=words[0].start,
                    end=words[-1].end,
                    words=tuple(
                        words
                    ),
                ),
            ),
        )

    def _block_text(
        self,
        block
    ):
        return " ".join(
            block.splitlines()[2:]
        )


class VoicePauseFittingTest(unittest.TestCase):

    PAUSE = (2.0, 3.5)

    def _timing(self, *words, voice_pauses=(PAUSE,)):
        return SubtitleTiming(
            source="whisper",
            segments=(
                SpeechSegment(
                    start=words[0][1],
                    end=words[-1][2],
                    words=tuple(
                        WordTiming(text, start, end, confidence=0.9, source="whisper")
                        for text, start, end in words
                    ),
                ),
            ),
            voice_pauses=voice_pauses,
        )

    def _spans(self, timing):
        return [(word.text, word.start, word.end) for word in timing.words]

    def test_word_running_into_a_pause_ends_where_the_pause_starts(self):
        fitted = fit_words_to_voice_pauses(
            self._timing(("uno", 1.0, 1.6), ("ángel.", 1.7, 3.2), ("Jacob", 3.6, 4.0))
        )

        self.assertEqual(
            [("uno", 1.0, 1.6), ("ángel.", 1.7, 2.0), ("Jacob", 3.6, 4.0)],
            self._spans(fitted),
        )
        self.assertEqual(0.9, fitted.words[1].confidence)
        self.assertEqual("whisper", fitted.words[1].source)

    def test_word_starting_inside_a_pause_starts_where_the_pause_ends(self):
        fitted = fit_words_to_voice_pauses(
            self._timing(("profundo:", 1.0, 1.9), ("aquella", 2.4, 4.1))
        )

        self.assertEqual(
            [("profundo:", 1.0, 1.9), ("aquella", 3.5, 4.1)],
            self._spans(fitted),
        )

    def test_word_wholly_inside_a_pause_is_left_with_zero_duration_at_its_end(self):
        fitted = fit_words_to_voice_pauses(
            self._timing(("uno", 1.0, 1.9), ("que", 2.5, 2.9), ("dos", 3.0, 4.0))
        )

        self.assertEqual(
            [("uno", 1.0, 1.9), ("que", 3.5, 3.5), ("dos", 3.5, 4.0)],
            self._spans(fitted),
        )

    def test_word_crossing_the_whole_pause_keeps_the_side_with_more_time(self):
        before = fit_words_to_voice_pauses(
            self._timing(("Prado.", 1.5, 3.8), ("Jacob", 3.9, 4.2))
        )
        after = fit_words_to_voice_pauses(
            self._timing(("vida.", 1.4, 1.97), ("Cambiar", 1.97, 3.9))
        )
        tie = fit_words_to_voice_pauses(self._timing(("uno", 1.7, 3.8)))

        self.assertEqual(
            [("Prado.", 1.5, 2.0), ("Jacob", 3.9, 4.2)],
            self._spans(before),
        )
        self.assertEqual(
            [("vida.", 1.4, 1.97), ("Cambiar", 3.5, 3.9)],
            self._spans(after),
        )
        self.assertEqual([("uno", 1.7, 2.0)], self._spans(tie))

    def test_words_touching_a_pause_edge_and_several_pauses(self):
        fitted = fit_words_to_voice_pauses(
            self._timing(
                ("uno", 1.0, 2.0),
                ("dos", 3.5, 4.0),
                ("tres", 4.1, 5.3),
                ("cuatro", 5.6, 6.0),
                voice_pauses=((2.0, 3.5), (5.0, 5.5)),
            )
        )

        self.assertEqual(
            [("uno", 1.0, 2.0), ("dos", 3.5, 4.0), ("tres", 4.1, 5.0), ("cuatro", 5.6, 6.0)],
            self._spans(fitted),
        )
        self.assertEqual((1.0, 6.0), (fitted.segments[0].start, fitted.segments[0].end))

    def test_without_pauses_the_timing_is_returned_unchanged(self):
        timing = self._timing(("ángel.", 1.7, 3.2), voice_pauses=())

        self.assertIs(timing, fit_words_to_voice_pauses(timing))

    def _write_whisper_json(self, directory, **extra):
        subtitle_path = Path(directory) / "subtitulos.srt"
        subtitle_path.write_text("", encoding="utf-8")
        whisper_timing_path(subtitle_path).write_text(
            json.dumps(
                {
                    "segments": [
                        {
                            "start": 1.0,
                            "end": 4.2,
                            "words": [
                                {"word": " ángel.", "start": 1.0, "end": 3.2, "probability": 0.8},
                                {"word": " Jacob", "start": 3.3, "end": 4.2, "probability": 0.9},
                            ],
                        }
                    ],
                    **extra,
                }
            ),
            encoding="utf-8",
        )
        return subtitle_path

    def test_resolver_fits_whisper_words_to_the_recorded_voice_pauses(self):
        with tempfile.TemporaryDirectory() as directory:
            subtitle_path = self._write_whisper_json(
                directory,
                voice_pauses=[{"start": 2.0, "end": 3.5}],
            )

            timing = SubtitleTimingResolver().resolve(subtitle_path=subtitle_path)

        self.assertEqual(((2.0, 3.5),), timing.voice_pauses)
        self.assertEqual(
            [("ángel.", 1.0, 2.0), ("Jacob", 3.5, 4.2)],
            self._spans(timing),
        )

    def test_resolver_without_voice_pauses_keeps_whisper_times(self):
        with tempfile.TemporaryDirectory() as directory:
            subtitle_path = self._write_whisper_json(directory)

            timing = SubtitleTimingResolver().resolve(subtitle_path=subtitle_path)
            parsed = WhisperTimingParser().parse(whisper_timing_path(subtitle_path))

        self.assertEqual(parsed, timing)
        self.assertEqual((), timing.voice_pauses)
        self.assertEqual(
            [("ángel.", 1.0, 3.2), ("Jacob", 3.3, 4.2)],
            self._spans(timing),
        )

    def test_resolver_returns_none_when_voice_pauses_are_invalid(self):
        for voice_pauses in (
            {"start": 2.0, "end": 3.5},
            [{"start": 2.0}],
            [{"start": 3.5, "end": 2.0}],
            [{"start": 2.0, "end": 3.0}, {"start": 2.5, "end": 4.0}],
        ):
            with self.subTest(voice_pauses=voice_pauses):
                with tempfile.TemporaryDirectory() as directory:
                    subtitle_path = self._write_whisper_json(
                        directory,
                        voice_pauses=voice_pauses,
                    )

                    self.assertIsNone(
                        SubtitleTimingResolver().resolve(subtitle_path=subtitle_path)
                    )

    def test_single_line_shows_no_text_inside_the_pause(self):
        model = SingleLineModel(
            {
                "max_chars_per_line": 60,
                "min_duration": 1.0,
                "max_duration": 3.0,
                "significant_gap_threshold": 0.35,
                "punctuation": {
                    key: False
                    for key in (
                        "remove_commas", "remove_periods", "remove_colons",
                        "remove_semicolons", "remove_question_marks",
                        "remove_exclamation_marks", "remove_ellipsis",
                        "remove_hyphens", "remove_em_dashes",
                        "remove_double_quotes", "remove_single_quotes",
                        "remove_parentheses",
                    )
                },
            }
        )
        timing = self._timing(
            ("Luchó", 0.5, 1.0), ("con", 1.05, 1.3), ("un", 1.35, 1.5),
            ("ángel.", 1.55, 3.25), ("Jacob", 3.3, 4.0), ("salió.", 4.05, 4.6),
        )

        blocks = model.optimize([], timing=fit_words_to_voice_pauses(timing))

        self.assertEqual(2, len(blocks))
        self.assertIn("00:00:00,500 --> 00:00:02,000\nLuchó con un ángel.", blocks[0])
        self.assertIn("00:00:03,500 --> 00:00:04,600\nJacob salió.", blocks[1])

    def _build_subtitles(self, directory, **build_options):
        directory = Path(directory)
        audio_path = directory / "voz.mp3"
        output_path = directory / "subtitulos.srt"
        audio_path.write_bytes(b"audio")
        whisper_json = json.dumps(
            {"segments": [{"words": [{"word": " Hola", "start": 0.0, "end": 0.5}]}]}
        )

        def fake_run(command, check):
            output_dir = Path(command[-1])
            (output_dir / "voz.srt").write_text(
                "1\n00:00:00,000 --> 00:00:00,500\nHola\n",
                encoding="utf-8",
            )
            (output_dir / "voz.json").write_text(whisper_json, encoding="utf-8")

        with patch(
            "app.modules.subtitles.io.subtitle_builder.subprocess.run",
            side_effect=fake_run,
        ):
            SubtitleBuilder().build(
                audio_path=audio_path,
                output_path=output_path,
                **build_options,
            )
        return whisper_json, whisper_timing_path(output_path).read_text(encoding="utf-8")

    def test_subtitle_builder_records_the_voice_pauses_in_the_timing_json(self):
        with tempfile.TemporaryDirectory() as directory:
            _, written = self._build_subtitles(
                directory,
                voice_pauses=((0.75, 1.25), (2.0, 3.5)),
            )

        data = json.loads(written)
        self.assertEqual(
            [{"start": 0.75, "end": 1.25}, {"start": 2.0, "end": 3.5}],
            data["voice_pauses"],
        )
        self.assertEqual(
            [{"word": " Hola", "start": 0.0, "end": 0.5}],
            data["segments"][0]["words"],
        )

    def test_subtitle_builder_without_pauses_keeps_the_whisper_json(self):
        for build_options in ({}, {"voice_pauses": ()}):
            with self.subTest(build_options=build_options):
                with tempfile.TemporaryDirectory() as directory:
                    original, written = self._build_subtitles(directory, **build_options)

                self.assertEqual(original, written)


class VoicedWordTimingsTest(unittest.TestCase):

    @staticmethod
    def _spans(words):
        return [(word.text, round(word.start, 6), round(word.end, 6)) for word in words]

    def test_without_a_pause_inside_it_is_the_plain_spread(self):
        texts = ("uno", "dos", "tres")

        for pauses in ((), ((0.0, 0.5),), ((2.0, 2.5),)):
            with self.subTest(pauses=pauses):
                self.assertEqual(
                    approximate_word_timings(0.5, 2.0, texts),
                    approximate_voiced_word_timings(0.5, 2.0, texts, pauses),
                )

    def test_words_never_fall_inside_a_pause(self):
        words = approximate_voiced_word_timings(
            0.0, 2.9, ("uno.", "dos", "tres", "cuatro."), ((1.0, 1.5),),
            (True, False, False, True),
        )

        self.assertEqual(
            [("uno.", 0.0, 1.0), ("dos", 1.5, 1.8), ("tres", 1.8, 2.2), ("cuatro.", 2.2, 2.9)],
            self._spans(words),
        )

    def test_more_sentence_ends_than_pauses_cuts_by_letters(self):
        # Two sentence ends for one pause: the cut comes from the letters
        # (1.5 s of voice; "tres" is centred at 1.25 s, after the 1.0 s part).
        words = approximate_voiced_word_timings(
            0.0, 2.0, ("uno.", "dos.", "tres"), ((1.0, 1.5),), (True, True, False),
        )

        self.assertEqual(
            [("uno.", 0.0, 0.5), ("dos.", 0.5, 1.0), ("tres", 1.5, 2.0)],
            self._spans(words),
        )

    def test_a_pause_partly_over_the_span_edge_shortens_it(self):
        words = approximate_voiced_word_timings(1.0, 2.0, ("uno", "dos"), ((0.5, 1.2),))

        self.assertEqual([("uno", 1.2, 1.6), ("dos", 1.6, 2.0)], self._spans(words))


if __name__ == "__main__":
    unittest.main()
