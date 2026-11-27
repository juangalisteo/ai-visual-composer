"""Telemetry helpers for application pipeline summaries."""

import json
import time
from dataclasses import dataclass
from pathlib import Path

from app.shared.media_probe import MediaProbe
from app.shared.operation_warnings import OperationWarning, OperationWarnings


@dataclass(frozen=True)
class PipelineTelemetryArtifacts:
    """Technical artifact paths used only to enrich one pipeline summary."""

    storyboard_path: Path
    images_manifest_path: Path
    final_audio_path: Path
    audio_path: Path

    def __post_init__(self):
        for field_name in (
            "storyboard_path",
            "images_manifest_path",
            "final_audio_path",
            "audio_path",
        ):
            object.__setattr__(
                self,
                field_name,
                Path(getattr(self, field_name)),
            )


class PipelineTelemetry:
    """Measure stages and complete summaries without directing a pipeline."""

    # The order in which a GUION run executes its stages.
    STAGE_ORDER = (
        "Guion",
        "Voz",
        "Audio",
        "Subtítulos",
        "Storyboard",
        "Imágenes",
        "Clips de vídeo",
        "Vídeo final",
    )

    def __init__(
        self,
        clock=None,
        media_probe=None,
    ):
        self._clock = (
            clock
            or time.perf_counter
        )
        self._media_probe = (
            media_probe
            or MediaProbe
        )

    def measure_stage(
        self,
        function,
        *args,
        **kwargs,
    ):
        """Return one call result and its elapsed seconds unchanged."""
        started_at = self._clock()
        result = function(
            *args,
            **kwargs,
        )
        return (
            result,
            self._clock()
            - started_at,
        )

    def complete(
        self,
        summary,
        stage_times,
        pipeline_start,
        artifacts=None,
    ):
        """Populate available telemetry and present one completed summary."""
        if artifacts is not None:
            self._complete_artifact_metrics(
                summary,
                artifacts,
            )

        for stage_name in self.STAGE_ORDER:
            if stage_name in stage_times:
                summary.add_stage(
                    stage_name,
                    stage_times[stage_name],
                )

        measured_total = (
            self._clock()
            - pipeline_start
        )
        recorded_total = summary.total_time()

        if measured_total > recorded_total:
            summary.set_total_time(
                measured_total
            )

        summary.print()

    def _complete_artifact_metrics(
        self,
        summary,
        artifacts,
    ):
        summary.set_scene_count(
            self._count_json_items(
                artifacts.storyboard_path,
                warnings=summary.warnings,
                metric_name="escenas",
            )
        )
        summary.set_scene_durations(
            self._scene_durations(artifacts.storyboard_path)
        )
        summary.set_image_count(
            self._count_json_items(
                artifacts.images_manifest_path,
                warnings=summary.warnings,
                metric_name="imágenes",
            )
        )
        summary.set_media_duration(
            self._resolve_media_duration(
                artifacts,
                warnings=summary.warnings,
            )
        )

    def _count_json_items(
        self,
        json_path,
        warnings=None,
        metric_name=None,
    ):
        json_path = Path(
            json_path
        )

        if not json_path.exists():
            return 0

        try:
            data = json.loads(
                json_path.read_text(
                    encoding="utf-8"
                )
            )

        except (
            json.JSONDecodeError,
            OSError,
        ) as error:
            self._record_summary_degradation(
                warnings=warnings,
                metric_name=metric_name or "elementos",
                resource=json_path,
                error=error,
            )
            return None

        if not isinstance(
            data,
            list,
        ):
            self._record_summary_degradation(
                warnings=warnings,
                metric_name=metric_name or "elementos",
                resource=json_path,
                error=TypeError("El manifiesto no contiene una lista."),
            )
            return None

        return len(
            data
        )

    @staticmethod
    def _scene_durations(storyboard_path):
        """The ``duration`` of every storyboard scene, or () if any is missing.

        A storyboard that cannot be read was already reported by the scene
        count; here it only leaves the durations out.
        """
        try:
            data = json.loads(Path(storyboard_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ()
        if not isinstance(data, list):
            return ()
        durations = []
        for scene in data:
            duration = scene.get("duration") if isinstance(scene, dict) else None
            if isinstance(duration, bool) or not isinstance(duration, (int, float)):
                return ()
            durations.append(float(duration))
        return tuple(durations)

    def _resolve_media_duration(
        self,
        artifacts,
        warnings=None,
    ):
        candidate_paths = (
            artifacts.final_audio_path,
            artifacts.audio_path,
        )

        for media_path in candidate_paths:
            if media_path.exists():
                try:
                    return self._media_probe.get_duration(
                        media_path
                    )
                except (
                    OSError,
                    RuntimeError,
                    ValueError,
                ) as error:
                    self._record_summary_degradation(
                        warnings=warnings,
                        metric_name="duración del medio",
                        resource=media_path,
                        error=error,
                    )
                    return None

        return None

    @staticmethod
    def _record_summary_degradation(
        warnings,
        metric_name,
        resource,
        error,
    ):
        """Record unavailable telemetry without changing pipeline continuity."""
        if not isinstance(warnings, OperationWarnings):
            return
        warnings.add(
            OperationWarning(
                family="DEGRADATION",
                user_message=(
                    f"No se pudo obtener la métrica de {metric_name}; "
                    "se muestra como no disponible."
                ),
                recommended_action=(
                    "Revisa el recurso generado si necesitas esa métrica."
                ),
                operation="Resumen del pipeline",
                resource=str(resource),
                technical_metadata={
                    "cause_type": type(error).__name__,
                    "metric": str(metric_name),
                    "source": "pipeline_summary",
                },
            )
        )
