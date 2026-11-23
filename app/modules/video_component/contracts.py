"""Pure, immutable contracts for the future WAN I2V architecture.

These contracts intentionally do not load configuration, access paths, build
workflows, communicate with ComfyUI, or persist manifests. Runtime adoption is
deferred to later WAN phases.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)


class ComfyUIInputOwnership(str, Enum):
    BACKEND_OWNED = "backend_owned"


class ComfyUIInputRetention(str, Enum):
    CLEANUP_ON_SUCCESS = "cleanup_on_success"
    PRESERVE_ON_FAILURE = "preserve_on_failure"
    PRESERVE_ALWAYS = "preserve_always"


class WanArtifactOwnership(str, Enum):
    """Ownership is explicit so cleanup never targets ComfyUI-owned output."""

    APPLICATION_OWNED = "application_owned"


class WanArtifactRetention(str, Enum):
    CLEANUP_ON_SUCCESS = "cleanup_on_success"
    PRESERVE_ON_FAILURE = "preserve_on_failure"
    PRESERVE_ALWAYS = "preserve_always"


class WanIntermediateOutput(str, Enum):
    """Technical WAN intermediate-output capability."""

    LOSSLESS_FFV1 = "lossless_ffv1"
    SAVEVIDEO_H264 = "savevideo_h264"


@dataclass(frozen=True)
class WanGenerationParameters:
    width: int
    height: int
    frames: int
    fps: float
    seed_mode: str
    seed: int | None = None

    def __post_init__(self):
        _require_positive_int(self.width, "width")
        _require_positive_int(self.height, "height")
        _require_positive_int(self.frames, "frames")
        _require_positive_number(self.fps, "fps")

        seed_mode = str(self.seed_mode).strip().lower()
        if seed_mode not in {"random", "fixed"}:
            raise ValueError("seed_mode must be random or fixed.")
        if seed_mode == "fixed" and self.seed is None:
            raise ValueError("fixed seed_mode requires seed.")
        if self.seed is not None:
            if isinstance(self.seed, bool) or not isinstance(self.seed, int):
                raise ValueError("seed must be an integer when supplied.")
            if self.seed < 0:
                raise ValueError("seed must not be negative.")
        object.__setattr__(self, "seed_mode", seed_mode)


@dataclass(frozen=True)
class WanDeliveryParameters:
    intermediate_output: WanIntermediateOutput = (
        WanIntermediateOutput.SAVEVIDEO_H264
    )

    def __post_init__(self):
        try:
            intermediate_output = WanIntermediateOutput(
                self.intermediate_output
            )
        except ValueError as error:
            raise ValueError(
                "intermediate_output must be lossless_ffv1 or savevideo_h264."
            ) from error
        object.__setattr__(
            self,
            "intermediate_output",
            intermediate_output,
        )


@dataclass(frozen=True)
class WanSamplingParameters:
    steps: int
    cfg: float
    sampler: str
    scheduler: str

    def __post_init__(self):
        _require_positive_int(self.steps, "steps")
        _require_positive_number(self.cfg, "cfg")
        object.__setattr__(self, "sampler", _required_text(self.sampler, "sampler"))
        object.__setattr__(self, "scheduler", _required_text(self.scheduler, "scheduler"))


@dataclass(frozen=True)
class WanVideoComponentDocument:
    """Declared I2V parameters associated with one operational VIDEO identity."""

    kind: str
    operational_profile: OperationalProfileKey
    format: str
    generation: WanGenerationParameters
    delivery: WanDeliveryParameters
    sampling: WanSamplingParameters

    def __post_init__(self):
        if self.kind != "video_component":
            raise ValueError("kind must be video_component.")
        if self.operational_profile.component is not ProfileComponent.VIDEO:
            raise ValueError("WAN documents require a VIDEO operational identity.")
        profile_format = _required_text(self.format, "format").lower()
        if profile_format != self.operational_profile.format:
            raise ValueError("format must match the operational identity.")
        object.__setattr__(self, "format", profile_format)


@dataclass(frozen=True)
class StagedComfyInput:
    job_id: str
    source_path: Path
    relative_input_name: str
    staged_path: Path
    ownership: ComfyUIInputOwnership = ComfyUIInputOwnership.BACKEND_OWNED
    retention: ComfyUIInputRetention = ComfyUIInputRetention.CLEANUP_ON_SUCCESS
    # Closest folder above the job folder that existed before staging: the
    # cleanup never deletes it (None: only the job folder is deleted).
    existing_folder: Path | None = None

    def __post_init__(self):
        object.__setattr__(self, "job_id", _required_text(self.job_id, "job_id"))
        relative_name = _required_text(
            self.relative_input_name,
            "relative_input_name",
        ).replace("\\", "/")
        if relative_name.startswith("/") or ".." in relative_name.split("/"):
            raise ValueError("relative_input_name must stay relative to the ComfyUI input root.")
        object.__setattr__(self, "source_path", Path(self.source_path))
        object.__setattr__(self, "staged_path", Path(self.staged_path))
        if self.existing_folder is not None:
            object.__setattr__(self, "existing_folder", Path(self.existing_folder))
        object.__setattr__(self, "relative_input_name", relative_name)
        object.__setattr__(self, "ownership", ComfyUIInputOwnership(self.ownership))
        object.__setattr__(self, "retention", ComfyUIInputRetention(self.retention))


@dataclass(frozen=True)
class WanWorkflowNodeRole:
    """A semantic workflow role, identified by class type rather than node ID."""

    role: str
    class_type: str
    cardinality: str = "exactly_one"

    def __post_init__(self):
        object.__setattr__(self, "role", _required_text(self.role, "role"))
        object.__setattr__(self, "class_type", _required_text(self.class_type, "class_type"))
        if self.cardinality != "exactly_one":
            raise ValueError("cardinality must be exactly_one.")


@dataclass(frozen=True)
class WanWorkflowInputRole:
    consumer_role: str
    input_name: str
    producer_class_type: str

    def __post_init__(self):
        object.__setattr__(self, "consumer_role", _required_text(self.consumer_role, "consumer_role"))
        object.__setattr__(self, "input_name", _required_text(self.input_name, "input_name"))
        object.__setattr__(
            self,
            "producer_class_type",
            _required_text(self.producer_class_type, "producer_class_type"),
        )


@dataclass(frozen=True)
class WanWorkflowBinding:
    node_roles: tuple[WanWorkflowNodeRole, ...]
    positive_prompt: WanWorkflowInputRole
    negative_prompt: WanWorkflowInputRole

    def __post_init__(self):
        node_roles = tuple(self.node_roles)
        if not node_roles:
            raise ValueError("node_roles are required.")
        roles = tuple(node.role for node in node_roles)
        if len(roles) != len(set(roles)):
            raise ValueError("node role names must be unique.")
        if self.positive_prompt == self.negative_prompt:
            raise ValueError("positive and negative prompt bindings must differ.")
        object.__setattr__(self, "node_roles", node_roles)


@dataclass(frozen=True)
class WanLosslessCapturePlan:
    """Technical, opt-in plan for a project-owned SaveImage branch."""

    job_id: str
    capture_node_id: str
    output_prefix: str
    expected_frame_count: int
    width: int
    height: int
    fps: float
    bit_depth: int
    ownership: WanArtifactOwnership = WanArtifactOwnership.APPLICATION_OWNED
    retention: WanArtifactRetention = WanArtifactRetention.CLEANUP_ON_SUCCESS
    materialization: str = "ffv1"

    def __post_init__(self):
        for field_name in ("job_id", "capture_node_id", "output_prefix"):
            object.__setattr__(
                self,
                field_name,
                _required_text(getattr(self, field_name), field_name),
            )
        if self.output_prefix.startswith("/") or ".." in self.output_prefix.replace("\\", "/").split("/"):
            raise ValueError("output_prefix must stay relative to ComfyUI output.")
        _require_positive_int(self.expected_frame_count, "expected_frame_count")
        _require_positive_int(self.width, "width")
        _require_positive_int(self.height, "height")
        _require_positive_number(self.fps, "fps")
        _require_positive_int(self.bit_depth, "bit_depth")
        if self.bit_depth != 8:
            raise ValueError("Only the current 8-bit IMAGE contract is supported.")
        if self.materialization != "ffv1":
            raise ValueError("materialization must be ffv1.")
        object.__setattr__(self, "ownership", WanArtifactOwnership(self.ownership))
        object.__setattr__(self, "retention", WanArtifactRetention(self.retention))


@dataclass(frozen=True)
class WanLosslessFrameSequence:
    """Validated local copy of one ordered IMAGE batch from one WAN prompt."""

    plan: WanLosslessCapturePlan
    prompt_id: str
    ordered_frame_paths: tuple[Path, ...]
    artifact_root: Path
    fingerprint: str

    def __post_init__(self):
        object.__setattr__(self, "prompt_id", _required_text(self.prompt_id, "prompt_id"))
        paths = tuple(Path(path) for path in self.ordered_frame_paths)
        if len(paths) != self.plan.expected_frame_count:
            raise ValueError("lossless frame count does not match the capture plan.")
        if len(paths) != len(set(paths)):
            raise ValueError("lossless frame paths must be unique.")
        if any(path.suffix.lower() != ".png" for path in paths):
            raise ValueError("lossless frame capture requires PNG frames.")
        object.__setattr__(self, "ordered_frame_paths", paths)
        object.__setattr__(self, "artifact_root", Path(self.artifact_root))
        object.__setattr__(self, "fingerprint", _required_text(self.fingerprint, "fingerprint"))


@dataclass(frozen=True)
class WanClipArtifact:
    scene_number: int
    source_image: Path
    output_clip: Path
    prompt_id: str
    seed: int
    frames: int
    fps: float
    generation_width: int
    generation_height: int
    steps: int
    cfg: float
    sampler: str
    scheduler: str
    backend: str
    model: str
    workflow: str
    duration_seconds: float
    fingerprint: str

    def __post_init__(self):
        _require_positive_int(self.scene_number, "scene_number")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must not be negative.")
        _require_positive_int(self.frames, "frames")
        _require_positive_number(self.fps, "fps")
        _require_positive_int(self.generation_width, "generation_width")
        _require_positive_int(self.generation_height, "generation_height")
        _require_positive_int(self.steps, "steps")
        _require_positive_number(self.cfg, "cfg")
        _require_positive_number(self.duration_seconds, "duration_seconds")
        object.__setattr__(self, "source_image", Path(self.source_image))
        object.__setattr__(self, "output_clip", Path(self.output_clip))
        for field_name in (
            "prompt_id",
            "sampler",
            "scheduler",
            "backend",
            "model",
            "workflow",
            "fingerprint",
        ):
            object.__setattr__(
                self,
                field_name,
                _required_text(getattr(self, field_name), field_name),
            )


@dataclass(frozen=True)
class WanPartialArtifact:
    scene_number: int
    diagnostic_reference: str
    prompt_id: str | None = None
    output_clip: Path | None = None

    def __post_init__(self):
        _require_positive_int(self.scene_number, "scene_number")
        object.__setattr__(
            self,
            "diagnostic_reference",
            _required_text(self.diagnostic_reference, "diagnostic_reference"),
        )
        if self.prompt_id is not None:
            object.__setattr__(self, "prompt_id", _required_text(self.prompt_id, "prompt_id"))
        if self.output_clip is not None:
            object.__setattr__(self, "output_clip", Path(self.output_clip))


@dataclass(frozen=True)
class WanBatchResult:
    status: str
    completed_clips: tuple[WanClipArtifact, ...] = field(default_factory=tuple)
    partial_artifacts: tuple[WanPartialArtifact, ...] = field(default_factory=tuple)

    def __post_init__(self):
        completed_clips = tuple(self.completed_clips)
        partial_artifacts = tuple(self.partial_artifacts)
        if self.status not in {"complete", "partial"}:
            raise ValueError("status must be complete or partial.")
        if self.status == "complete" and (not completed_clips or partial_artifacts):
            raise ValueError("complete batches require clips and no partial artifacts.")
        if self.status == "partial" and not partial_artifacts:
            raise ValueError("partial batches require partial artifacts.")
        scene_numbers = tuple(clip.scene_number for clip in completed_clips)
        if len(scene_numbers) != len(set(scene_numbers)):
            raise ValueError("completed clip scene numbers must be unique.")
        object.__setattr__(self, "completed_clips", completed_clips)
        object.__setattr__(self, "partial_artifacts", partial_artifacts)


def _required_text(value, label):
    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} is required.")
    return text


def _require_positive_int(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer.")


def _require_positive_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{label} must be greater than zero.")
