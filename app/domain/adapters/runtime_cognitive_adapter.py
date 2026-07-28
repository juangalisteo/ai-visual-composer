from dataclasses import dataclass

from app.domain import (
    ColorPlan,
    CompositionPlan,
    GenerationResult,
    GenerationTranslation,
    GlobalIntent,
    LightingPlan,
    MotionSense,
    NarrativeContext,
    NarrativeEvent,
    NarrativeFacts,
    NarrativeFunction,
    NarrativeReading,
    PhotographyPlan,
    SceneIntent,
    StagingPlan,
    StoryboardScene,
    VisualBrief,
    VisualStrategy,
)


@dataclass(frozen=True)
class RuntimeCognitiveSceneAdaptation:
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


class RuntimeCognitiveAdapter:

    @staticmethod
    def from_storyboard_scene(
        storyboard_scene: StoryboardScene,
        visual_idea: str = "",
        orientation: str = ""
    ) -> RuntimeCognitiveSceneAdaptation:
        trace_references = (
            RuntimeCognitiveAdapter.trace_storyboard_scene(
                storyboard_scene
            )
        )

        narrative_reading = (
            RuntimeCognitiveAdapter.narrative_reading_from_scene(
                storyboard_scene
            )
        )
        global_intent = (
            RuntimeCognitiveAdapter.global_intent_from_scene(
                storyboard_scene
            )
        )
        scene_intent = (
            RuntimeCognitiveAdapter.scene_intent_from_scene(
                storyboard_scene
            )
        )
        visual_strategy = (
            RuntimeCognitiveAdapter.visual_strategy_from_scene(
                storyboard_scene
            )
        )
        staging = (
            RuntimeCognitiveAdapter.staging_from_scene(
                storyboard_scene
            )
        )
        photography = (
            RuntimeCognitiveAdapter.photography_from_scene(
                storyboard_scene
            )
        )
        composition = (
            RuntimeCognitiveAdapter.composition_from_scene(
                storyboard_scene
            )
        )
        lighting = (
            RuntimeCognitiveAdapter.lighting_from_scene(
                storyboard_scene
            )
        )
        color = (
            RuntimeCognitiveAdapter.color_from_scene(
                storyboard_scene
            )
        )
        motion = (
            RuntimeCognitiveAdapter.motion_from_scene(
                storyboard_scene
            )
        )

        visual_brief = VisualBrief(
            visible_content=(
                RuntimeCognitiveAdapter.visible_content_from_scene(
                    storyboard_scene,
                    visual_idea
                )
            ),
            visible_subject=RuntimeCognitiveAdapter._clean(
                storyboard_scene.visible_subject
            ),
            visible_action=RuntimeCognitiveAdapter._clean(
                storyboard_scene.visible_action
            ),
            visible_environment=RuntimeCognitiveAdapter._clean(
                storyboard_scene.setting
            ),
            time_context=RuntimeCognitiveAdapter._clean(
                storyboard_scene.time_context
            ),
            key_objects=tuple(
                storyboard_scene.key_objects
            ),
            spatial_relationships=tuple(
                storyboard_scene.spatial_relationships
            ),
            continuity_links=tuple(
                storyboard_scene.continuity_links
            ),
            abstract_source=RuntimeCognitiveAdapter._clean(
                storyboard_scene.abstract_source
            ),
            filmable_interpretation=RuntimeCognitiveAdapter._clean(
                storyboard_scene.filmable_interpretation
            ),
            visual_constraints=tuple(
                storyboard_scene.visual_constraints
            ),
            visual_truth_status=RuntimeCognitiveAdapter._clean(
                storyboard_scene.visual_truth_status
            ),
            narrative_composition=(
                RuntimeCognitiveAdapter.composition_guidance_from_orientation(
                    orientation
                )
            ),
            primary_subject=(
                RuntimeCognitiveAdapter.visible_subject_from_scene(
                    storyboard_scene
                )
            ),
            visual_reading=RuntimeCognitiveAdapter._clean(
                storyboard_scene.filmable_interpretation
            ),
            visual_continuity=RuntimeCognitiveAdapter._join(
                storyboard_scene.continuity_links
            ),
            visual_strategy=visual_strategy,
            staging=staging,
            photography=photography,
            composition=composition,
            lighting=lighting,
            color=color,
            motion=motion
        )

        return RuntimeCognitiveSceneAdaptation(
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
            facts=NarrativeFacts(
                stated=_tuple_if_present(
                    RuntimeCognitiveAdapter._clean(
                        storyboard_scene.text
                    )
                )
            ),
            event=NarrativeEvent(
                action=RuntimeCognitiveAdapter._clean(
                    storyboard_scene.action
                ),
                subject=RuntimeCognitiveAdapter._clean(
                    storyboard_scene.subject
                )
            ),
            context=NarrativeContext(
                known_context=RuntimeCognitiveAdapter._clean(
                    storyboard_scene.narrative_moment
                )
            ),
            function=NarrativeFunction(
                primary=RuntimeCognitiveAdapter._clean(
                    storyboard_scene.narrative_role
                )
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
            representation_approach="",
            visual_limits=tuple(
                storyboard_scene.visual_constraints
            )
        )

    @staticmethod
    def staging_from_scene(
        storyboard_scene: StoryboardScene
    ) -> StagingPlan:
        return StagingPlan(
            main_subject=(
                RuntimeCognitiveAdapter.visible_subject_from_scene(
                    storyboard_scene
                )
            ),
            environment=(
                RuntimeCognitiveAdapter.visible_environment_from_scene(
                    storyboard_scene
                )
            ),
            action_or_state=(
                RuntimeCognitiveAdapter.visible_action_from_scene(
                    storyboard_scene
                )
            ),
            spatial_relationship=RuntimeCognitiveAdapter._join(
                storyboard_scene.spatial_relationships
            ),
            significant_objects=tuple(
                storyboard_scene.key_objects
            )
        )

    @staticmethod
    def visible_content_from_scene(
        storyboard_scene: StoryboardScene,
        visual_idea: str = ""
    ) -> str:
        visual_truth_content = (
            RuntimeCognitiveAdapter._clean(
                storyboard_scene.filmable_interpretation
            )
            or RuntimeCognitiveAdapter._join(
                (
                    storyboard_scene.visible_subject,
                    storyboard_scene.visible_action,
                    storyboard_scene.setting
                    if RuntimeCognitiveAdapter.has_visual_truth_content(
                        storyboard_scene
                    )
                    else "",
                    storyboard_scene.time_context,
                )
            )
        )
        return (
            visual_truth_content
            or RuntimeCognitiveAdapter._clean(
                visual_idea
            )
            or RuntimeCognitiveAdapter._clean(
                storyboard_scene.text
            )
        )

    @staticmethod
    def has_visual_truth_content(
        storyboard_scene: StoryboardScene
    ) -> bool:
        return any(
            (
                RuntimeCognitiveAdapter._clean(
                    storyboard_scene.visible_subject
                ),
                RuntimeCognitiveAdapter._clean(
                    storyboard_scene.visible_action
                ),
                RuntimeCognitiveAdapter._clean(
                    storyboard_scene.time_context
                ),
                storyboard_scene.key_objects,
                storyboard_scene.spatial_relationships,
                storyboard_scene.continuity_links,
                RuntimeCognitiveAdapter._clean(
                    storyboard_scene.abstract_source
                ),
                RuntimeCognitiveAdapter._clean(
                    storyboard_scene.filmable_interpretation
                ),
                storyboard_scene.visual_constraints,
            )
        )

    @staticmethod
    def visible_subject_from_scene(
        storyboard_scene: StoryboardScene
    ) -> str:
        return (
            RuntimeCognitiveAdapter._clean(
                storyboard_scene.visible_subject
            )
            or RuntimeCognitiveAdapter._clean(
                storyboard_scene.subject
            )
        )

    @staticmethod
    def visible_action_from_scene(
        storyboard_scene: StoryboardScene
    ) -> str:
        return (
            RuntimeCognitiveAdapter._clean(
                storyboard_scene.visible_action
            )
            or RuntimeCognitiveAdapter._clean(
                storyboard_scene.action
            )
        )

    @staticmethod
    def visible_environment_from_scene(
        storyboard_scene: StoryboardScene
    ) -> str:
        return RuntimeCognitiveAdapter._clean(
            storyboard_scene.setting
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
    def composition_guidance_from_orientation(
        orientation: str
    ) -> str:
        orientation = RuntimeCognitiveAdapter._clean(
            orientation
        ).lower()
        if orientation == "vertical":
            return "vertical 9:16"
        if orientation == "horizontal":
            return "wide horizontal 16:9"
        return ""

    @staticmethod
    def generation_translation_from_result(
        generation_result: GenerationResult,
        target_backend: str = ""
    ) -> GenerationTranslation:
        return GenerationTranslation(
            target_backend=RuntimeCognitiveAdapter._clean(
                target_backend
            ),
            trace_references=(
                RuntimeCognitiveAdapter.trace_generation_result(
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

        references.extend(
            RuntimeCognitiveAdapter.trace_visual_truth(
                storyboard_scene
            )
        )

        return tuple(
            references
        )

    @staticmethod
    def trace_visual_truth(
        storyboard_scene: StoryboardScene
    ) -> tuple[str, ...]:
        visual_truth_fields = (
            "visible_subject",
            "visible_action",
            "setting",
            "time_context",
            "key_objects",
            "spatial_relationships",
            "continuity_links",
            "abstract_source",
            "filmable_interpretation",
            "visual_constraints",
            "visual_truth_status",
        )
        references = []
        for field in visual_truth_fields:
            value = getattr(
                storyboard_scene,
                field
            )
            if value:
                references.append(
                    f"StoryboardScene.{field}"
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

    @staticmethod
    def _join(
        values
    ) -> str:
        return " | ".join(
            item
            for item in (
                RuntimeCognitiveAdapter._clean(
                    value
                )
                for value in values
            )
            if item
        )


def _tuple_if_present(
    value: str
) -> tuple[str, ...]:
    if not value:
        return ()
    return (
        value,
    )
