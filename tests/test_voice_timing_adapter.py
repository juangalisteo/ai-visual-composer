import inspect
import unittest

from app.modules.audio.tts_contracts import TtsWordTiming
from app.modules.audio.voice_timing_adapter import VoiceTimingAdapter


class VoiceTimingAdapterTest(unittest.TestCase):

    def setUp(self):
        self.adapter = VoiceTimingAdapter()

    def test_adapts_neutral_word_timings_to_primary_subtitle_timing(self):
        timing = self.adapter.adapt(
            (
                TtsWordTiming("Hola", 0.0, 0.4),
                TtsWordTiming("mundo", 0.5, 0.9),
            )
        )

        self.assertEqual("tts", timing.source)
        self.assertEqual("primary", timing.reliability)
        self.assertEqual(0.9, timing.duration)
        self.assertEqual(1, len(timing.segments))
        self.assertEqual(
            (("Hola", 0.0, 0.4, "tts"), ("mundo", 0.5, 0.9, "tts")),
            tuple(
                (word.text, word.start, word.end, word.source)
                for word in timing.words
            ),
        )

    def test_absent_or_empty_timings_remain_absent(self):
        self.assertIsNone(self.adapter.adapt(None))
        self.assertIsNone(self.adapter.adapt(()))

    def test_rejects_invalid_word_types_and_overlapping_intervals(self):
        with self.assertRaisesRegex(TypeError, "TtsWordTiming"):
            self.adapter.adapt((object(),))
        with self.assertRaisesRegex(ValueError, "non-overlapping"):
            self.adapter.adapt(
                (
                    TtsWordTiming("uno", 0.0, 0.6),
                    TtsWordTiming("dos", 0.5, 1.0),
                )
            )

    def test_adapter_contract_has_no_provider_or_runtime_dependencies(self):
        from app.modules.audio import voice_timing_adapter

        source = inspect.getsource(voice_timing_adapter).lower()
        for forbidden in (
            "kokoro",
            "piper",
            "projectmanager",
            "start.py",
            "display_name",
            "guion",
            "imagen",
            "video",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
