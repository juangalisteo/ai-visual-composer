from pathlib import Path

from app.modules.video_component.comfyui_video_adapter import (
    ComfyUIVideoAdapter,
)
from app.modules.video_component.comfyui_video_backend import (
    ComfyUIVideoBackend,
)
from app.modules.video_component.models import (
    BackendVideoPrompt,
    VideoPreparationResult,
)
from app.modules.video_component.motion_intent_builder import (
    MotionIntentBuilder,
)
from app.modules.video_component.source_image_analysis import (
    SourceImageAnalyzer,
)
from app.modules.video_component.video_prompt_translator import (
    VideoPromptTranslator,
)


class VideoComponentBuilder:

    def __init__(
        self,
        source_image_analyzer=None,
        motion_intent_builder=None,
        video_prompt_translator=None,
        backend_video_adapter=None,
        video_backend=None,
    ):
        self.source_image_analyzer = (
            source_image_analyzer
            or SourceImageAnalyzer()
        )
        self.motion_intent_builder = (
            motion_intent_builder
            or MotionIntentBuilder()
        )
        self.video_prompt_translator = (
            video_prompt_translator
            or VideoPromptTranslator()
        )
        self.backend_video_adapter = (
            backend_video_adapter
            or ComfyUIVideoAdapter()
        )
        self.video_backend = (
            video_backend
            or ComfyUIVideoBackend()
        )

    def prepare(
        self,
        source_path=None,
        storyboard_scene=None
    ) -> VideoPreparationResult:
        visual_context = (
            self.source_image_analyzer.analyze(
                Path(
                    source_path
                    or "tests/fixtures/video/source.png"
                )
            )
        )

        motion_intent = (
            self.motion_intent_builder.build(
                visual_context,
                storyboard_scene=storyboard_scene
            )
        )

        prompt_plan = (
            self.video_prompt_translator.translate(
                motion_intent
            )
        )

        return VideoPreparationResult(
            visual_context=visual_context,
            motion_intent=motion_intent,
            prompt_plan=prompt_plan
        )

    def generate_clip(
        self,
        source_path=None,
        output_dir=None,
        output_name="clip_001.mp4",
        storyboard_scene=None,
        **backend_prompt_overrides
    ):
        preparation = self.prepare(
            source_path=source_path,
            storyboard_scene=storyboard_scene
        )
        backend_prompt = BackendVideoPrompt.from_preparation(
            preparation,
            **backend_prompt_overrides
        )
        workflow = self.backend_video_adapter.adapt(
            backend_prompt
        )
        return self.video_backend.generate(
            workflow,
            output_dir=(
                Path(
                    output_dir
                    or "output/video_component/video_clips"
                )
            ),
            output_name=output_name
        )
