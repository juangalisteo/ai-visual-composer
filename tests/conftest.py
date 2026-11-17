import pytest

from app.managers.font_manager import RUN_FALLBACK_NOTICES


@pytest.fixture(autouse=True)
def _fresh_font_fallback_notices():
    """Every test starts with an empty run registry of fallback warnings."""
    RUN_FALLBACK_NOTICES.reset()
    yield
    RUN_FALLBACK_NOTICES.reset()
