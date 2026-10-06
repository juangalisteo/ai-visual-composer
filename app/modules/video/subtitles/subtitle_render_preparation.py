from app.modules.video.subtitles.ass_subtitle_builder import (
    AssSubtitleBuilder,
    PreparedSubtitle,
    SubtitleRenderBackend,
    SubtitleRenderBackendResolver,
)
from app.modules.video.subtitles.subtitle_style_builder import SubtitleStyleBuilder


class SubtitleRenderPreparation:

    def __init__(self, backend_resolver=None, ass_builder=None, style_builder=None):
        self.backend_resolver = backend_resolver or SubtitleRenderBackendResolver()
        self.ass_builder = ass_builder or AssSubtitleBuilder()
        self.style_builder = style_builder or SubtitleStyleBuilder()

    def prepare(
        self,
        subtitle_path,
        render_style,
        width,
        height,
        style_source,
        timing=None,
    ):
        backend = self.backend_resolver.resolve(render_style)
        if backend is SubtitleRenderBackend.STATIC:
            return PreparedSubtitle(
                path=subtitle_path,
                backend=backend,
                force_style=self.style_builder.build(style_source),
            )
        temporary_path = self.ass_builder.build_temporary(
            subtitle_path=subtitle_path,
            render_style=render_style,
            width=width,
            height=height,
            timing=timing,
        )
        return PreparedSubtitle(
            path=temporary_path,
            backend=backend,
            force_style=None,
            temporary_path=temporary_path,
        )
