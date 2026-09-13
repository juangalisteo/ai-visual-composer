from dataclasses import dataclass
from pathlib import Path

from app.modules.video.media.media_loader import (
    VideoMedia
)
from app.modules.video.media.timeline_builder import (
    VideoTimeline
)
from app.modules.video.video_config import (
    VideoConfig
)


@dataclass(frozen=True)
class FilterContext:
    """
    Datos inmutables compartidos por todos los GraphBuilder.
    """

    media: VideoMedia
    timeline: VideoTimeline
    config: VideoConfig

    subtitle_style: str | None
    fonts_dir: Path
    render_subtitles: bool = True

    overlay_inputs: tuple[
        Path,
        ...
    ] = ()

    visual_effect_inputs: tuple[
        Path,
        ...
    ] = ()

    first_overlay_input: int = 0

    first_visual_effect_input: int = 0
