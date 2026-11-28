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


@pytest.fixture
def run_log_text(tmp_path):
    """Start the real record of the run in ``tmp_path``; call it to read it."""
    from app.shared.run_log import RunLog

    path = tmp_path / "registro.txt"
    RunLog.start(RUN_LOG, path)
    return lambda: path.read_text(encoding="utf-8")
