"""How overlays and visual effects are blended, declared in ``config/video.json``.

The ``screen``, ``add``, ``lighten`` and ``overlay`` modes are not linear, so
mixing them on YUV planes also mixes the colour planes and tints the picture
(PRUEBA-GS: magenta). Both inputs are converted to ``layer_blend.pixel_format``
(an RGB format) before ``blend`` and the result goes back to the profile's
``video.pixel_format``. ``layer_blend.scale_flags`` are the swscale flags of
those conversions: with the default ones every round trip darkens the luma.

The ``normal`` mode (alpha overlay) is linear and is not converted.
"""

from dataclasses import dataclass
from pathlib import Path

from app.shared.settings_file import load_settings_document, require_token


LAYER_BLEND_SETTINGS_PATH = Path("config/video.json")
_OPERATION = "Cargar configuración del vídeo"


@dataclass(frozen=True)
class LayerBlendSettings:
    pixel_format: str
    scale_flags: str


def load_layer_blend_settings(path=LAYER_BLEND_SETTINGS_PATH) -> LayerBlendSettings:
    document = load_settings_document(path, operation=_OPERATION)
    return LayerBlendSettings(
        pixel_format=require_token(
            document,
            ("layer_blend", "pixel_format"),
            path,
            operation=_OPERATION,
            example="«gbrp»",
        ),
        scale_flags=require_token(
            document,
            ("layer_blend", "scale_flags"),
            path,
            operation=_OPERATION,
            example="«accurate_rnd+full_chroma_int»",
        ),
    )
