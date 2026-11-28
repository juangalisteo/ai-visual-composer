"""Direct IMAGE-to-VIDEO API: request, service and the P7 adapter."""

import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.core.pipeline_telemetry import PipelineTelemetry
from app.managers.pipeline_summary import PipelineSummary
from app.managers.project_manager import ProjectManager
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
from app.modules.video_component.contracts import WanIntermediateOutput
from app.modules.video_component.builder import VideoComponentBuilder
from app.modules.video_component.models import VideoClipGenerationResult
from app.modules.video_component.profile_parameters import (
    build_video_backend_overrides,
    load_video_component_parameters,
)
from app.shared.profile_resolver import ProfileResolver


class DirectI2VArtifactOwnership(str, Enum):
    """The caller owns a direct-I2V artifact after successful generation."""

    CALLER_OWNED = "caller_owned"


@dataclass(frozen=True)
class DirectI2VGenerationResult:
    """Pure result contract for a future direct-I2V generation service."""

    generation: VideoClipGenerationResult
    profile_key: OperationalProfileKey
    intermediate_output: WanIntermediateOutput
    ownership: DirectI2VArtifactOwnership

    def __post_init__(self):
        if not isinstance(self.generation, VideoClipGenerationResult):
            raise TypeError("generation must be a VideoClipGenerationResult.")
        if not isinstance(self.profile_key, OperationalProfileKey):
            raise TypeError(
                "profile_key must be an OperationalProfileKey."
            )
        if self.profile_key.component is not ProfileComponent.VIDEO:
            raise ValueError(
                "Direct I2V requires a VIDEO operational identity."
            )

        intermediate_output = WanIntermediateOutput(
            self.intermediate_output
        )
        ownership = DirectI2VArtifactOwnership(self.ownership)
        if ownership is not DirectI2VArtifactOwnership.CALLER_OWNED:
            raise ValueError("Direct I2V artifacts must remain caller-owned.")

        object.__setattr__(
            self,
            "intermediate_output",
            intermediate_output,
        )
        object.__setattr__(self, "ownership", ownership)


class DirectI2VGenerationService:
    """Generate one caller-owned I2V artifact from declared VIDEO settings."""

    def __init__(self, profile_resolver=None, video_builder=None):
        self._profile_resolver = profile_resolver or ProfileResolver()
        self._video_builder = video_builder or VideoComponentBuilder()

    def generate(self, request):
        if not isinstance(request, DirectI2VRequest):
            raise TypeError("request must be a DirectI2VRequest.")

        profile = load_video_component_parameters(
            request.profile_key,
            resolver=self._profile_resolver,
        )
        overrides = build_video_backend_overrides(profile)
        generation = self._video_builder.generate_clip(
            source_path=request.source_image,
            output_dir=request.output_dir,
            output_name=f"{request.output_stem}.mp4",
            **overrides,
        )
        return DirectI2VGenerationResult(
            generation=generation,
            profile_key=request.profile_key,
            intermediate_output=overrides["intermediate_output"],
            ownership=DirectI2VArtifactOwnership.CALLER_OWNED,
        )


@dataclass(frozen=True)
class DirectI2VRequest:
    """Explicit technical input for one direct IMAGE-to-VIDEO request."""

    source_image: Path
    profile_key: OperationalProfileKey
    output_dir: Path
    output_stem: str

    def __post_init__(self):
        if not isinstance(self.profile_key, OperationalProfileKey):
            raise TypeError(
                "profile_key must be an OperationalProfileKey."
            )
        if self.profile_key.component is not ProfileComponent.VIDEO:
            raise ValueError(
                "Direct I2V requires a VIDEO operational identity."
            )
        if not isinstance(self.output_stem, str):
            raise TypeError("output_stem must be text.")

        output_stem = self.output_stem.strip()
        if not output_stem:
            raise ValueError("output_stem must not be empty.")

        object.__setattr__(self, "source_image", Path(self.source_image))
        object.__setattr__(self, "output_dir", Path(self.output_dir))
        object.__setattr__(self, "output_stem", output_stem)


def run_direct_i2v(
    *,
    pipeline_start=None,
    project=None,
    profile_key=None,
    source_path,
    video_builder=None,
):
    """Generate one direct I2V clip in the project and print its summary (P7)."""
    if pipeline_start is None:
        pipeline_start = time.perf_counter()

    project = (
        project
        or ProjectManager()
    )

    project.setup()

    video_builder = (
        video_builder
        or VideoComponentBuilder()
    )

    output_dir = (
        project.base_path
        / "video_clips"
    )

    service = DirectI2VGenerationService(
        video_builder=video_builder
    )
    request = DirectI2VRequest(
        source_image=source_path,
        profile_key=profile_key,
        output_dir=output_dir,
        output_stem="clip_001",
    )
    pipeline_telemetry = PipelineTelemetry()
    result, video_elapsed = pipeline_telemetry.measure_stage(
        service.generate,
        request,
    )

    summary = PipelineSummary(
        project.project_name
    )
    summary.set_media_duration(
        result.generation.duration_seconds
    )
    pipeline_telemetry.complete(
        summary=summary,
        stage_times={
            "Clips de vídeo": video_elapsed,
        },
        pipeline_start=pipeline_start,
    )

    return result.generation.output_clip
