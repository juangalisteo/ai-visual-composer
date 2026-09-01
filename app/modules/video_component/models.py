from dataclasses import dataclass, field
from pathlib import Path


class SourceImageAnalysisError(ValueError):
    pass


class ComfyUIVideoAdapterError(ValueError):
    pass


class ComfyUIVideoBackendError(RuntimeError):
    def __init__(
        self,
        message,
        *,
        category="UNKNOWN_BACKEND_ERROR",
        prompt_id="",
        node_id="",
        node_type="",
        exception_type="",
        exception_message="",
        status="",
    ):
        self.category = category
        self.prompt_id = prompt_id
        self.node_id = node_id
        self.node_type = node_type
        self.exception_type = exception_type
        self.exception_message = exception_message
        self.status = status
        super().__init__(
            message
        )


@dataclass(frozen=True)
class MinimalVisualContext:
    source_path: Path
    width: int
    height: int
    aspect_ratio: str
    orientation: str
    image_format: str
    stability_constraints: tuple[str, ...] = field(
        default_factory=tuple
    )

    def __post_init__(
        self
    ):
        if self.width <= 0:
            raise ValueError(
                "Image width must be greater than zero."
            )

        if self.height <= 0:
            raise ValueError(
                "Image height must be greater than zero."
            )

        if self.orientation not in {
            "landscape",
            "portrait",
            "square",
        }:
            raise ValueError(
                "Unsupported image orientation."
            )

        if not self.aspect_ratio.strip():
            raise ValueError(
                "Image aspect ratio is required."
            )

        if not self.image_format.strip():
            raise ValueError(
                "Image format is required."
            )

        object.__setattr__(
            self,
            "source_path",
            Path(self.source_path)
        )

        object.__setattr__(
            self,
            "image_format",
            self.image_format.strip().upper()
        )

        object.__setattr__(
            self,
            "stability_constraints",
            tuple(self.stability_constraints)
        )


@dataclass(frozen=True)
class MotionIntent:
    source: str
    camera_motion: str
    motion_intensity: str
    stability: str
    temporal_rhythm: str
    preservation_constraints: tuple[str, ...] = field(
        default_factory=tuple
    )
    avoidance_constraints: tuple[str, ...] = field(
        default_factory=tuple
    )
    source_trace: tuple[str, ...] = field(
        default_factory=tuple
    )

    def __post_init__(
        self
    ):
        for field_name in (
            "source",
            "camera_motion",
            "motion_intensity",
            "stability",
            "temporal_rhythm",
        ):
            if not getattr(
                self,
                field_name
            ).strip():
                raise ValueError(
                    f"{field_name} is required."
                )

        object.__setattr__(
            self,
            "preservation_constraints",
            tuple(self.preservation_constraints)
        )
        object.__setattr__(
            self,
            "avoidance_constraints",
            tuple(self.avoidance_constraints)
        )
        object.__setattr__(
            self,
            "source_trace",
            tuple(self.source_trace)
        )


@dataclass(frozen=True)
class VideoPromptPlan:
    prompt: str
    negative_prompt: str
    motion_summary: str
    constraints: tuple[str, ...] = field(
        default_factory=tuple
    )
    source_trace: tuple[str, ...] = field(
        default_factory=tuple
    )

    def __post_init__(
        self
    ):
        if not self.prompt.strip():
            raise ValueError(
                "Video prompt is required."
            )

        if not self.motion_summary.strip():
            raise ValueError(
                "Motion summary is required."
            )

        object.__setattr__(
            self,
            "constraints",
            tuple(self.constraints)
        )
        object.__setattr__(
            self,
            "source_trace",
            tuple(self.source_trace)
        )


@dataclass(frozen=True)
class VideoPreparationResult:
    visual_context: MinimalVisualContext
    motion_intent: MotionIntent
    prompt_plan: VideoPromptPlan
    status: str = "prepared"
    backend_required: bool = False

    def __post_init__(
        self
    ):
        if self.status != "prepared":
            raise ValueError(
                "Block 1 can only prepare video requests."
            )

        if self.backend_required:
            raise ValueError(
                "Block 1 must not require a real backend."
            )


@dataclass(frozen=True)
class BackendVideoPrompt:
    source_image: Path
    positive_prompt: str
    negative_prompt: str
    motion_summary: str
    constraints: tuple[str, ...] = field(
        default_factory=tuple
    )
    camera_motion: str = ""
    motion_intensity: str = ""
    stability: str = ""
    temporal_rhythm: str = ""
    preservation_constraints: tuple[str, ...] = field(
        default_factory=tuple
    )
    avoidance_constraints: tuple[str, ...] = field(
        default_factory=tuple
    )
    source_trace: tuple[str, ...] = field(
        default_factory=tuple
    )
    seed: int = 123456789
    frames: int = 17
    fps: float = 8.0
    generation_width: int = 320
    generation_height: int = 320
    target_width: int = 320
    target_height: int = 320
    steps: int = 4
    cfg: float = 5.0
    sampler: str = "uni_pc"
    scheduler: str = "simple"
    profile_name: str = ""
    backend: str = "ComfyUI"
    model: str = "wan2.2_ti2v_5B_fp16.safetensors"
    workflow: str = (
        "config/comfyui_wan22_ti2v_i2v_workflow_api.json"
    )

    def __post_init__(
        self
    ):
        if not self.positive_prompt.strip():
            raise ValueError(
                "Positive video prompt is required."
            )

        if not self.motion_summary.strip():
            raise ValueError(
                "Motion summary is required."
            )

        if self.seed < 0:
            raise ValueError(
                "Seed must not be negative."
            )

        if self.frames <= 0:
            raise ValueError(
                "Frames must be greater than zero."
            )

        if self.fps <= 0:
            raise ValueError(
                "FPS must be greater than zero."
            )

        if self.generation_width <= 0:
            raise ValueError(
                "Generation width must be greater than zero."
            )

        if self.generation_height <= 0:
            raise ValueError(
                "Generation height must be greater than zero."
            )

        if self.target_width <= 0:
            raise ValueError(
                "Target width must be greater than zero."
            )

        if self.target_height <= 0:
            raise ValueError(
                "Target height must be greater than zero."
            )

        if self.steps <= 0:
            raise ValueError(
                "Steps must be greater than zero."
            )

        if self.cfg <= 0:
            raise ValueError(
                "CFG must be greater than zero."
            )

        if not self.sampler.strip():
            raise ValueError(
                "Sampler is required."
            )

        if not self.scheduler.strip():
            raise ValueError(
                "Scheduler is required."
            )

        object.__setattr__(
            self,
            "source_image",
            Path(self.source_image)
        )
        object.__setattr__(
            self,
            "constraints",
            tuple(self.constraints)
        )
        object.__setattr__(
            self,
            "preservation_constraints",
            tuple(self.preservation_constraints)
        )
        object.__setattr__(
            self,
            "avoidance_constraints",
            tuple(self.avoidance_constraints)
        )
        object.__setattr__(
            self,
            "source_trace",
            tuple(self.source_trace)
        )
        object.__setattr__(
            self,
            "sampler",
            self.sampler.strip()
        )
        object.__setattr__(
            self,
            "scheduler",
            self.scheduler.strip()
        )
        object.__setattr__(
            self,
            "profile_name",
            self.profile_name.strip()
        )

    @classmethod
    def from_preparation(
        cls,
        preparation: VideoPreparationResult,
        **overrides
    ):
        values = {
            "source_image": preparation.visual_context.source_path,
            "positive_prompt": preparation.prompt_plan.prompt,
            "negative_prompt": (
                preparation.prompt_plan.negative_prompt
            ),
            "motion_summary": (
                preparation.prompt_plan.motion_summary
            ),
            "constraints": preparation.prompt_plan.constraints,
            "camera_motion": preparation.motion_intent.camera_motion,
            "motion_intensity": preparation.motion_intent.motion_intensity,
            "stability": preparation.motion_intent.stability,
            "temporal_rhythm": preparation.motion_intent.temporal_rhythm,
            "preservation_constraints": (
                preparation.motion_intent.preservation_constraints
            ),
            "avoidance_constraints": (
                preparation.motion_intent.avoidance_constraints
            ),
            "source_trace": preparation.prompt_plan.source_trace,
        }
        values.update(
            overrides
        )
        return cls(
            **values
        )


@dataclass(frozen=True)
class ComfyUIVideoWorkflow:
    workflow: dict
    backend_prompt: BackendVideoPrompt
    source_image_name: str
    output_prefix: str

    def __post_init__(
        self
    ):
        if not self.workflow:
            raise ValueError(
                "ComfyUI workflow is required."
            )

        if not self.source_image_name.strip():
            raise ValueError(
                "Source image name is required."
            )

        if not self.output_prefix.strip():
            raise ValueError(
                "Output prefix is required."
            )


@dataclass(frozen=True)
class VideoClipGenerationResult:
    source_image: Path
    output_clip: Path
    manifest_path: Path | None
    prompt_id: str
    backend: str
    model: str
    workflow: str
    seed: int
    frames: int
    fps: float
    generation_width: int
    generation_height: int
    target_width: int
    target_height: int
    steps: int
    cfg: float
    sampler: str
    scheduler: str
    profile_name: str
    duration_seconds: float
    fingerprint: str
    positive_prompt: str = ""
    negative_prompt: str = ""
    motion_summary: str = ""
    camera_motion: str = ""
    motion_intensity: str = ""
    stability: str = ""
    temporal_rhythm: str = ""
    preservation_constraints: tuple[str, ...] = field(
        default_factory=tuple
    )
    avoidance_constraints: tuple[str, ...] = field(
        default_factory=tuple
    )
    source_trace: tuple[str, ...] = field(
        default_factory=tuple
    )

    def __post_init__(
        self
    ):
        object.__setattr__(
            self,
            "source_image",
            Path(self.source_image)
        )
        object.__setattr__(
            self,
            "output_clip",
            Path(self.output_clip)
        )
        if self.manifest_path is not None:
            object.__setattr__(
                self,
                "manifest_path",
                Path(self.manifest_path)
            )
        object.__setattr__(
            self,
            "preservation_constraints",
            tuple(self.preservation_constraints)
        )
        object.__setattr__(
            self,
            "avoidance_constraints",
            tuple(self.avoidance_constraints)
        )
        object.__setattr__(
            self,
            "source_trace",
            tuple(self.source_trace)
        )

        if not self.output_clip.exists():
            raise FileNotFoundError(
                "Generated video clip does not exist: "
                f"{self.output_clip}"
            )

        if self.output_clip.stat().st_size <= 0:
            raise ValueError(
                "Generated video clip is empty."
            )
