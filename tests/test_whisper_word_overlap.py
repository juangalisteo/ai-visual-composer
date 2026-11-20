"""Whisper word times that overlap only by float rounding are kept.

The times of the rounding cases come from real Davefx + Whisper runs: a word
that ends at 27.720000000000002 s (last word of a segment) and the next one,
first of the following segment, that starts at 27.72 s.
"""

import json
from pathlib import Path

import pytest

from app.modules.subtitles.io.external_media_subtitles import (
    ExternalMediaSubtitlePreparationService,
)
from app.modules.subtitles.io.whisper_settings import (
    whisper_word_overlap_tolerance,
)
from app.modules.subtitles.policies.timing import (
    SubtitleTimingResolver,
    WhisperTimingParser,
    whisper_timing_path,
)
from app.shared.operational_error import OperationalError


REAL_CONFIG = Path(__file__).resolve().parents[1] / "config" / "whisper.json"

ROUNDING_SEGMENTS = [
    {
        "start": 22.04,
        "end": 27.52,
        "words": [
            {"word": " presente.", "start": 25.94, "end": 26.38},
            {"word": " Tesla", "start": 27.12, "end": 27.44},
            {"word": " no", "start": 27.44, "end": 27.720000000000002},
        ],
    },
    {
        "start": 27.72,
        "end": 30.26,
        "words": [
            {"word": " solo", "start": 27.72, "end": 27.94},
            {"word": " cambió", "start": 27.94, "end": 28.28},
        ],
    },
]


def _write_whisper(directory, segments, **extra):
    subtitle_path = Path(directory) / "subtitles.srt"
    subtitle_path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nprueba\n",
        encoding="utf-8",
    )
    whisper_timing_path(subtitle_path).write_text(
        json.dumps({"segments": segments, **extra}),
        encoding="utf-8",
    )
    return subtitle_path


def _times(timing):
    return [(word.text, word.start, word.end) for word in timing.words]


def _segments(*words):
    return [{"words": [
        {"word": text, "start": start, "end": end}
        for text, start, end in words
    ]}]


def _write_config(root, content):
    config = Path(root) / "config"
    config.mkdir(exist_ok=True)
    (config / "whisper.json").write_text(content, encoding="utf-8")


def test_rounding_overlap_between_segments_keeps_every_word_time(tmp_path):
    subtitle_path = _write_whisper(tmp_path, ROUNDING_SEGMENTS)

    timing = SubtitleTimingResolver(0.001).resolve(subtitle_path)

    assert timing is not None
    assert _times(timing) == [
        ("presente.", 25.94, 26.38),
        ("Tesla", 27.12, 27.44),
        ("no", 27.44, 27.720000000000002),
        ("solo", 27.720000000000002, 27.94),
        ("cambió", 27.94, 28.28),
    ]


def test_without_tolerance_the_rounding_overlap_is_rejected_as_before(tmp_path):
    subtitle_path = _write_whisper(tmp_path, ROUNDING_SEGMENTS)

    assert SubtitleTimingResolver(0.0).resolve(subtitle_path) is None
    with pytest.raises(ValueError, match="sin solaparse"):
        WhisperTimingParser(0.0).parse(whisper_timing_path(subtitle_path))


def test_real_overlap_larger_than_the_tolerance_is_rejected(tmp_path):
    subtitle_path = _write_whisper(tmp_path, _segments(
        ("uno", 0.0, 1.0),
        ("dos", 0.998, 1.5),
    ))

    assert SubtitleTimingResolver(0.001).resolve(subtitle_path) is None
    with pytest.raises(ValueError, match="sin solaparse"):
        WhisperTimingParser(0.001).parse(whisper_timing_path(subtitle_path))


def test_overlap_equal_to_the_tolerance_is_rounding(tmp_path):
    subtitle_path = _write_whisper(tmp_path, _segments(
        ("uno", 0.0, 1.5),
        ("dos", 1.0, 2.0),
    ))

    timing = SubtitleTimingResolver(0.5).resolve(subtitle_path)

    assert _times(timing) == [("uno", 0.0, 1.5), ("dos", 1.5, 2.0)]
    assert SubtitleTimingResolver(0.4).resolve(subtitle_path) is None


def test_word_inside_the_overlap_also_moves_its_end(tmp_path):
    subtitle_path = _write_whisper(tmp_path, _segments(
        ("uno", 0.0, 1.0004),
        ("y", 1.0, 1.0002),
        ("dos", 1.1, 1.5),
    ))

    timing = SubtitleTimingResolver(0.001).resolve(subtitle_path)

    assert _times(timing) == [
        ("uno", 0.0, 1.0004),
        ("y", 1.0004, 1.0004),
        ("dos", 1.1, 1.5),
    ]


def test_rounding_overlap_inside_one_segment_is_kept(tmp_path):
    subtitle_path = _write_whisper(tmp_path, _segments(
        ("sino", 27.66, 27.96),
        ("que", 27.96, 28.240000000000002),
        ("también", 28.24, 28.54),
    ))

    timing = SubtitleTimingResolver(0.001).resolve(subtitle_path)

    assert _times(timing)[2] == ("también", 28.240000000000002, 28.54)
    assert timing.word_count == 3


def test_without_overlap_the_tolerance_changes_nothing(tmp_path):
    segments = [
        {"start": 0.0, "end": 1.2, "words": [
            {"word": " uno", "start": 0.0, "end": 0.2, "probability": 0.9},
            {"word": " dos", "start": 0.2, "end": 0.6, "probability": 0.8},
        ]},
        {"start": 0.9, "end": 1.6, "words": [
            {"word": " tres", "start": 0.9, "end": 1.2},
            {"word": " cuatro", "start": 1.2, "end": 1.2},
            {"word": " cinco", "start": 1.2, "end": 1.6},
        ]},
    ]
    subtitle_path = _write_whisper(
        tmp_path,
        segments,
        voice_pauses=[{"start": 0.6, "end": 0.9}],
    )

    strict = SubtitleTimingResolver(0.0).resolve(subtitle_path)
    tolerant = SubtitleTimingResolver(0.001).resolve(subtitle_path)

    assert tolerant == strict


def test_resolver_reads_the_tolerance_from_config_whisper_json(
    tmp_path,
    monkeypatch,
):
    subtitle_path = _write_whisper(tmp_path, ROUNDING_SEGMENTS)
    monkeypatch.chdir(tmp_path)

    _write_config(tmp_path, '{"word_overlap_tolerance_seconds": 0}')
    assert SubtitleTimingResolver().resolve(subtitle_path) is None

    _write_config(tmp_path, '{"word_overlap_tolerance_seconds": 0.001}')
    assert SubtitleTimingResolver().resolve(subtitle_path).word_count == 5


def test_the_project_declares_a_one_millisecond_tolerance():
    assert whisper_word_overlap_tolerance(REAL_CONFIG) == 0.001


def _config_error(path):
    with pytest.raises(OperationalError) as context:
        whisper_word_overlap_tolerance(path)
    error = context.value
    assert error.context.family == "CONFIG"
    return error.context


def test_missing_config_file_is_a_config_error_with_the_relative_path(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    context = _config_error(Path("config/whisper.json"))

    assert context.resource == "config/whisper.json"
    assert "«config/whisper.json»" in context.user_message
    assert "Falta el archivo" in context.user_message


def test_missing_key_is_a_config_error_naming_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, "{}")

    context = _config_error(Path("config/whisper.json"))

    assert context.resource == "config/whisper.json"
    assert (
        "«config/whisper.json» no declara «word_overlap_tolerance_seconds»."
        == context.user_message
    )


@pytest.mark.parametrize(
    "value",
    ["-0.001", "true", '"0.001"', "null", "[0.001]"],
)
def test_invalid_tolerance_is_a_config_error(tmp_path, monkeypatch, value):
    monkeypatch.chdir(tmp_path)
    _write_config(
        tmp_path,
        '{"word_overlap_tolerance_seconds": ' + value + "}",
    )

    context = _config_error(Path("config/whisper.json"))

    assert "mayor o igual que 0" in context.user_message


def test_infinite_tolerance_is_a_config_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, '{"word_overlap_tolerance_seconds": Infinity}')

    context = _config_error(Path("config/whisper.json"))

    assert "mayor o igual que 0" in context.user_message


def test_integer_zero_tolerance_is_valid(tmp_path):
    _write_config(tmp_path, '{"word_overlap_tolerance_seconds": 0}')

    value = whisper_word_overlap_tolerance(tmp_path / "config" / "whisper.json")

    assert value == 0.0
    assert isinstance(value, float)


@pytest.mark.parametrize(
    ("content", "fragment"),
    [
        ("{", "no es un JSON válido (línea 1)"),
        ("[0.001]", "debe ser un objeto JSON"),
    ],
)
def test_malformed_config_is_a_config_error(
    tmp_path,
    monkeypatch,
    content,
    fragment,
):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, content)

    context = _config_error(Path("config/whisper.json"))

    assert fragment in context.user_message


def test_resolver_does_not_hide_a_config_error(tmp_path, monkeypatch):
    subtitle_path = _write_whisper(tmp_path, ROUNDING_SEGMENTS)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(OperationalError):
        SubtitleTimingResolver().resolve(subtitle_path)


class _AudioExtractionRunner:

    def run(self, command):
        Path(command[-1]).write_bytes(b"audio")


class _WhisperBuilder:
    """Writes the SRT and the Whisper JSON a real run would leave."""

    def __init__(self, segments):
        self.segments = segments

    def build(self, audio_path, output_path):
        output_path = Path(output_path)
        output_path.write_text(
            "1\n00:00:22,040 --> 00:00:30,260\nprueba\n",
            encoding="utf-8",
        )
        whisper_timing_path(output_path).write_text(
            json.dumps({"segments": self.segments}),
            encoding="utf-8",
        )
        return output_path


def _studio_video_timing(root, segments, tolerance):
    Path(root).mkdir()
    video_path = Path(root) / "source.mp4"
    video_path.write_bytes(b"video")
    return ExternalMediaSubtitlePreparationService(
        runner=_AudioExtractionRunner(),
        subtitle_builder=_WhisperBuilder(segments),
        timing_resolver=SubtitleTimingResolver(tolerance),
    ).prepare(video_path, Path(root) / "working").timing


def test_studio_video_only_works_with_the_rounding_overlap(tmp_path):
    with pytest.raises(RuntimeError, match="word timestamps utilizables"):
        _studio_video_timing(tmp_path / "strict", ROUNDING_SEGMENTS, 0.0)

    timing = _studio_video_timing(tmp_path / "tolerant", ROUNDING_SEGMENTS, 0.001)

    assert timing.word_count == 5


def test_studio_video_only_is_unchanged_without_overlap(tmp_path):
    segments = [dict(ROUNDING_SEGMENTS[0]), ROUNDING_SEGMENTS[1]]
    segments[0]["words"] = ROUNDING_SEGMENTS[0]["words"][:2]

    strict = _studio_video_timing(tmp_path / "strict", segments, 0.0)
    tolerant = _studio_video_timing(tmp_path / "tolerant", segments, 0.001)

    assert tolerant == strict
