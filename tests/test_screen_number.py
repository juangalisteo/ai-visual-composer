"""Decimal comma on screen, point in files and in the record (A2-E)."""

import pytest

from app.core.script_length import DurationMargin
from app.shared.progress_logger import ProgressLogger
from app.shared.screen_number import screen_decimal
from app.shared.time_formatter import TimeFormatter


@pytest.mark.parametrize(
    ("value", "places", "expected"),
    (
        (5.5, 2, "5,50"),
        (0.007, 3, "0,007"),
        (12, 1, "12,0"),
        (-1.25, 2, "-1,25"),
        (12.5, None, "12,5"),
        (10, None, "10"),
        ("3.0", 2, "3,00"),
    ),
)
def test_screen_decimal_uses_a_comma(value, places, expected):
    assert screen_decimal(value, places) == expected


@pytest.mark.parametrize(
    ("seconds", "screen", "record"),
    (
        (5.5, "5,50 s", "5.50 s"),
        (82.234, "1 min 22,23 s", "1 min 22.23 s"),
        (3725.5, "1 h 2 min 5,50 s", "1 h 2 min 5.50 s"),
        (-3, "0,00 s", "0.00 s"),
    ),
)
def test_elapsed_time_on_screen_and_in_the_record(seconds, screen, record):
    assert TimeFormatter.format(seconds) == screen
    assert TimeFormatter.format(seconds, screen=False) == record


def test_finished_step_on_screen_has_a_comma_and_in_the_record_a_point(capsys, run_log_text):
    ProgressLogger.finish("Finalizado", 1.5)
    ProgressLogger.detail_finish("FFMPEG PREPARADO", 1.5)

    assert capsys.readouterr().out == "Finalizado (1,50 s)\n"
    record = run_log_text()
    assert "Finalizado (1,50 s)" in record
    assert "FFMPEG PREPARADO (1.50 s)" in record


def test_script_margin_is_described_with_a_comma():
    margin = DurationMargin(below=0.125, above=None)
    assert "12,5 %" in margin.describe()
