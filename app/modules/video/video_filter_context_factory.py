from pathlib import Path

from app.modules.video.ffmpeg.filter_context import FilterContext
from app.modules.video.subtitles.subtitle_style_builder import (
    SubtitleStyleBuilder
)
from app.modules.video.subtitles.subtitle_render_preparation import (
    SubtitleRenderPreparation,
)


class VideoFilterContextFactory:

    def build(
        self,
        build_context,
        components
    ):
        prepared_subtitle = None
        if build_context.render_subtitles:
            prepared_subtitle = SubtitleRenderPreparation(
                style_builder=SubtitleStyleBuilder()
            ).prepare(
                subtitle_path=build_context.timeline.subtitle_path,
                render_style=build_context.config.subtitles,
                width=build_context.config.width,
                height=build_context.config.height,
                style_source=build_context.config.subtitle_style,
                cue_policy=build_context.config.subtitle_cue_policy,
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
            subtitle_style=(
                prepared_subtitle.force_style
                if prepared_subtitle is not None
                else None
            ),
            fonts_dir=Path(
                "assets/fonts"
            ),
            subtitle_path=(
                prepared_subtitle.path
                if prepared_subtitle is not None
                else None
            ),
            subtitle_backend=(
                prepared_subtitle.backend
                if prepared_subtitle is not None
                else None
            ),
            temporary_subtitle_path=(
                prepared_subtitle.temporary_path
                if prepared_subtitle is not None
                else None
            ),
            render_subtitles=build_context.render_subtitles,
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
