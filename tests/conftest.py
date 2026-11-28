import pytest

from app.managers.font_manager import RUN_FALLBACK_NOTICES
from app.shared.run_log import RUN_LOG


@pytest.fixture(autouse=True)
def _fresh_font_fallback_notices():
    """Every test starts with an empty run registry of fallback warnings."""
    RUN_FALLBACK_NOTICES.reset()
    yield
    RUN_FALLBACK_NOTICES.reset()


@pytest.fixture(autouse=True)
def _no_run_log_in_output(request, monkeypatch):
    """``main.main()`` would start output/<proyecto>/registro.txt in the
    working directory; tests that need the real record ask for it with
    ``@pytest.mark.real_run_log`` (and work in their own folder)."""
    RUN_LOG.stop()
    if "real_run_log" not in request.keywords:
        monkeypatch.setattr(RUN_LOG, "start", lambda path: True)
    yield
    RUN_LOG.stop()


@pytest.fixture(autouse=True)
def _whisper_cuda_cache_outside_the_project(request, monkeypatch, tmp_path_factory):
    """``SubtitleBuilder`` creates the CUDA cache folder of config/whisper.json
    (models/whisper/_cache/cuda) before running Whisper; in a test run from the
    project folder that would be the project's. Tests get a pytest folder,
    made only if asked for; tests that need the declared folder ask for it with
    ``@pytest.mark.real_whisper_cuda_cache`` (and work in their own folder)."""
    if "real_whisper_cuda_cache" not in request.keywords:
        monkeypatch.setattr(
            "app.modules.subtitles.io.subtitle_builder.whisper_cuda_cache_dir",
            lambda: tmp_path_factory.mktemp("test_cuda_cache"),
        )


@pytest.fixture
def run_log_text(tmp_path):
    """Start the real record of the run in ``tmp_path``; call it to read it."""
    from app.shared.run_log import RunLog

    path = tmp_path / "registro.txt"
    RunLog.start(RUN_LOG, path)
    return lambda: path.read_text(encoding="utf-8")
