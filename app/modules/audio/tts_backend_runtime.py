"""Composition root for the product's neutral TTS backend capabilities."""

from pathlib import Path

from app.modules.audio.chatterbox_backend import ChatterboxBackend
from app.modules.audio.kokoro_backend import KokoroBackend
from app.modules.audio.piper_backend_provider import PiperBackendProvider
from app.modules.audio.tts_backend_registry import TtsBackendRegistry


DEFAULT_TTS_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def build_default_tts_backend_registry(
    *,
    project_root: Path | str = DEFAULT_TTS_PROJECT_ROOT,
) -> TtsBackendRegistry:
    """Register product capabilities without selecting one from presentation data.

    Providers remain lazy: their resources are checked only when a technical
    voice document resolves the provider's exact ``backend_key``. Backends
    that run in their own process load nothing until they synthesize.
    """
    return TtsBackendRegistry(
        (
            PiperBackendProvider(project_root),
            ChatterboxBackend(project_root),
            KokoroBackend(project_root),
        )
    )
