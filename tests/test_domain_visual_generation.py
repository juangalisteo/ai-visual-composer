import unittest
from dataclasses import FrozenInstanceError, asdict, fields

from app.domain import (
    ColorPlan,
    CompositionPlan,
    GenerationResult,
    GenerationTranslation,
    GlobalIntent,
    LightingPlan,
    MotionSense,
    NarrativeFacts,
    NarrativeReading,
    PhotographyPlan,
    SceneIntent,
    StagingPlan,
    StoryboardScene,
    VisualBrief,
    VisualStrategy,
)


class VisualGenerationDomainModelsTest(unittest.TestCase):

    def test_models_are_passive_immutable_domain_structures(self):
        reading = NarrativeReading(
            facts=NarrativeFacts(
                stated=(
                    "La ley de correspondencia.",
                )
            )
        )

        self.assertEqual(
            reading.facts.stated,
            (
                "La ley de correspondencia.",
            )
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            reading.facts = NarrativeFacts()

    def test_intent_models_keep_global_and_scene_responsibilities(self):
        global_intent = GlobalIntent(
            expressive_purpose="Reveal a hidden relation."
        )

        scene_intent = SceneIntent(
            emotional_function="Show the discovery."
        )

        self.assertEqual(
            global_intent.expressive_purpose,
            "Reveal a hidden relation."
        )
        self.assertEqual(
            scene_intent.emotional_function,
            "Show the discovery."
        )

    def test_visual_models_do_not_require_backend_specific_data(self):
        scene = StoryboardScene(
            scene_number=1,
            text="A reflective scene.",
            visible_subject="study table",
            visible_action="rests in quiet light",
            visible_environment="quiet study",
            filmable_interpretation="a study table rests in quiet light",
        )

        brief = VisualBrief(
            visible_content="study table",
            visual_strategy=VisualStrategy(
                representation_approach="quiet symbolic realism"
            ),
            staging=StagingPlan(
                main_subject="study table"
            )
        )

        result = GenerationResult(
            output_path="output/images/scene_001.png",
            scene_number=1,
            width=1280,
            height=720
        )

        self.assertEqual(
            brief.visible_content,
            "study table"
        )
        self.assertEqual(
            result.status,
            "completed"
        )
        self.assertEqual(
            scene.visual_truth_status,
            "structured"
        )

    def test_storyboard_scene_supports_visual_truth_construction(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Texto de la escena",
            duration=5.0,
            source_index=0,
            visible_subject="persona observable",
            visible_action="observa una llave",
            visible_environment="biblioteca",
            filmable_interpretation="una persona observa una llave",
        )

        self.assertEqual(
            scene.scene_number,
            1
        )
        self.assertEqual(
            scene.text,
            "Texto de la escena"
        )
        self.assertEqual(
            scene.duration,
            5.0
        )
        self.assertEqual(
            scene.source_index,
            0
        )
        self.assertEqual(
            scene.visible_subject,
            "persona observable"
        )
        self.assertEqual(
            scene.key_objects,
            ()
        )
        self.assertEqual(
            scene.visual_truth_status,
            "structured"
        )

    def test_storyboard_scene_keeps_visual_truth_positional_order(self):
        scene = StoryboardScene(
            1,
            "Texto",
            "funcion narrativa",
            "momento narrativo",
            4.0,
            2,
            "notas",
            "sujeto visible",
            "accion visible",
            "entorno visible",
        )

        self.assertEqual(
            scene.scene_number,
            1
        )
        self.assertEqual(
            scene.notes,
            "notas"
        )
        self.assertEqual(
            scene.visible_subject,
            "sujeto visible"
        )
        self.assertEqual(
            scene.visible_action,
            "accion visible"
        )
        self.assertEqual(
            scene.visible_environment,
            "entorno visible"
        )
        self.assertEqual(
            scene.visual_truth_status,
            "structured"
        )

    def test_storyboard_scene_supports_structured_filmable_scene(self):
        scene = StoryboardScene(
            scene_number=7,
            text="La correspondencia se vuelve observable.",
            visible_subject="investigadora adulta junto a una mesa",
            visible_action="observa una llave de bronce",
            visible_environment="biblioteca historica",
            time_context="noche silenciosa",
            key_objects=(
                "llave de bronce",
                "mesa de madera",
            ),
            spatial_relationships=(
                "la llave esta entre la investigadora y una lampara",
            ),
            continuity_links=(
                "misma investigadora de la escena anterior",
            ),
            abstract_source="ley de correspondencia",
            filmable_interpretation=(
                "una llave fisica conecta el patron de un mapa "
                "con la decision de la investigadora"
            ),
            visual_constraints=(
                "sin texto legible",
                "mantener ropa sobria",
            ),
            visual_truth_status="structured",
        )

        self.assertEqual(
            scene.visible_subject,
            "investigadora adulta junto a una mesa"
        )
        self.assertEqual(
            scene.visible_action,
            "observa una llave de bronce"
        )
        self.assertEqual(
            scene.time_context,
            "noche silenciosa"
        )
        self.assertEqual(
            scene.key_objects,
            (
                "llave de bronce",
                "mesa de madera",
            )
        )
        self.assertEqual(
            scene.visual_truth_status,
            "structured"
        )

    def test_storyboard_scene_defaults_are_not_shared(self):
        first = StoryboardScene(
            scene_number=1,
            text="Primera escena",
        )
        second = StoryboardScene(
            scene_number=2,
            text="Segunda escena",
        )

        self.assertIsInstance(
            first.key_objects,
            tuple
        )
        self.assertEqual(
            first.key_objects,
            second.key_objects
        )
        self.assertIsInstance(
            first.spatial_relationships,
            tuple
        )
        self.assertIsInstance(
            first.continuity_links,
            tuple
        )
        self.assertIsInstance(
            first.visual_constraints,
            tuple
        )

        with self.assertRaises(
            AttributeError
        ):
            first.key_objects.append(
                "objeto"
            )

    def test_storyboard_scene_is_immutable(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Escena",
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            scene.visible_subject = "otro sujeto"

    def test_storyboard_scene_equality_is_deterministic(self):
        first = StoryboardScene(
            scene_number=1,
            text="Escena",
            visible_subject="sujeto visible",
            key_objects=(
                "objeto",
            ),
        )
        second = StoryboardScene(
            scene_number=1,
            text="Escena",
            visible_subject="sujeto visible",
            key_objects=(
                "objeto",
            ),
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            asdict(
                first
            ),
            asdict(
                second
            )
        )

    def test_storyboard_scene_visual_truth_serialization_keeps_existing_fields(self):
        serialized = asdict(
            StoryboardScene(
                scene_number=1,
                text="Escena Visual Truth",
                duration=5.0,
                source_index=0,
                visible_subject="persona observable",
                visible_action="camina",
                visible_environment="pasillo",
                filmable_interpretation="una persona camina por un pasillo",
            )
        )

        self.assertEqual(
            serialized["scene_number"],
            1
        )
        self.assertEqual(
            serialized["text"],
            "Escena Visual Truth"
        )
        self.assertEqual(
            serialized["duration"],
            5.0
        )
        self.assertEqual(
            serialized["source_index"],
            0
        )
        self.assertEqual(
            serialized["visual_truth_status"],
            "structured"
        )

    def test_storyboard_scene_rich_serialization_preserves_visual_truth_fields(self):
        serialized = asdict(
            StoryboardScene(
                scene_number=1,
                text="Escena rica",
                visible_subject="persona observable",
                visible_action="abre una puerta",
                key_objects=(
                    "puerta",
                ),
                spatial_relationships=(
                    "la persona esta frente a la puerta",
                ),
                continuity_links=(
                    "continua desde el pasillo",
                ),
                abstract_source="transicion interior",
                filmable_interpretation="una puerta se abre fisicamente",
                visual_constraints=(
                    "sin texto",
                ),
                visual_truth_status="partially_structured",
            )
        )

        self.assertEqual(
            serialized["visible_subject"],
            "persona observable"
        )
        self.assertEqual(
            serialized["visible_action"],
            "abre una puerta"
        )
        self.assertEqual(
            serialized["key_objects"],
            (
                "puerta",
            )
        )
        self.assertEqual(
            serialized["abstract_source"],
            "transicion interior"
        )
        self.assertEqual(
            serialized["filmable_interpretation"],
            "una puerta se abre fisicamente"
        )

    def test_storyboard_scene_is_exported_from_domain_package(self):
        from app.domain import StoryboardScene as ExportedStoryboardScene

        self.assertIs(
            ExportedStoryboardScene,
            StoryboardScene
        )

    def test_storyboard_scene_does_not_include_backend_dependencies(self):
        field_names = set(
            StoryboardScene.__dataclass_fields__
        )

        forbidden = {
            "prompt",
            "positive_prompt",
            "negative_prompt",
            "model",
            "workflow",
            "sampler",
            "scheduler",
            "guidance",
            "steps",
            "payload",
            "nodes",
            "comfyui",
            "backend",
            "codec",
            "lens",
            "focal_length",
            "color_grading",
            "camera_movement",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                field_names
            )
        )

    def test_storyboard_scene_does_not_include_legacy_setting(self):
        field_names = [
            field.name
            for field in fields(
                StoryboardScene
            )
        ]

        self.assertNotIn(
            "setting",
            field_names
        )
        self.assertNotIn(
            "subject",
            field_names
        )
        self.assertNotIn(
            "action",
            field_names
        )
        self.assertNotIn(
            "visible_setting",
            field_names
        )

    def test_abstract_source_and_filmable_interpretation_can_coexist(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Escena abstracta",
            abstract_source="correspondencia universal",
            filmable_interpretation=(
                "una hoja y un mapa estelar muestran "
                "un patron fisico similar"
            ),
            visual_truth_status="partially_structured",
        )

        self.assertEqual(
            scene.abstract_source,
            "correspondencia universal"
        )
        self.assertIn(
            "hoja",
            scene.filmable_interpretation
        )

    def test_cognitive_language_models_can_be_composed(self):
        reading = NarrativeReading(
            facts=NarrativeFacts(
                stated=(
                    "A principle is explained.",
                )
            )
        )
        global_intent = GlobalIntent(
            expressive_purpose="Reveal an invisible order.",
            dominant_emotion="wonder",
            global_energy="calm"
        )
        scene_intent = SceneIntent(
            emotional_function="quiet revelation",
            emotion="awe",
            emotional_intensity="low"
        )
        strategy = VisualStrategy(
            representation_approach="cinematic abstraction",
            realism_level="grounded",
            symbolism_degree="restrained",
            scale_treatment="macro and micro echo"
        )
        staging = StagingPlan(
            main_subject="geometric pattern",
            environment="minimal contemplative space",
            action_or_state="still reflection"
        )
        photography = PhotographyPlan(
            point_of_view="observational",
            emotional_distance="measured",
            photographic_atmosphere="quiet"
        )
        composition = CompositionPlan(
            visual_hierarchy="pattern first",
            framing="centered",
            figure_ground_relationship="clear separation"
        )
        lighting = LightingPlan(
            source="soft motivated side light",
            quality="diffuse",
            contrast="gentle"
        )
        color = ColorPlan(
            temperature="neutral warm",
            palette=(
                "deep graphite",
                "soft gold"
            )
        )
        motion = MotionSense(
            latent_energy="contained",
            rhythm="slow",
            visual_breathing="spacious"
        )
        brief = VisualBrief(
            visible_content="nested geometric reflections",
            felt_experience="calm discovery",
            visual_strategy=strategy,
            staging=staging,
            photography=photography,
            composition=composition,
            lighting=lighting,
            color=color,
            motion=motion,
            continuity_relationship="continues the contemplative arc"
        )
        translation = GenerationTranslation(
            target_backend="generic image generator",
            translation_priorities=(
                "preserve visual hierarchy",
            ),
            translation_restrictions=(
                "no backend-specific syntax",
            ),
            translated_directives=(
                "structured visual directive",
            ),
            trace_references=(
                "VisualBrief.visible_content",
            )
        )

        self.assertEqual(
            reading.facts.stated,
            (
                "A principle is explained.",
            )
        )
        self.assertEqual(
            global_intent.global_energy,
            "calm"
        )
        self.assertEqual(
            scene_intent.emotional_intensity,
            "low"
        )
        self.assertIs(
            brief.visual_strategy,
            strategy
        )
        self.assertIs(
            brief.staging,
            staging
        )
        self.assertIs(
            brief.photography,
            photography
        )
        self.assertIs(
            brief.composition,
            composition
        )
        self.assertIs(
            brief.lighting,
            lighting
        )
        self.assertIs(
            brief.color,
            color
        )
        self.assertIs(
            brief.motion,
            motion
        )
        self.assertEqual(
            translation.trace_references,
            (
                "VisualBrief.visible_content",
            )
        )

    def test_cognitive_language_models_are_immutable(self):
        intent = SceneIntent(
            emotional_function="pause"
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            intent.emotional_function = "changed"

    def test_visual_brief_is_not_a_prompt_or_backend_payload(self):
        field_names = set(
            VisualBrief.__dataclass_fields__
        )

        forbidden = {
            "prompt",
            "positive_prompt",
            "negative_prompt",
            "payload",
            "workflow",
            "nodes",
            "file_path",
            "output_path",
            "constraints",
            "negative_constraints"
        }

        self.assertTrue(
            forbidden.isdisjoint(
                field_names
            )
        )

    def test_generation_translation_does_not_own_creative_decisions(self):
        field_names = set(
            GenerationTranslation.__dataclass_fields__
        )

        forbidden = {
            "narrative_reading",
            "global_intent",
            "scene_intent",
            "visual_brief",
            "visual_strategy",
            "staging",
            "photography",
            "composition",
            "lighting",
            "color",
            "motion"
        }

        self.assertTrue(
            forbidden.isdisjoint(
                field_names
            )
        )


if __name__ == "__main__":
    unittest.main()
