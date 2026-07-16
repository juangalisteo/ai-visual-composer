from pathlib import Path

from app.modules.video.ffmpeg.filter_context import FilterContext
from app.modules.video.subtitles.subtitle_style_builder import (
    SubtitleStyleBuilder
)


class VideoFilterContextFactory:

    def build(
        self,
        build_context,
        components
    ):
        subtitle_style = (
            SubtitleStyleBuilder().build(
                build_context.config.subtitle_style
            )
        )

        first_overlay_input = (
            len(build_context.media.image_paths) + 1
        )

        first_visual_effect_input = (
            first_overlay_input
            + len(
                components.overlay_builder.inputs
            )
        )

        return FilterContext(
            media=build_context.media,
            timeline=build_context.timeline,
            config=build_context.config,
            subtitle_style=subtitle_style,
            fonts_dir=Path(
                "assets/fonts"
            ),
            overlay_inputs=(
                components.overlay_builder.inputs
            ),
            visual_effect_inputs=(
                components.visual_effect_builder.inputs
            ),
            first_overlay_input=(
                first_overlay_input
            ),
            first_visual_effect_input=(
                first_visual_effect_input
            )
        )
