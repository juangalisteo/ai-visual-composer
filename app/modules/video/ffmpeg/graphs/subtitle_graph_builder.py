from pathlib import Path
import time

from app.modules.video.ffmpeg.graphs.base_graph_builder import (
    BaseGraphBuilder
)
from app.modules.video.ffmpeg.graphs.graph_result import GraphResult
from app.shared.progress_logger import ProgressLogger


class SubtitleGraphBuilder(
    BaseGraphBuilder
):

    def build(
        self,
        graph
    ):
        start = time.perf_counter()

        context = graph.context

        filter_parts = list(
            graph.filter_parts
        )

        current_stream = (
            graph.current_stream
        )

        if not current_stream:
            raise ValueError(
                "No existe un stream para aplicar "
                "los subtítulos."
            )

        subtitle_path = Path(
            context.timeline.subtitle_path
        )

        fonts_dir = Path(
            context.fonts_dir
        )

        if not subtitle_path.exists():
            raise FileNotFoundError(
                f"No existe el archivo SRT: "
                f"{subtitle_path}"
            )

        if not fonts_dir.exists():
            raise FileNotFoundError(
                f"No existe la carpeta de fuentes: "
                f"{fonts_dir}"
            )

        escaped_subtitle_path = (
            self._escape_path(
                subtitle_path
            )
        )

        escaped_fonts_dir = (
            self._escape_path(
                fonts_dir
            )
        )

        output_stream = (
            "[vout]"
        )

        filter_parts.append(
            f"{current_stream}"
            f"subtitles='{escaped_subtitle_path}':"
            f"fontsdir='{escaped_fonts_dir}':"
            f"force_style='{context.subtitle_style}'"
            f"{output_stream}"
        )

        ProgressLogger.info(
            f"Subtítulos preparados "
            f"({time.perf_counter() - start:.4f} s)"
        )

        return GraphResult(
            parts=filter_parts,
            current_stream=output_stream,
            video_streams=graph.video_streams
        )

    def _escape_path(
        self,
        path
    ):
        return (
            Path(path)
            .resolve()
            .as_posix()
            .replace(
                ":",
                r"\:"
            )
            .replace(
                "'",
                r"\'"
            )
        )