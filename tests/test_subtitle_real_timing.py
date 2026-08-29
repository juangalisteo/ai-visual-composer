import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.modules.audio.voice_builder import VoiceBuilder
from app.modules.subtitles.models.single_line_model import SingleLineModel
from app.modules.subtitles.models.word_by_word_model import WordByWordModel
from app.modules.subtitles.subtitle_builder import SubtitleBuilder
from app.modules.subtitles.timing import (
    EDGE_TTS_TICKS_PER_SECOND,
    EdgeWordBoundaryParser,
    SpeechSegment,
    SubtitleTiming,
    SubtitleTimingResolver,
    WhisperTimingParser,
    WordTiming,
    edge_word_boundaries_path,
    whisper_timing_path,
)


class SubtitleRealTimingTest(unittest.TestCase):

    def test_edge_word_boundary_parser_converts_ticks_to_seconds(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata_path = Path(temp_dir) / "voz_word_boundaries.jsonl"
            metadata_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "WordBoundary",
                                "offset": 0,
                                "duration": EDGE_TTS_TICKS_PER_SECOND // 2,
                                "text": "Hola",
                            }
                        ),
                        json.dumps(
                            {
                                "type": "WordBoundary",
                                "offset": EDGE_TTS_TICKS_PER_SECOND,
                                "duration": EDGE_TTS_TICKS_PER_SECOND // 4,
                                "text": "mundo",
                            }
                        ),
                    ]
                ),
                encoding="utf-8",
            )

            timing = EdgeWordBoundaryParser().parse(metadata_path)

        self.assertEqual(timing.source, "edge_tts")
        self.assertEqual(timing.reliability, "primary")
        self.assertEqual(timing.word_count, 2)
        self.assertEqual(timing.words[0].start, 0.0)
        self.assertEqual(timing.words[0].end, 0.5)
        self.assertEqual(timing.words[1].start, 1.0)
        self.assertEqual(timing.words[1].end, 1.25)

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

    def test_resolver_prefers_edge_over_whisper(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            audio_path = temp_path / "voz.mp3"
            subtitle_path = temp_path / "subtitulos.srt"
            audio_path.write_bytes(b"audio")
            subtitle_path.write_text("", encoding="utf-8")

            edge_word_boundaries_path(audio_path).write_text(
                json.dumps(
                    {
                        "type": "WordBoundary",
                        "offset": 0,
                        "duration": EDGE_TTS_TICKS_PER_SECOND,
                        "text": "Edge",
                    }
                ),
                encoding="utf-8",
            )
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

        self.assertEqual(timing.source, "edge_tts")
        self.assertEqual(timing.words[0].text, "Edge")

    def test_resolver_falls_back_to_whisper_when_edge_is_missing(self):
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
        self.assertIn("edge_tts:missing", timing.fallback_reason)

    def test_resolver_falls_back_to_whisper_when_edge_metadata_is_invalid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            audio_path = temp_path / "voz.mp3"
            subtitle_path = temp_path / "subtitulos.srt"
            audio_path.write_bytes(b"audio")
            subtitle_path.write_text("", encoding="utf-8")

            edge_word_boundaries_path(audio_path).write_text(
                "{invalid",
                encoding="utf-8",
            )
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
        self.assertIn("edge_tts:Metadata Edge TTS inválida.", timing.fallback_reason)

    def test_resolver_returns_none_when_no_timing_sidecar_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            subtitle_path = Path(temp_dir) / "subtitulos.srt"
            subtitle_path.write_text("", encoding="utf-8")

            timing = SubtitleTimingResolver().resolve(
                subtitle_path=subtitle_path
            )

        self.assertIsNone(timing)

    def test_word_by_word_uses_real_word_timing_and_preserves_gap(self):
        model = WordByWordModel(
            {
                "min_duration": 0.3,
                "max_duration": 1.2,
                "remove_extra_commas": True,
            }
        )
        timing = SubtitleTiming(
            source="edge_tts",
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
        self.assertIn("00:00:00,700 --> 00:00:01,000", blocks[1])

    def test_word_by_word_preserves_legacy_distribution_without_timing(self):
        model = WordByWordModel(
            {
                "min_duration": 0.3,
                "max_duration": 1.2,
                "remove_extra_commas": True,
            }
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
            }
        )
        timing = SubtitleTiming(
            source="edge_tts",
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
                "app.modules.subtitles.subtitle_builder.subprocess.run",
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

    def test_voice_builder_requests_edge_word_boundaries_sidecar(self):
        calls = []

        class FakeCommunicate:

            def __init__(self, **kwargs):
                calls.append(("init", kwargs))

            async def save(self, audio_path, metadata_path=None):
                calls.append(
                    (
                        "save",
                        audio_path,
                        metadata_path,
                    )
                )
                Path(audio_path).write_bytes(b"audio")
                Path(metadata_path).write_text(
                    "",
                    encoding="utf-8",
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "voz.mp3"
            builder = object.__new__(
                VoiceBuilder
            )
            builder.voice = "es-ES-AlvaroNeural"
            builder.rate = "+0%"
            builder.volume = "+0%"

            with patch(
                "app.modules.audio.voice_builder.edge_tts.Communicate",
                FakeCommunicate,
            ):
                asyncio.run(
                    builder._generate_audio(
                        text="Hola mundo",
                        output_path=output_path,
                    )
                )

        self.assertEqual(calls[0][1]["boundary"], "WordBoundary")
        self.assertEqual(
            calls[1][2],
            str(edge_word_boundaries_path(output_path)),
        )

    def test_real_micro_cue_merges_with_next_word(self):
        original_words = (
            WordTiming("y", 9.063, 9.089, source="edge_tts"),
            WordTiming("la", 9.103, 9.208, source="edge_tts"),
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
            remove_extra_commas=False,
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

    def test_micro_cue_policy_applies_to_edge_timing(self):
        model = self._word_by_word_model(
            fps=30
        )

        blocks = model.optimize(
            [],
            timing=SubtitleTiming(
                source="edge_tts",
                segments=(
                    SpeechSegment(
                        start=1.0,
                        end=1.2,
                        words=(
                            WordTiming("y", 1.0, 1.026, source="edge_tts"),
                            WordTiming("la", 1.04, 1.2, source="edge_tts"),
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
        remove_extra_commas=True,
        micro_cues_enabled=True
    ):
        return WordByWordModel(
            {
                "min_duration": 0.3,
                "max_duration": 1.2,
                "remove_extra_commas": remove_extra_commas,
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
        source="edge_tts"
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


if __name__ == "__main__":
    unittest.main()
