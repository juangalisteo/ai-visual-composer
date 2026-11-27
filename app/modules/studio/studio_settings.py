"""STUDIO settings shared by every format, declared in ``config/studio.json``.

- ``video_audio_srt.audio_tail_margin_seconds``: in VIDEO + AUDIO | SRT, a
  new audio shorter than the video by less than this many seconds is taken as
  equal: nothing is asked and nothing is added after it (PRUEBA-GS: the
  question «AUDIO MÁS CORTO QUE EL VÍDEO» came up for 6 ms).

Every key is required: the code never invents a value.
"""

from pathlib import Path

from app.shared.settings_file import load_settings_document, require_seconds


STUDIO_SETTINGS_PATH = Path("config/studio.json")
_OPERATION = "Cargar configuración de STUDIO"


def video_audio_tail_margin(path=STUDIO_SETTINGS_PATH) -> float:
    document = load_settings_document(path, operation=_OPERATION)
    return require_seconds(
        document,
        ("video_audio_srt", "audio_tail_margin_seconds"),
        path,
        operation=_OPERATION,
        example="0.1",
    )
