"""Margin of a topic script's duration, declared in config/ai.json (T0)."""

import json
import math
from pathlib import Path

import pytest

from app.core.script_length import (
    DurationMargin,
    ScriptLengthBudget,
    SpeechPacing,
    script_duration_margin,
)
from app.shared.operational_error import OperationalError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ONLY_BELOW = DurationMargin(below=0.10, above=None)
PACING = SpeechPacing(letters_per_second=13.0, words_per_second=2.5)


@pytest.mark.parametrize(
    ("seconds", "fits"),
    (
        (44.99, False),
        (45.0, True),
        (50.0, True),
        (55.01, True),
        (500.0, True),
    ),
)
def test_only_a_short_voice_is_outside_a_margin_without_upper_limit(seconds, fits):
    assert ONLY_BELOW.fits(seconds, 50) is fits


@pytest.mark.parametrize(
    ("seconds", "fits"),
    ((44.99, False), (45.0, True), (55.0, True), (55.01, False)),
)
def test_an_upper_limit_is_applied_when_declared(seconds, fits):
    assert DurationMargin(below=0.10, above=0.10).fits(seconds, 50) is fits


def test_float_rounding_at_the_minimum_still_fits():
    assert ONLY_BELOW.fits(45.0 - 5e-10, 50)
    assert not ONLY_BELOW.fits(45.0 - 1e-6, 50)


def test_rescaled_budget_keeps_the_margin():
    budget = ScriptLengthBudget.for_duration(
        50, PACING, DurationMargin(below=0.2, above=0.3)
    )

    rescaled = budget.rescaled(words=100, observed_seconds=40)

    assert rescaled.margin == budget.margin
    assert (rescaled.min_words, rescaled.target_words, rescaled.max_words) == (
        100,
        125,
        162,
    )


def test_shortfall_is_the_distance_outside_the_margin():
    assert ONLY_BELOW.shortfall(40, 50) == pytest.approx(5.0)
    assert ONLY_BELOW.shortfall(46, 50) == 0.0
    assert ONLY_BELOW.shortfall(90, 50) == 0.0
    assert DurationMargin(below=0.10, above=0.20).shortfall(66, 50) == pytest.approx(6.0)
    assert DurationMargin(below=0.0, above=0.0).shortfall(49, 50) == pytest.approx(1.0)


def test_limits_in_seconds():
    assert ONLY_BELOW.minimum_seconds(50) == pytest.approx(45.0)
    assert ONLY_BELOW.maximum_seconds(50) is None
    assert DurationMargin(below=0.2, above=0.05).maximum_seconds(40) == pytest.approx(42.0)


def test_describe_for_the_terminal():
    assert ONLY_BELOW.describe() == "-10 %, sin tope por arriba"
    assert DurationMargin(below=0.125, above=0.05).describe() == "-12,5 % / +5 %"


def test_budget_word_range_follows_the_margin():
    open_budget = ScriptLengthBudget.for_duration(50, PACING, ONLY_BELOW)
    closed_budget = ScriptLengthBudget.for_duration(
        50, PACING, DurationMargin(below=0.20, above=0.10)
    )

    assert (open_budget.min_words, open_budget.target_words, open_budget.max_words) == (
        112,
        125,
        None,
    )
    assert (
        closed_budget.min_words,
        closed_budget.target_words,
        closed_budget.max_words,
    ) == (100, 125, 138)
    assert open_budget.fits(45.0) and not open_budget.fits(44.9)
    assert open_budget.fits(400.0)


def test_budget_requires_a_margin():
    with pytest.raises(TypeError):
        ScriptLengthBudget(
            duration_seconds=10,
            target_words=25,
            min_words=22,
            max_words=None,
            pacing=PACING,
            margin=None,
        )


def test_the_project_declares_ten_percent_below_and_no_upper_limit():
    ai_config = json.loads(
        (REPOSITORY_ROOT / "config" / "ai.json").read_text(encoding="utf-8")
    )

    assert script_duration_margin(ai_config) == DurationMargin(below=0.10, above=None)


def test_configured_values_are_read_as_declared():
    margin = script_duration_margin(
        {"script": {"duration_margin": {"below": 0.25, "above": 0.5}}}
    )

    assert margin == DurationMargin(below=0.25, above=0.5)


@pytest.mark.parametrize(
    "ai_config",
    (
        {},
        {"model": "m"},
        {"script": None},
        {"script": {"model": "m"}},
        {"script": {"duration_margin": None}},
        None,
        [],
    ),
)
def test_missing_margin_is_a_config_error_naming_the_file_and_the_key(ai_config):
    with pytest.raises(OperationalError) as raised:
        script_duration_margin(ai_config)

    context = raised.value.context
    assert context.family == "CONFIG"
    assert context.resource == "config/ai.json"
    assert context.technical_metadata["key"] == "script.duration_margin"
    assert context.user_message == (
        "Configuración del guion no válida en config/ai.json: falta "
        "«script.duration_margin», el margen aceptado para la duración de un "
        "guion generado por tema."
    )
    assert "config/ai.json" in context.recommended_action


@pytest.mark.parametrize(
    "value",
    (
        0.10,
        "0.10",
        [],
        {"below": 0.10},
        {"above": None},
        {"below": 0.10, "above": None, "extra": 1},
    ),
)
def test_margin_with_a_wrong_shape_is_a_config_error(value):
    with pytest.raises(OperationalError) as raised:
        script_duration_margin({"script": {"duration_margin": value}})

    context = raised.value.context
    assert context.family == "CONFIG"
    assert "«script.duration_margin» debe ser un objeto con «below» y «above»" in (
        context.user_message
    )


@pytest.mark.parametrize(
    ("below", "above", "key"),
    (
        (None, None, "below"),
        (True, None, "below"),
        ("0.1", None, "below"),
        (-0.01, None, "below"),
        (1, None, "below"),
        (1.5, None, "below"),
        (math.nan, None, "below"),
        (math.inf, None, "below"),
        (0.1, False, "above"),
        (0.1, "x", "above"),
        (0.1, -0.2, "above"),
        (0.1, 1.0, "above"),
    ),
)
def test_invalid_numbers_are_a_config_error(below, above, key):
    with pytest.raises(OperationalError) as raised:
        script_duration_margin(
            {"script": {"duration_margin": {"below": below, "above": above}}}
        )

    context = raised.value.context
    assert context.family == "CONFIG"
    assert context.resource == "config/ai.json"
    assert (
        f"«script.duration_margin.{key}» debe ser un número de 0 a 1 sin llegar "
        "a 1 (0.10 es un 10 %)."
    ) in context.user_message


def test_zero_is_a_valid_margin():
    margin = script_duration_margin(
        {"script": {"duration_margin": {"below": 0, "above": 0}}}
    )

    assert margin.fits(50, 50)
    assert not margin.fits(49.9, 50)
    assert not margin.fits(50.1, 50)
