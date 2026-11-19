from pathlib import Path

import pytest

from app.modules.script.models import InvalidScriptOutputError
from app.modules.standard.script_duration_fit import ScriptDurationFit
from app.shared.operation_warnings import OperationWarnings


FIRST_SCRIPT = "Guion primero."
ADJUSTED_SCRIPT = "Guion ajustado."
ADJUSTED_PAUSES = ((1.0, 1.5),)


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


def _fit(collaborators, files, *, target_seconds=10, warnings=None):
    script_path, voice_path = files
    return ScriptDurationFit(
        measure_seconds=collaborators.measure,
        adjust_script=collaborators.adjust,
        synthesize_voice=collaborators.synthesize,
        warnings=warnings,
    ).fit(
        script_text=FIRST_SCRIPT,
        target_seconds=target_seconds,
        script_path=script_path,
        voice_path=voice_path,
        voice_pauses=((0.5, 1.0),),
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


@pytest.mark.parametrize("seconds", (9.0, 10.0, 11.0))
def test_voice_within_ten_percent_is_kept_without_asking_ollama(files, seconds):
    collaborators = FakeCollaborators({"voz.mp3": seconds})

    result = _fit(collaborators, files)

    _assert_first_kept(files, result)
    assert result.voice_seconds == seconds
    assert not result.adjustment_requested
    assert collaborators.adjust_calls == []
    assert collaborators.synthesis_calls == []


def test_long_voice_asks_once_for_a_shorter_script_and_adopts_the_closer_one(
    files, capsys
):
    collaborators = FakeCollaborators({"voz.mp3": 13.0, "voz_ajuste.mp3": 10.2})
    warnings = OperationWarnings()

    result = _fit(collaborators, files, warnings=warnings)

    script_path, voice_path = files
    assert collaborators.adjust_calls == [(FIRST_SCRIPT, 13.0, "guion_ajuste.txt")]
    assert collaborators.synthesis_calls == [(ADJUSTED_SCRIPT, "voz_ajuste.mp3")]
    assert result.adjustment_adopted
    assert result.script_text == ADJUSTED_SCRIPT
    assert result.voice_pauses == ADJUSTED_PAUSES
    assert result.voice_seconds == 10.2
    assert script_path.read_text(encoding="utf-8") == ADJUSTED_SCRIPT
    assert voice_path.read_bytes() == b"voz ajustada"
    _assert_no_candidates_left(files)
    assert len(warnings) == 0
    output = capsys.readouterr().out
    assert "La voz dura 13,0 s y se pidieron 10,0 s (+30 %)" in output
    assert "Se pide a Ollama un guion más corto (una sola vez)." in output


def test_short_voice_asks_for_a_longer_script(files, capsys):
    collaborators = FakeCollaborators({"voz.mp3": 8.0, "voz_ajuste.mp3": 9.6})

    result = _fit(collaborators, files)

    assert result.adjustment_adopted
    assert "Se pide a Ollama un guion más largo (una sola vez)." in (
        capsys.readouterr().out
    )


def test_adjusted_script_that_is_farther_is_discarded_and_the_terminal_warns(
    files, capsys
):
    collaborators = FakeCollaborators({"voz.mp3": 13.0, "voz_ajuste.mp3": 14.0})
    warnings = OperationWarnings()

    result = _fit(collaborators, files, warnings=warnings)

    _assert_first_kept(files, result)
    assert result.adjustment_requested and not result.adjustment_adopted
    _assert_no_candidates_left(files)
    assert len(collaborators.adjust_calls) == 1
    output = capsys.readouterr().out
    assert "ADVERTENCIA: La voz final dura 13,0 s y se pidieron 10,0 s (+30 %)" in output
    assert "fuera del margen de ±10 %" in output
    assert [warning.family for warning in warnings] == ["DEGRADATION"]


def test_a_tie_keeps_the_first_script(files):
    collaborators = FakeCollaborators({"voz.mp3": 12.5, "voz_ajuste.mp3": 12.5})

    result = _fit(collaborators, files)

    _assert_first_kept(files, result)
    _assert_no_candidates_left(files)


def test_closer_but_still_out_of_range_is_adopted_with_a_warning_and_no_second_try(
    files,
):
    collaborators = FakeCollaborators({"voz.mp3": 14.0, "voz_ajuste.mp3": 11.5})
    warnings = OperationWarnings()

    result = _fit(collaborators, files, warnings=warnings)

    assert result.adjustment_adopted
    assert result.voice_seconds == 11.5
    assert len(collaborators.adjust_calls) == 1
    assert len(collaborators.synthesis_calls) == 1
    assert len(warnings) == 1


def test_malformed_adjustment_keeps_the_first_script_without_new_voice(files, capsys):
    error = InvalidScriptOutputError(
        reason="model_comment_not_allowed",
        field="script",
        original_response="Aqui tienes el guion.",
        parser_id="script_generation_contract_v1",
        model="test-model",
        prompt_id="prompt-id",
    )
    collaborators = FakeCollaborators({"voz.mp3": 13.0}, adjust_error=error)
    warnings = OperationWarnings()

    result = _fit(collaborators, files, warnings=warnings)

    _assert_first_kept(files, result)
    _assert_no_candidates_left(files)
    assert collaborators.synthesis_calls == []
    assert len(warnings) == 1
    assert "Ollama no devolvió un guion ajustado válido" in capsys.readouterr().out
