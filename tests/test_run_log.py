"""Record of each run and technical lines out of the screen (A2-D, fallo 13)."""

import subprocess
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

import main
from app.modules.subtitles.io.subtitle_builder import SubtitleBuilder
from app.modules.video.transitions.transition_builder import TransitionBuilder
from app.shared.operational_error import OperationalError
from app.shared.progress_logger import ProgressLogger
from app.shared.run_log import RUN_LOG, RunLog


def _clock():
    return datetime(2026, 11, 27, 9, 5, 7)


def test_record_writes_each_line_with_the_time(tmp_path):
    record = RunLog(clock=_clock)
    path = tmp_path / "nueva" / "registro.txt"

    assert record.start(path) is True
    record.write("PASO...\n\n  detalle  ")
    record.stop()

    assert path.read_text(encoding="utf-8") == (
        "[09:05:07] Registro de la ejecución · 2026-11-27 09:05:07\n"
        "[09:05:07] PASO...\n"
        "\n"
        "[09:05:07]   detalle\n"
    )
    assert record.active is False and record.path is None


def test_without_a_record_writing_does_nothing(tmp_path):
    record = RunLog(clock=_clock)
    record.write("nada")
    assert record.active is False
    assert list(tmp_path.iterdir()) == []


def test_a_record_that_cannot_be_created_returns_false(tmp_path):
    blocker = tmp_path / "archivo"
    blocker.write_text("x", encoding="utf-8")
    record = RunLog(clock=_clock)

    assert record.start(blocker / "registro.txt") is False
    assert record.active is False
    record.write("nada")


def test_a_new_record_closes_the_previous_one(tmp_path):
    record = RunLog(clock=_clock)
    record.start(tmp_path / "uno.txt")
    record.start(tmp_path / "dos.txt")
    record.write("segundo")
    record.stop()

    assert "segundo" not in (tmp_path / "uno.txt").read_text(encoding="utf-8")
    assert "segundo" in (tmp_path / "dos.txt").read_text(encoding="utf-8")


def test_a_failing_write_stops_the_record_without_stopping_the_run(tmp_path):
    record = RunLog(clock=_clock)
    record.start(tmp_path / "registro.txt")
    record._file = Mock(write=Mock(side_effect=OSError("disco lleno")))

    record.write("línea")

    assert record.active is False


def test_info_goes_to_screen_and_record_detail_only_to_record(capsys, run_log_text):
    ProgressLogger.info("En pantalla")
    ProgressLogger.detail("Solo en el registro")
    ProgressLogger.detail_start("PREPARANDO ALGO")
    ProgressLogger.detail_finish("ALGO PREPARADO", 1.5)

    screen = capsys.readouterr().out
    record = run_log_text()
    assert screen == "En pantalla\n"
    assert "En pantalla" in record
    assert "Solo en el registro" in record
    assert "PREPARANDO ALGO..." in record
    assert "ALGO PREPARADO (1.50 s)" in record


def test_ffmpeg_details_stay_out_of_the_screen(capsys, run_log_text):
    TransitionBuilder().build(
        previous_stream="[a]",
        current_stream="[b]",
        output_stream="[ab]",
        transition_type="fade",
        duration=0.4,
        offset=5.29,
        from_scene=1,
        to_scene=2,
    )

    assert capsys.readouterr().out == ""
    assert "Transición 1→2: fade | 0.40 s | offset 5.29 s" in run_log_text()


def test_whisper_output_goes_to_the_record(tmp_path, capsys, run_log_text):
    audio = tmp_path / "voz.mp3"
    audio.write_bytes(b"x")
    output = tmp_path / "subtitles" / "voz.srt"

    def whisper(command, **options):
        assert options["stdout"] is subprocess.PIPE
        assert options["stderr"] is subprocess.STDOUT
        assert options["env"]["PYTHONIOENCODING"] == "utf-8"
        folder = command[command.index("--output_dir") + 1]
        (tmp_path / folder / "voz.srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nHola\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "[00:00.000 --> 00:01.000]  Hola\n")

    config = Mock(cli_arguments=Mock(return_value=["--model", "x"]), no_speech_threshold=0.6)
    with patch("app.modules.subtitles.io.subtitle_builder.subprocess.run", side_effect=whisper):
        SubtitleBuilder(transcription_config=config).build(audio_path=audio, output_path=output)

    assert "[00:00.000 --> 00:01.000]  Hola" in run_log_text()
    assert "-->" not in capsys.readouterr().out


def test_failing_whisper_keeps_its_output_in_the_record_and_the_error(tmp_path, run_log_text):
    audio = tmp_path / "voz.mp3"
    audio.write_bytes(b"x")
    failure = subprocess.CalledProcessError(1, ["whisper"], output="RuntimeError: sin memoria\n")
    config = Mock(cli_arguments=Mock(return_value=[]), model="medium", no_speech_threshold=0.6)

    with patch(
        "app.modules.subtitles.io.subtitle_builder.subprocess.run",
        side_effect=failure,
    ), pytest.raises(OperationalError) as caught:
        SubtitleBuilder(transcription_config=config).build(
            audio_path=audio,
            output_path=tmp_path / "voz.srt",
        )

    assert "RuntimeError: sin memoria" in run_log_text()
    assert "sin memoria" in caught.value.context.technical_metadata["output_summary"]


def _run_main(monkeypatch, tmp_path, *, side_effect=None):
    monkeypatch.chdir(tmp_path)
    request = Mock(route=None, project_name="test_project", overwrite_project=False)
    with patch("main.RunController") as controller, patch("main.FormatCatalog"), patch(
        "main.FontManager"
    ), patch("main.run_application", side_effect=side_effect):
        controller.return_value.run.return_value = request
        return main.main()


@pytest.mark.real_run_log
def test_main_keeps_the_record_beside_the_project(monkeypatch, tmp_path):
    def run(request):
        ProgressLogger.info("GENERANDO ALGO...")
        ProgressLogger.detail("detalle técnico 0.0000 s")

    assert _run_main(monkeypatch, tmp_path, side_effect=run) == 0

    record = (tmp_path / "output" / "test_project" / "registro.txt").read_text(
        encoding="utf-8"
    )
    assert "GENERANDO ALGO..." in record
    assert "detalle técnico 0.0000 s" in record
    assert RUN_LOG.active is False


@pytest.mark.real_run_log
def test_main_writes_the_error_in_the_record_too(monkeypatch, tmp_path, capsys):
    def run(request):
        raise RuntimeError("fallo de prueba")

    with patch("main.write_internal_error_log", return_value=None):
        assert _run_main(monkeypatch, tmp_path, side_effect=run) == 1

    record = (tmp_path / "output" / "test_project" / "registro.txt").read_text(
        encoding="utf-8"
    )
    assert "Se produjo un error interno inesperado." in record
    assert "Se produjo un error interno inesperado." in capsys.readouterr().out
    assert RUN_LOG.active is False


@pytest.mark.real_run_log
def test_main_goes_on_without_a_record_it_cannot_create(monkeypatch, tmp_path, capsys):
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "test_project").write_text("no es carpeta", encoding="utf-8")

    assert _run_main(monkeypatch, tmp_path) == 0

    screen = capsys.readouterr().out
    assert "No se pudo crear el registro de la ejecución" in screen
    assert "la ejecución sigue sin él" in screen
