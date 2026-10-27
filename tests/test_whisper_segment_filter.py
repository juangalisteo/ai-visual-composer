import json
import math
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from app.modules.subtitles.io.external_media_subtitles import (
    ExternalMediaSubtitlePreparationService,
)
from app.modules.subtitles.io.subtitle_builder import SubtitleBuilder
from app.modules.subtitles.io.whisper_diagnostics import (
    WhisperDiscardedSegmentDiagnostics,
    WhisperSegmentDiagnostics,
)
from app.modules.subtitles.io.whisper_segment_filter import (
    REPETITION_IN_SILENCE,
    WhisperRepetitionFilter,
)
from app.modules.subtitles.policies.timing import (
    SubtitleTimingResolver,
    whisper_timing_path,
)


RUN = "app.modules.subtitles.io.subtitle_builder.subprocess.run"
INFO = "app.modules.subtitles.io.subtitle_builder.ProgressLogger.info"
PHRASE = "En el precio a pagar en un ajuste de cuentas."


def _segment(segment_id, words, *, seek=0, no_speech_prob=0.0967):
    return {
        "id": segment_id,
        "seek": seek,
        "start": words[0][1],
        "end": words[-1][2],
        "text": "".join(f" {word}" for word, _start, _end in words),
        "tokens": [50364 + segment_id],
        "temperature": 0.0,
        "avg_logprob": -0.17,
        "compression_ratio": 1.37,
        "no_speech_prob": no_speech_prob,
        "words": [
            {"word": f" {word}", "start": start, "end": end, "probability": 0.9}
            for word, start, end in words
        ],
    }


def _spread(text, start, end):
    """Words of ``text`` spread evenly between ``start`` and ``end``."""
    words = text.split()
    step = (end - start) / len(words)
    return [
        (word, round(start + index * step, 2), round(start + (index + 1) * step, 2))
        for index, word in enumerate(words)
    ]


def _instant(text, start):
    """Words of ``text`` squeezed at ``start``, as Whisper aligns silence."""
    words = text.split()
    return [(word, start, start) for word in words[:-1]] + [
        (words[-1], start, round(start + 0.02, 2)),
    ]


def _this_mp4_segments():
    """Synthetic copy of the this.mp4 transcription (30.06 s video)."""
    return [
        _segment(0, _spread("¿Te has cuestionado la naturaleza de tu realidad?", 1.6, 4.9)),
        _segment(1, _spread("¿Te has parado a pensar en tus actos?", 8.32, 10.98)),
        _segment(2, _spread(f"¿{PHRASE[:-1]}?", 13.12, 16.3)),
        _segment(3, _spread("Vamos a ajustar cuentas.", 21.78, 23.88)),
        _segment(4, _instant(PHRASE, 30.0), seek=3000, no_speech_prob=0.9391),
    ]


def _timestamp(seconds):
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _whisper_srt(segments, newline="\r\n"):
    """SRT as Whisper writes it with word timestamps: one cue per segment."""
    return "".join(
        f"{number}{newline}"
        f"{_timestamp(segment['words'][0]['start'])} --> "
        f"{_timestamp(segment['words'][-1]['end'])}{newline}"
        f"{''.join(word['word'] for word in segment['words']).strip()}"
        f"{newline}{newline}"
        for number, segment in enumerate(
            (segment for segment in segments if segment["words"]),
            start=1,
        )
    )


def _srt_cues(content):
    cues = []
    for block in content.strip().split("\n\n"):
        lines = block.splitlines()
        start, end = lines[1].split(" --> ")
        cues.append((start, end, " ".join(lines[2:])))
    return cues


def _fake_whisper(segments, written, *, srt=None, newline="\r\n"):
    def run(command, check):
        output_dir = Path(command[command.index("--output_dir") + 1])
        stem = Path(command[3]).stem
        written["srt"] = (
            srt if srt is not None else _whisper_srt(segments, newline)
        ).encode("utf-8")
        written["json"] = json.dumps({
            "text": "".join(segment["text"] for segment in segments),
            "segments": segments,
            "language": "es",
        }).encode("utf-8")
        (output_dir / f"{stem}.srt").write_bytes(written["srt"])
        (output_dir / f"{stem}.json").write_bytes(written["json"])

    return run


def _build(root, segments, **whisper_options):
    """Run the real SubtitleBuilder over a fake Whisper CLI output."""
    audio_path = root / "source.wav"
    audio_path.write_bytes(b"audio")
    output_path = root / "subtitles.srt"
    written = {}
    with patch(
        RUN,
        side_effect=_fake_whisper(segments, written, **whisper_options),
    ), patch(INFO) as info:
        SubtitleBuilder().build(audio_path=audio_path, output_path=output_path)
    return (
        output_path.read_bytes(),
        whisper_timing_path(output_path).read_bytes(),
        info,
        written,
    )


def test_this_mp4_case_drops_the_repeated_phrase_from_srt_and_timing_json():
    segments = _this_mp4_segments()
    with tempfile.TemporaryDirectory() as directory:
        srt, timing_json, info, written = _build(Path(directory), segments)

    data = json.loads(timing_json)
    assert srt == _whisper_srt(segments[:4]).encode("utf-8")
    assert written["srt"].startswith(srt)
    assert data["segments"] == segments[:4]
    assert data["text"] == "".join(segment["text"] for segment in segments[:4])
    assert data["discarded_segments"] == [
        {"reason": REPETITION_IN_SILENCE, "segment": segments[4]},
    ]
    info.assert_called_once_with(
        "Whisper: 1 segmento descartado (repetición en silencio)"
    )


def test_real_long_repeated_phrase_is_kept():
    segments = _this_mp4_segments()[:4] + [
        _segment(4, _spread(f"¿{PHRASE[:-1]}?", 26.0, 28.6), no_speech_prob=0.9),
    ]
    with tempfile.TemporaryDirectory() as directory:
        srt, timing_json, info, written = _build(Path(directory), segments)

    assert srt == written["srt"]
    assert timing_json == written["json"]
    info.assert_not_called()


def test_short_word_that_repeats_nothing_is_kept():
    segments = [
        _segment(0, _spread("¿Vienes mañana a la reunión?", 1.0, 2.6)),
        _segment(1, [("Sí.", 29.98, 30.0)], seek=3000, no_speech_prob=0.95),
    ]
    with tempfile.TemporaryDirectory() as directory:
        srt, timing_json, info, written = _build(Path(directory), segments)

    assert srt == written["srt"]
    assert timing_json == written["json"]
    info.assert_not_called()


def test_timing_json_stays_coherent_with_the_srt():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        _build(root, _this_mp4_segments())
        cues = _srt_cues((root / "subtitles.srt").read_text(encoding="utf-8"))
        timing = SubtitleTimingResolver().resolve(root / "subtitles.srt")

    assert timing is not None
    assert len(timing.segments) == len(cues) == 4
    for (start, end, text), segment in zip(cues, timing.segments):
        assert start == _timestamp(segment.words[0].start)
        assert end == _timestamp(segment.words[-1].end)
        assert text.split() == [word.text for word in segment.words]
    assert max(word.end for word in timing.words) == 23.88


def test_short_repetition_inside_speech_is_kept_unless_whisper_heard_no_speech():
    rule = WhisperRepetitionFilter()

    def segments(no_speech_prob):
        return [
            _segment(0, _spread("Vamos a ajustar cuentas.", 1.0, 2.5)),
            _segment(
                1,
                _instant("Vamos a ajustar cuentas.", 3.0),
                no_speech_prob=no_speech_prob,
            ),
            _segment(2, _spread("Después llega otra frase.", 4.0, 5.5)),
        ]

    assert rule.discarded_indexes(segments(0.1), 0.6) == ()
    assert rule.discarded_indexes(segments(0.9), 0.6) == (1,)


def test_several_trailing_repetitions_are_all_dropped():
    segments = _this_mp4_segments() + [
        _segment(5, _instant(PHRASE, 30.04), seek=3000, no_speech_prob=0.9391),
    ]
    with tempfile.TemporaryDirectory() as directory:
        srt, timing_json, info, _written = _build(Path(directory), segments)

    assert srt == _whisper_srt(segments[:4]).encode("utf-8")
    assert [entry["segment"]["id"] for entry in json.loads(timing_json)[
        "discarded_segments"
    ]] == [4, 5]
    info.assert_called_once_with(
        "Whisper: 2 segmentos descartados (repetición en silencio)"
    )


def test_srt_that_does_not_match_the_json_is_left_untouched():
    segments = _this_mp4_segments()
    with tempfile.TemporaryDirectory() as directory:
        srt, timing_json, info, written = _build(
            Path(directory),
            segments,
            srt=_whisper_srt(segments[:3]),
        )

    assert srt == written["srt"]
    assert timing_json == written["json"]
    info.assert_not_called()


def test_lf_srt_keeps_its_line_endings():
    segments = _this_mp4_segments()
    with tempfile.TemporaryDirectory() as directory:
        srt, _timing_json, _info, _written = _build(
            Path(directory),
            segments,
            newline="\n",
        )

    assert srt == _whisper_srt(segments[:4], "\n").encode("utf-8")


class _NoRunner:
    def run(self, command):
        raise AssertionError("MP3 must not be extracted before Whisper")


def test_diagnostics_list_the_discarded_segment_without_its_text():
    segments = _this_mp4_segments()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source.mp3"
        source.write_bytes(b"audio")
        sidecar = root / "diagnostics.json"
        with patch(RUN, side_effect=_fake_whisper(segments, {})), patch(INFO):
            prepared = ExternalMediaSubtitlePreparationService(
                runner=_NoRunner(),
            ).prepare(
                media_path=source,
                working_directory=root / "work",
                diagnostics_output_path=sidecar,
            )
        payload = sidecar.read_bytes()

    assert prepared.diagnostics.discarded_segments == (
        WhisperDiscardedSegmentDiagnostics(
            segment=WhisperSegmentDiagnostics(
                segment_id=4,
                seek=3000,
                start=30.0,
                end=30.02,
                no_speech_prob=0.9391,
                avg_logprob=-0.17,
                compression_ratio=1.37,
                temperature=0.0,
            ),
            reason=REPETITION_IN_SILENCE,
        ),
    )
    assert [
        segment.segment_id for segment in prepared.diagnostics.segments
    ] == [0, 1, 2, 3]
    assert max(word.end for word in prepared.timing.words) == 23.88
    assert json.loads(payload)["discarded_segments"] == [
        {
            "segment_id": 4,
            "seek": 3000,
            "start": 30.0,
            "end": 30.02,
            "no_speech_prob": 0.9391,
            "avg_logprob": -0.17,
            "compression_ratio": 1.37,
            "temperature": 0.0,
            "reason": REPETITION_IN_SILENCE,
        },
    ]
    assert b"precio" not in payload


@pytest.mark.parametrize(
    ("value", "error"),
    [
        (0, ValueError),
        (-0.05, ValueError),
        (math.inf, ValueError),
        (math.nan, ValueError),
        (True, TypeError),
        ("0.05", TypeError),
    ],
)
def test_max_seconds_per_word_must_be_a_positive_number(value, error):
    with pytest.raises(error):
        WhisperRepetitionFilter(max_seconds_per_word=value)
