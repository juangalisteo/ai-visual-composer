from collections import OrderedDict

from app.cli.error_presenter import ErrorPresenter
from app.shared.operation_warnings import OperationWarning, OperationWarnings
from app.shared.progress_logger import ProgressLogger
from app.shared.time_formatter import TimeFormatter


class PipelineSummary:

    LINE_WIDTH = 40
    LABEL_WIDTH = 27

    def __init__(
        self,
        project_name,
        include_visual_metrics=True,
    ):
        self.project_name = str(
            project_name
        )
        self.include_visual_metrics = bool(
            include_visual_metrics
        )

        self.scene_count = 0
        self.image_count = 0
        self.media_duration = None

        self.details = OrderedDict()
        self.stage_times = OrderedDict()
        self._total_time = None
        self.warnings = OperationWarnings()

    def set_scene_count(
        self,
        scene_count
    ):
        self.scene_count = (
            None
            if scene_count is None
            else int(scene_count)
        )

    def set_image_count(
        self,
        image_count
    ):
        self.image_count = (
            None
            if image_count is None
            else int(image_count)
        )

    def set_media_duration(
        self,
        duration_seconds
    ):
        if duration_seconds is None:
            self.media_duration = None
            return

        self.media_duration = max(
            0.0,
            float(duration_seconds)
        )

    def add_stage(
        self,
        name,
        elapsed_seconds
    ):
        self.stage_times[str(name)] = max(
            0.0,
            float(elapsed_seconds)
        )

    def add_detail(
        self,
        name,
        value
    ):
        self.details[str(name)] = str(value)

    def add_warning(self, warning: OperationWarning):
        """Attach one non-fatal degradation to this pipeline summary."""
        return self.warnings.add(warning)

    def set_total_time(
        self,
        elapsed_seconds
    ):
        self._total_time = max(
            0.0,
            float(elapsed_seconds)
        )

    def total_time(self):
        if self._total_time is not None:
            return self._total_time

        return sum(
            self.stage_times.values()
        )

    def render(self):
        lines = [
            "=" * self.LINE_WIDTH,
            "RESUMEN DEL PIPELINE".center(
                self.LINE_WIDTH
            ),
            "=" * self.LINE_WIDTH,
            "",
            self._metric_line(
                "Proyecto",
                self.project_name
            ),
        ]

        if self.include_visual_metrics:
            lines.extend([
                self._metric_line(
                    "Escenas",
                    self.scene_count
                ),
                self._metric_line(
                    "Imágenes",
                    self.image_count
                ),
                self._metric_line(
                    "Duración",
                    self._format_media_duration()
                ),
            ])
            seconds_per_image = self._format_seconds_per_image()
            if seconds_per_image is not None:
                lines.append(
                    self._metric_line(
                        "Segundos por imagen",
                        seconds_per_image
                    )
                )

        for detail_name, detail_value in self.details.items():
            lines.append(
                self._metric_line(
                    detail_name,
                    detail_value
                )
            )

        warning_presentations = tuple(
            ErrorPresenter().present_warning(warning).text
            for warning in self.warnings
        )
        if warning_presentations:
            lines.extend([
                "",
                "AVISOS",
                "-" * self.LINE_WIDTH,
                *warning_presentations,
            ])

        lines.extend([
            "",
            "-" * self.LINE_WIDTH,
            ""
        ])

        for stage_name, elapsed in self.stage_times.items():
            lines.append(
                self._metric_line(
                    stage_name,
                    TimeFormatter.format(
                        elapsed
                    )
                )
            )

        lines.extend([
            "",
            "-" * self.LINE_WIDTH,
            "",
            self._metric_line(
                "Tiempo total",
                TimeFormatter.format(
                    self.total_time()
                )
            ),
            "",
            "=" * self.LINE_WIDTH,
            "Proyecto generado correctamente.",
            "=" * self.LINE_WIDTH
        ])

        return "\n".join(
            lines
        )

    def print(self):
        warning_count = len(self.warnings)
        ProgressLogger.info(
            "\n"
            + self.render(),
            warnings=self.warnings,
            operation="Resumen del pipeline",
        )
        if len(self.warnings) > warning_count:
            warning = self.warnings.snapshot()[-1]
            ProgressLogger.info(
                "\n"
                + ErrorPresenter().present_warning(warning).text
            )

    def _metric_line(
        self,
        label,
        value
    ):
        label = str(
            label
        )

        value = str(
            value
        )

        dot_count = max(
            1,
            self.LABEL_WIDTH
            - len(label)
        )

        return (
            f"{label}"
            f"{'.' * dot_count} "
            f"{value}"
        )

    def _format_media_duration(self):
        if self.media_duration is None:
            return "No disponible"

        total_seconds = int(
            round(
                self.media_duration
            )
        )

        hours = (
            total_seconds
            // 3600
        )

        minutes = (
            total_seconds
            % 3600
        ) // 60

        seconds = (
            total_seconds
            % 60
        )

        if hours > 0:
            return (
                f"{hours:02}:"
                f"{minutes:02}:"
                f"{seconds:02}"
            )

        return (
            f"{minutes:02}:"
            f"{seconds:02}"
        )

    def _format_seconds_per_image(self):
        if self.scene_count == 0:
            return None

        if (
            self.scene_count is None
            or self.media_duration is None
        ):
            return "No disponible"

        return (
            f"{self.media_duration / self.scene_count:.2f}"
        )
