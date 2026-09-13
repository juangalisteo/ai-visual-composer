from pathlib import Path
import time

from app.managers.project_manager import ProjectManager
from app.shared.config_contract import (
    require_float,
    require_mapping,
)
from app.shared.config_manager import ConfigManager
from app.shared.progress_logger import ProgressLogger

from app.modules.subtitles.cue_transformer import SubtitleCueTransformer
from app.modules.subtitles.timing import (
    SubtitleTimingResolver,
    count_gaps
)


class SrtOptimizer:

    def __init__(
        self,
        subtitle_profile,
        render_fps=None
    ):
        config = ConfigManager()

        if render_fps is None:
            profile = config.get_profile_config()
            video_style = require_mapping(
                profile,
                "video_style",
                "video_style"
            )
            render_fps = require_float(
                video_style,
                "fps",
                "video_style.fps"
            )

        self.transformer = SubtitleCueTransformer(
            subtitle_profile=subtitle_profile,
            render_fps=render_fps,
        )
        self.model = self.transformer.model

    def optimize(
        self,
        input_path=None,
        output_path=None,
        canonical_content=None,
    ):
        ProgressLogger.start(
            "OPTIMIZANDO SRT"
        )

        start = time.perf_counter()

        project = ProjectManager()

        if input_path is None:
            input_path = (
                project.subtitle_path()
            )

        if output_path is None:
            output_path = (
                project.subtitle_path()
            )

        input_path = Path(
            input_path
        )

        output_path = Path(
            output_path
        )

        if not input_path.exists():
            raise FileNotFoundError(
                f"No existe el SRT: "
                f"{input_path}"
            )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        content = input_path.read_text(
            encoding="utf-8"
        )

        if not content.strip():
            raise ValueError(
                "El archivo SRT está vacío."
            )

        timing = SubtitleTimingResolver().resolve(
            subtitle_path=input_path,
            audio_path=project.audio_path()
        )

        optimized_content = self.transformer.transform(
            content,
            timing=timing,
            canonical_content=canonical_content,
        )

        if timing is not None:
            gap_threshold = float(
                getattr(
                    self.model,
                    "significant_gap_threshold",
                    0.35
                )
            )
            ProgressLogger.info(
                "Subtitle timing source: "
                f"{timing.source} | "
                f"words timed: {timing.word_count} | "
                f"gaps detected: "
                f"{count_gaps(timing.words, gap_threshold)}"
            )

            if timing.fallback_reason:
                ProgressLogger.info(
                    "Subtitle timing fallback: "
                    f"{timing.fallback_reason}"
                )

            stats = getattr(
                self.model,
                "last_micro_cue_stats",
                None
            )

            if stats is not None and stats.detected:
                ProgressLogger.info(
                    "Micro-cues detected: "
                    f"{stats.detected} | "
                    "Micro-cues merged: "
                    f"{stats.merged}"
                )
        else:
            ProgressLogger.info(
                "Subtitle timing source: Legacy SRT"
            )

        output_path.write_text(
            optimized_content,
            encoding="utf-8"
        )

        if not output_path.exists():
            raise FileNotFoundError(
                "No se encontró el SRT optimizado: "
                f"{output_path}"
            )

        if output_path.stat().st_size <= 0:
            raise RuntimeError(
                "El SRT optimizado está vacío."
            )

        elapsed = (
            time.perf_counter()
            - start
        )

        ProgressLogger.finish(
            "SUBT\u00cdTULOS FINALES GENERADOS",
            elapsed
        )

        return output_path
