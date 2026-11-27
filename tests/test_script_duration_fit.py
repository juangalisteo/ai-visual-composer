from pathlib import Path

import pytest

from app.core.script_length import DurationMargin
from app.modules.script.models import InvalidScriptOutputError
from app.modules.standard.script_duration_fit import ScriptDurationFit
from app.shared.operation_warnings import OperationWarnings


FIRST_SCRIPT = "Guion primero."
ADJUSTED_SCRIPT = "Guion ajustado."
ADJUSTED_PAUSES = ((1.0, 1.5),)
# The margin of config/ai.json (T0): up to 10 % shorter, no upper limit.
ONLY_BELOW = DurationMargin(below=0.10, above=None)
# A margin with an upper limit, to check that it still works as data.
SYMMETRIC = DurationMargin(below=0.10, above=0.10)


class FakeCollaborators:
    """Measures by file name and records every adjustment and synthesis."""

    def __init__(self, durations, adjust_error=None):
        self.durations = dict(durations)
        self.adjust_error = adjust_error
        self.adjust_calls = []
        self.synthesis_calls = []
        self.measured = []

    def measure(self, path):
        self.measured.append(Path(path).name)
        return self.durations[Path(path).name]

    def adjust(self, *, previous_script, measured_seconds, output_path):
        self.adjust_calls.append(
            (previous_script, measured_seconds, Path(output_path).name)
        )
        if self.adjust_error is not None:
            raise self.adjust_error
        Path(output_path).write_text(ADJUSTED_SCRIPT, encoding="utf-8")
        return ADJUSTED_SCRIPT

    def synthesize(self, text, output_path):
        self.synthesis_calls.append((text, Path(output_path).name))
        Path(output_path).write_bytes(b"voz ajustada")
        return Path(output_path), ADJUSTED_PAUSES


@pytest.fixture
def files(tmp_path):
    script_path = tmp_path / "guion.txt"
    voice_path = tmp_path / "voz.mp3"
    script_path.write_text(FIRST_SCRIPT, encoding="utf-8")
    voice_path.write_bytes(b"voz primera")
    return script_path, voice_path


def _fit(
    collaborators,
    files,
    *,
    target_seconds=10,
    warnings=None,
    margin=ONLY_BELOW,
    **fit_options,
):
    script_path, voice_path = files
    return ScriptDurationFit(
        measure_seconds=collaborators.measure,
        adjust_script=collaborators.adjust,
        synthesize_voice=collaborators.synthesize,
        margin=margin,
        warnings=warnings,
    ).fit(
        script_text=FIRST_SCRIPT,
        target_seconds=target_seconds,
        script_path=script_path,
        voice_path=voice_path,
        voice_pauses=((0.5, 1.0),),
        **fit_options,
    )


def _assert_first_kept(files, result):
    script_path, voice_path = files
    assert result.script_text == FIRST_SCRIPT
    assert result.voice_pauses == ((0.5, 1.0),)
    assert script_path.read_text(encoding="utf-8") == FIRST_SCRIPT
    assert voice_path.read_bytes() == b"voz primera"


def _assert_no_candidates_left(files):
    script_path, _ = files
    assert sorted(path.name for path in script_path.parent.iterdir()) == [
        "guion.txt",
        "voz.mp3",
    ]


@pytest.mark.parametrize("seconds", (45.0, 50.0, 55.0, 80.0, 200.0))
def test_voice_within_the_margin_or_longer_is_kept_without_asking_ollama(
    files, seconds
):
    collaborators = FakeCollaborators({"voz.mp3": seconds})
    warnings = OperationWarnings()

    result = _fit(collaborators, files, target_seconds=50, warnings=warnings)

    _assert_first_kept(files, result)
    assert result.voice_seconds == seconds
    assert not result.adjustment_requested
    assert collaborators.adjust_calls == []
    assert collaborators.synthesis_calls == []
    assert len(warnings) == 0


def test_short_voice_asks_once_for_a_longer_script_and_adopts_it(files, capsys):
    collaborators = FakeCollaborators({"voz.mp3": 40.0, "voz_ajuste.mp3": 47.0})
    warnings = OperationWarnings()

    result = _fit(collaborators, files, target_seconds=50, warnings=warnings)

    script_path, voice_path = files
    assert collaborators.adjust_calls == [(FIRST_SCRIPT, 40.0, "guion_ajuste.txt")]
    assert collaborators.synthesis_calls == [(ADJUSTED_SCRIPT, "voz_ajuste.mp3")]
    assert result.adjustment_requested and result.adjustment_adopted
    assert result.script_text == ADJUSTED_SCRIPT
    assert result.voice_pauses == ADJUSTED_PAUSES
    assert result.voice_seconds == 47.0
    assert script_path.read_text(encoding="utf-8") == ADJUSTED_SCRIPT
    assert voice_path.read_bytes() == b"voz ajustada"
    _assert_no_candidates_left(files)
    assert len(warnings) == 0
    output = capsys.readouterr().out
    assert "La voz dura 40,0 s y se pidieron 50,0 s (-20 %)" in output
    assert "Se pide a Ollama un guion más largo (una sola vez)." in output


def test_adjusted_voice_that_overshoots_fits_because_there_is_no_upper_limit(files):
    # 70 s is 20 s from the target but inside the margin; 42 s is closer in
    # seconds but outside it. The one that fits is kept.
    collaborators = FakeCollaborators({"voz.mp3": 42.0, "voz_ajuste.mp3": 70.0})
    warnings = OperationWarnings()

    result = _fit(collaborators, files, target_seconds=50, warnings=warnings)

    assert result.adjustment_adopted
    assert result.voice_seconds == 70.0
    assert len(warnings) == 0


def test_still_short_keeps_the_better_of_the_two_and_warns_in_one_line(
    files, capsys
):
    collaborators = FakeCollaborators({"voz.mp3": 35.0, "voz_ajuste.mp3": 41.0})
    warnings = OperationWarnings()

    result = _fit(collaborators, files, target_seconds=50, warnings=warnings)

    assert result.adjustment_adopted
    assert result.voice_seconds == 41.0
    assert len(collaborators.adjust_calls) == 1
    assert len(collaborators.synthesis_calls) == 1
    _assert_no_candidates_left(files)
    warning_lines = [
        line
        for line in capsys.readouterr().out.splitlines()
        if "ADVERTENCIA" in line
    ]
    assert warning_lines == [
        "ADVERTENCIA: La voz final dura 41,0 s y se pidieron 50,0 s (-18 %), "
        "fuera del margen (-10 %, sin tope por arriba). Se usa el guion que "
        "más se acerca."
    ]
    assert [warning.family for warning in warnings] == ["DEGRADATION"]


def test_adjusted_script_that_is_shorter_is_discarded_and_the_terminal_warns(
    files, capsys
):
    collaborators = FakeCollaborators({"voz.mp3": 40.0, "voz_ajuste.mp3": 30.0})
    warnings = OperationWarnings()

    result = _fit(collaborators, files, target_seconds=50, warnings=warnings)

    _assert_first_kept(files, result)
    assert result.adjustment_requested and not result.adjustment_adopted
    _assert_no_candidates_left(files)
    output = capsys.readouterr().out
    assert "Se mantiene el primer guion: con el ajustado la voz dura 30,0 s." in output
    assert "ADVERTENCIA: La voz final dura 40,0 s" in output
    assert len(warnings) == 1


def test_a_tie_keeps_the_first_script(files):
    collaborators = FakeCollaborators({"voz.mp3": 40.0, "voz_ajuste.mp3": 40.0})

    result = _fit(collaborators, files, target_seconds=50)

    _assert_first_kept(files, result)
    _assert_no_candidates_left(files)


def test_spent_adjustment_only_warns_without_asking_ollama(files, capsys):
    collaborators = FakeCollaborators({"voz.mp3": 40.0})
    warnings = OperationWarnings()

    result = _fit(
        collaborators,
        files,
        target_seconds=50,
        warnings=warnings,
        adjustment_allowed=False,
    )

    _assert_first_kept(files, result)
    assert not result.adjustment_requested
    assert collaborators.adjust_calls == []
    assert collaborators.synthesis_calls == []
    warning_lines = [
        line
        for line in capsys.readouterr().out.splitlines()
        if "ADVERTENCIA" in line
    ]
    assert warning_lines == [
        "ADVERTENCIA: La voz final dura 40,0 s y se pidieron 50,0 s (-20 %), "
        "fuera del margen (-10 %, sin tope por arriba). Ya se pidió a Ollama "
        "una corrección de extensión antes de la voz: se sigue con este guion."
    ]
    assert len(warnings) == 1


def test_spent_adjustment_with_a_voice_inside_the_margin_says_nothing(files, capsys):
    collaborators = FakeCollaborators({"voz.mp3": 46.0})
    warnings = OperationWarnings()

    result = _fit(
        collaborators,
        files,
        target_seconds=50,
        warnings=warnings,
        adjustment_allowed=False,
    )

    _assert_first_kept(files, result)
    assert "ADVERTENCIA" not in capsys.readouterr().out
    assert len(warnings) == 0


def test_an_upper_limit_in_the_margin_asks_for_a_shorter_script(files, capsys):
    collaborators = FakeCollaborators({"voz.mp3": 13.0, "voz_ajuste.mp3": 10.2})

    result = _fit(collaborators, files, margin=SYMMETRIC)

    assert result.adjustment_adopted
    assert result.voice_seconds == 10.2
    assert "Se pide a Ollama un guion más corto (una sola vez)." in (
        capsys.readouterr().out
    )


def test_an_upper_limit_in_the_margin_is_described_in_the_warning(files, capsys):
    collaborators = FakeCollaborators({"voz.mp3": 14.0, "voz_ajuste.mp3": 11.5})

    _fit(collaborators, files, margin=SYMMETRIC)

    assert "fuera del margen (-10 % / +10 %)" in capsys.readouterr().out


def test_malformed_adjustment_keeps_the_first_script_without_new_voice(files, capsys):
    error = InvalidScriptOutputError(
        reason="model_comment_not_allowed",
        field="script",
        original_response="Aqui tienes el guion.",
        parser_id="script_generation_contract_v1",
        model="test-model",
        prompt_id="prompt-id",
    )
    collaborators = FakeCollaborators({"voz.mp3": 40.0}, adjust_error=error)
    warnings = OperationWarnings()

    result = _fit(collaborators, files, target_seconds=50, warnings=warnings)

    _assert_first_kept(files, result)
    _assert_no_candidates_left(files)
    assert collaborators.synthesis_calls == []
    assert len(warnings) == 1
    assert "Ollama no devolvió un guion ajustado válido" in capsys.readouterr().out
