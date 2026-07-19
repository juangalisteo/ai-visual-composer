from dataclasses import dataclass

from app.domain import (
    ColorPlan,
    CompositionPlan,
    GenerationResult,
    GenerationTranslation,
    GlobalIntent,
    LightingPlan,
    MotionSense,
    NarrativeReading,
    PhotographyPlan,
    SceneIntent,
    StagingPlan,
    StoryboardScene,
    VisualBrief,
    VisualStrategy,
)


@dataclass(frozen=True)
class LegacyCognitiveSceneAdaptation:
    storyboard_scene: StoryboardScene
    narrative_reading: NarrativeReading
    global_intent: GlobalIntent
    scene_intent: SceneIntent
    visual_strategy: VisualStrategy
    staging: StagingPlan
    photography: PhotographyPlan
    composition: CompositionPlan
    lighting: LightingPlan
    color: ColorPlan
    motion: MotionSense
    visual_brief: VisualBrief
    trace_references: tuple[str, ...]


class LegacyCognitiveAdapter:

    @staticmethod
    def from_storyboard_scene(
        storyboard_scene: StoryboardScene,
        visual_idea: str = ""
    ) -> LegacyCognitiveSceneAdaptation:
        trace_references = (
            LegacyCognitiveAdapter.trace_storyboard_scene(
                storyboard_scene
            )
        )

        narrative_reading = (
            LegacyCognitiveAdapter.narrative_reading_from_scene(
                storyboard_scene
            )
        )
        global_intent = (
            LegacyCognitiveAdapter.global_intent_from_scene(
                storyboard_scene
            )
        )
        scene_intent = (
            LegacyCognitiveAdapter.scene_intent_from_scene(
                storyboard_scene
            )
        )
        visual_strategy = (
            LegacyCognitiveAdapter.visual_strategy_from_scene(
                storyboard_scene
            )
        )
        staging = (
            LegacyCognitiveAdapter.staging_from_scene(
                storyboard_scene
            )
        )
        photography = (
            LegacyCognitiveAdapter.photography_from_scene(
                storyboard_scene
            )
        )
        composition = (
            LegacyCognitiveAdapter.composition_from_scene(
                storyboard_scene
            )
        )
        lighting = (
            LegacyCognitiveAdapter.lighting_from_scene(
                storyboard_scene
            )
        )
        color = (
            LegacyCognitiveAdapter.color_from_scene(
                storyboard_scene
            )
        )
        motion = (
            LegacyCognitiveAdapter.motion_from_scene(
                storyboard_scene
            )
        )

        visual_brief = VisualBrief(
            visible_content=LegacyCognitiveAdapter._clean(
                visual_idea
            ),
            visual_strategy=visual_strategy,
            staging=staging,
            photography=photography,
            composition=composition,
            lighting=lighting,
            color=color,
            motion=motion
        )

        return LegacyCognitiveSceneAdaptation(
            storyboard_scene=storyboard_scene,
            narrative_reading=narrative_reading,
            global_intent=global_intent,
            scene_intent=scene_intent,
            visual_strategy=visual_strategy,
            staging=staging,
            photography=photography,
            composition=composition,
            lighting=lighting,
            color=color,
            motion=motion,
            visual_brief=visual_brief,
            trace_references=trace_references
        )

    @staticmethod
    def narrative_reading_from_scene(
        storyboard_scene: StoryboardScene
    ) -> NarrativeReading:
        return NarrativeReading(
            event=LegacyCognitiveAdapter._clean(
                storyboard_scene.text
            ),
            scene_function=LegacyCognitiveAdapter._clean(
                storyboard_scene.narrative_role
            ),
            relation_to_whole=LegacyCognitiveAdapter._clean(
                storyboard_scene.narrative_moment
            )
        )

    @staticmethod
    def global_intent_from_scene(
        storyboard_scene: StoryboardScene
    ) -> GlobalIntent:
        return GlobalIntent(
            expressive_purpose=""
        )

    @staticmethod
    def scene_intent_from_scene(
        storyboard_scene: StoryboardScene
    ) -> SceneIntent:
        return SceneIntent(
            emotional_function=""
        )

    @staticmethod
    def visual_strategy_from_scene(
        storyboard_scene: StoryboardScene
    ) -> VisualStrategy:
        return VisualStrategy(
            representation_approach=""
        )

    @staticmethod
    def staging_from_scene(
        storyboard_scene: StoryboardScene
    ) -> StagingPlan:
        return StagingPlan(
            main_subject=LegacyCognitiveAdapter._clean(
                storyboard_scene.subject
            ),
            environment=LegacyCognitiveAdapter._clean(
                storyboard_scene.setting
            ),
            action_or_state=LegacyCognitiveAdapter._clean(
                storyboard_scene.action
            )
        )

    @staticmethod
    def photography_from_scene(
        storyboard_scene: StoryboardScene
    ) -> PhotographyPlan:
        return PhotographyPlan(
            point_of_view=""
        )

    @staticmethod
    def composition_from_scene(
        storyboard_scene: StoryboardScene
    ) -> CompositionPlan:
        return CompositionPlan(
            visual_hierarchy=""
        )

    @staticmethod
    def lighting_from_scene(
        storyboard_scene: StoryboardScene
    ) -> LightingPlan:
        return LightingPlan(
            source=""
        )

    @staticmethod
    def color_from_scene(
        storyboard_scene: StoryboardScene
    ) -> ColorPlan:
        return ColorPlan(
            temperature=""
        )

    @staticmethod
    def motion_from_scene(
        storyboard_scene: StoryboardScene
    ) -> MotionSense:
        return MotionSense(
            latent_energy=""
        )

    @staticmethod
    def generation_translation_from_result(
        generation_result: GenerationResult,
        target_backend: str = ""
    ) -> GenerationTranslation:
        return GenerationTranslation(
            target_backend=LegacyCognitiveAdapter._clean(
                target_backend
            ),
            trace_references=(
                LegacyCognitiveAdapter.trace_generation_result(
                    generation_result
                )
            )
        )

    @staticmethod
    def trace_storyboard_scene(
        storyboard_scene: StoryboardScene
    ) -> tuple[str, ...]:
        references = [
            "StoryboardScene.scene_number"
        ]

        if storyboard_scene.source_index is not None:
            references.append(
                "StoryboardScene.source_index"
            )

        if storyboard_scene.duration is not None:
            references.append(
                "StoryboardScene.duration"
            )

        return tuple(
            references
        )

    @staticmethod
    def trace_generation_result(
        generation_result: GenerationResult
    ) -> tuple[str, ...]:
        references = [
            "GenerationResult.output_path"
        ]

        if generation_result.scene_number is not None:
            references.append(
                "GenerationResult.scene_number"
            )

        if generation_result.width is not None:
            references.append(
                "GenerationResult.width"
            )

        if generation_result.height is not None:
            references.append(
                "GenerationResult.height"
            )

        if generation_result.duration is not None:
            references.append(
                "GenerationResult.duration"
            )

        return tuple(
            references
        )

    @staticmethod
    def _clean(
        value
    ) -> str:
        if value is None:
            return ""

        return str(
            value
        ).strip()
