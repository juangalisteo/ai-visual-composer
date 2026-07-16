from dataclasses import dataclass

from app.modules.video.ffmpeg.filter_context import (
    FilterContext
)


@dataclass(frozen=True)
class GraphContext:
    """
    Estado acumulado mientras se construye filter_complex.
    """

    context: FilterContext

    filter_parts: list[str]

    current_stream: str = ""

    video_streams: tuple[
        str,
        ...
    ] = ()

    visual_effect_streams: tuple[
        str,
        ...
    ] = ()

    overlay_streams: tuple[
        str,
        ...
    ] = ()
