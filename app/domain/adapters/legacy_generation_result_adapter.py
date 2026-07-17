from pathlib import Path

from app.domain import GenerationResult, StoryboardScene


class LegacyGenerationResultAdapter:

    @staticmethod
    def from_image_result(
        image_path,
        storyboard_scene: StoryboardScene,
        width: int,
        height: int
    ) -> GenerationResult:
        return GenerationResult(
            output_path=str(
                Path(
                    image_path
                )
            ),
            scene_number=storyboard_scene.scene_number,
            width=width,
            height=height,
            duration=storyboard_scene.duration
        )
