import unittest

from app.domain import (
    GenerationResult,
    StoryboardScene,
)
from app.domain.adapters import (
    GenerationResultAdapter,
    RuntimeCognitiveAdapter,
    RuntimeCognitiveSceneAdaptation,
    StoryboardSceneAdapter,
)


class RuntimeDomainAdaptersTest(unittest.TestCase):

    def test_storyboard_adapter_preserves_current_storyboard_contract(self):
        scene = StoryboardSceneAdapter.from_dict(
            scene={
                "scene": "2",
                "text": "La escena conserva su texto.",
                "duration": 4.5,
                "visual_idea": "A quiet dawn over a valley",
            },
            default_scene_number=1,
        )

        self.assertEqual(
            scene,
            StoryboardScene(
                scene_number=2,
                text="La escena conserva su texto.",
                duration=4.5,
                source_index=1,
            ),
        )
        self.assertEqual(
            "legacy",
            scene.visual_truth_status,
        )
        self.assertEqual(
            "",
            scene.visible_subject,
        )
        self.assertEqual(
            "A quiet dawn over a valley",
            StoryboardSceneAdapter.legacy_visual_idea(
                {
                    "visual_idea": "A quiet dawn over a valley",
                }
            ),
        )

    def test_storyboard_adapter_preserves_storyboard_scene_2_fields(self):
        scene = StoryboardSceneAdapter.from_dict(
            scene={
                "scene": "3",
                "text": "La escena conserva su texto.",
                "visual_idea": "A quiet dawn over a valley",
                "narrative_role": "revelacion",
                "narrative_moment": "inicio",
                "subject": "una investigadora",
                "action": "observa una llave",
                "setting": "biblioteca antigua",
                "notes": "mantener calma",
                "visible_subject": "investigadora adulta",
                "visible_action": "observa una llave de bronce",
                "time_context": "noche",
                "key_objects": [
                    "llave de bronce",
                    "",
                    None,
                ],
                "spatial_relationships": [
                    "la llave esta sobre la mesa",
                ],
                "continuity_links": (
                    "misma investigadora",
                ),
                "abstract_source": "ley de correspondencia",
                "filmable_interpretation": (
                    "una llave fisica expresa una relacion invisible"
                ),
                "visual_constraints": "sin texto legible",
                "visual_truth_status": "structured",
            },
            default_scene_number=1,
        )

        self.assertEqual(
            "revelacion",
            scene.narrative_role,
        )
        self.assertEqual(
            "inicio",
            scene.narrative_moment,
        )
        self.assertEqual(
            "una investigadora",
            scene.subject,
        )
        self.assertEqual(
            "observa una llave",
            scene.action,
        )
        self.assertEqual(
            "biblioteca antigua",
            scene.setting,
        )
        self.assertEqual(
            "mantener calma",
            scene.notes,
        )
        self.assertEqual(
            "investigadora adulta",
            scene.visible_subject,
        )
        self.assertEqual(
            "observa una llave de bronce",
            scene.visible_action,
        )
        self.assertEqual(
            "noche",
            scene.time_context,
        )
        self.assertEqual(
            (
                "llave de bronce",
            ),
            scene.key_objects,
        )
        self.assertEqual(
            (
                "la llave esta sobre la mesa",
            ),
            scene.spatial_relationships,
        )
        self.assertEqual(
            (
                "misma investigadora",
            ),
            scene.continuity_links,
        )
        self.assertEqual(
            "ley de correspondencia",
            scene.abstract_source,
        )
        self.assertEqual(
            "una llave fisica expresa una relacion invisible",
            scene.filmable_interpretation,
        )
        self.assertEqual(
            (
                "sin texto legible",
            ),
            scene.visual_constraints,
        )
        self.assertEqual(
            "structured",
            scene.visual_truth_status,
        )

    def test_storyboard_adapter_keeps_legacy_status_when_field_is_absent(self):
        scene = StoryboardSceneAdapter.from_dict(
            scene={
                "scene": "4",
                "text": "Escena legacy.",
            },
            default_scene_number=1,
        )

        self.assertEqual(
            "legacy",
            scene.visual_truth_status,
        )
        self.assertEqual(
            (),
            scene.key_objects,
        )

    def test_storyboard_adapter_is_deterministic_and_does_not_mutate_input(self):
        raw_scene = {
            "scene": "5",
            "text": " Escena determinista. ",
            "key_objects": [
                " objeto ",
            ],
            "visual_constraints": [
                " sin texto ",
            ],
            "visual_truth_status": " partially_structured ",
        }
        original = {
            key: (
                tuple(
                    value
                )
                if isinstance(
                    value,
                    list
                )
                else value
            )
            for key, value in raw_scene.items()
        }

        first = StoryboardSceneAdapter.from_dict(
            scene=raw_scene,
            default_scene_number=1,
        )
        second = StoryboardSceneAdapter.from_dict(
            scene=raw_scene,
            default_scene_number=1,
        )

        self.assertEqual(
            first,
            second,
        )
        self.assertEqual(
            (
                "objeto",
            ),
            first.key_objects,
        )
        self.assertEqual(
            (
                "sin texto",
            ),
            first.visual_constraints,
        )
        self.assertEqual(
            "partially_structured",
            first.visual_truth_status,
        )
        self.assertEqual(
            original,
            {
                key: (
                    tuple(
                        value
                    )
                    if isinstance(
                        value,
                        list
                    )
                    else value
                )
                for key, value in raw_scene.items()
            },
        )

    def test_generation_result_adapter_preserves_manifest_inputs(self):
        result = GenerationResultAdapter.from_image_result(
            image_path="output/images/scene_001.png",
            storyboard_scene=StoryboardScene(
                scene_number=1,
                text="Escena",
                duration=3.0,
            ),
            width=640,
            height=360,
        )

        self.assertEqual(
            result,
            GenerationResult(
                output_path="output\\images\\scene_001.png",
                scene_number=1,
                width=640,
                height=360,
                duration=3.0,
            ),
        )

    def test_runtime_cognitive_adapter_builds_effective_visual_source_data(self):
        adaptation = RuntimeCognitiveAdapter.from_storyboard_scene(
            storyboard_scene=StoryboardScene(
                scene_number=1,
                text="La escena conserva su texto.",
                subject="una persona",
                action="observa una llave",
                setting="una biblioteca",
                duration=5.0,
                source_index=1,
            ),
            legacy_visual_idea="A person observing an old key",
            orientation="horizontal",
        )

        self.assertIsInstance(
            adaptation,
            RuntimeCognitiveSceneAdaptation,
        )
        self.assertEqual(
            "A person observing an old key",
            adaptation.visual_brief.visible_content,
        )
        self.assertEqual(
            "wide horizontal 16:9",
            adaptation.visual_brief.narrative_composition,
        )
        self.assertEqual(
            "una persona",
            adaptation.visual_brief.staging.main_subject,
        )
        self.assertEqual(
            "observa una llave",
            adaptation.visual_brief.staging.action_or_state,
        )
        self.assertEqual(
            "una biblioteca",
            adaptation.visual_brief.staging.environment,
        )
        self.assertIn(
            "StoryboardScene.duration",
            adaptation.trace_references,
        )

    def test_runtime_cognitive_adapter_preserves_visual_truth_2_fields(self):
        scene = StoryboardScene(
            scene_number=7,
            text="Una idea abstracta se vuelve visible.",
            subject="una investigadora",
            action="recibe una llave",
            setting="archivo subterraneo",
            visible_subject="investigadora con abrigo gris",
            visible_action="recibe una llave antigua",
            visible_environment="archivo subterraneo",
            time_context="noche lluviosa",
            key_objects=(
                "llave antigua",
                "sobre lacrado",
            ),
            spatial_relationships=(
                "la llave queda entre ambas manos",
                "el sobre permanece sobre la mesa",
            ),
            continuity_links=(
                "misma investigadora de la escena anterior",
                "misma llave antigua",
            ),
            abstract_source="confianza entregada",
            filmable_interpretation=(
                "una llave antigua cambia de manos en silencio"
            ),
            visual_constraints=(
                "sin texto legible",
                "sin ropa moderna brillante",
            ),
            visual_truth_status="structured",
        )

        adaptation = RuntimeCognitiveAdapter.from_storyboard_scene(
            storyboard_scene=scene,
            legacy_visual_idea="legacy idea should not replace visual truth",
            orientation="vertical",
        )
        brief = adaptation.visual_brief

        self.assertEqual(
            "una llave antigua cambia de manos en silencio",
            brief.visible_content,
        )
        self.assertEqual(
            scene.visible_subject,
            brief.visible_subject,
        )
        self.assertEqual(
            scene.visible_action,
            brief.visible_action,
        )
        self.assertEqual(
            scene.visible_environment,
            brief.visible_environment,
        )
        self.assertEqual(
            scene.time_context,
            brief.time_context,
        )
        self.assertEqual(
            scene.key_objects,
            brief.key_objects,
        )
        self.assertEqual(
            scene.spatial_relationships,
            brief.spatial_relationships,
        )
        self.assertEqual(
            scene.continuity_links,
            brief.continuity_links,
        )
        self.assertEqual(
            scene.abstract_source,
            brief.abstract_source,
        )
        self.assertEqual(
            scene.filmable_interpretation,
            brief.filmable_interpretation,
        )
        self.assertEqual(
            scene.visual_constraints,
            brief.visual_constraints,
        )
        self.assertEqual(
            scene.visual_truth_status,
            brief.visual_truth_status,
        )
        self.assertEqual(
            "vertical 9:16",
            brief.narrative_composition,
        )
        self.assertEqual(
            scene.visible_subject,
            brief.primary_subject,
        )
        self.assertEqual(
            scene.filmable_interpretation,
            brief.visual_reading,
        )
        self.assertEqual(
            "misma investigadora de la escena anterior | misma llave antigua",
            brief.visual_continuity,
        )
        self.assertEqual(
            scene.visible_subject,
            brief.staging.main_subject,
        )
        self.assertEqual(
            scene.visible_action,
            brief.staging.action_or_state,
        )
        self.assertEqual(
            scene.visible_environment,
            brief.staging.environment,
        )
        self.assertEqual(
            "la llave queda entre ambas manos | el sobre permanece sobre la mesa",
            brief.staging.spatial_relationship,
        )
        self.assertEqual(
            scene.key_objects,
            brief.staging.significant_objects,
        )
        self.assertEqual(
            scene.visual_constraints,
            brief.visual_strategy.visual_limits,
        )
        self.assertEqual(
            "",
            brief.visual_strategy.representation_approach,
        )
        self.assertIn(
            "StoryboardScene.visible_subject",
            adaptation.trace_references,
        )
        self.assertIn(
            "StoryboardScene.filmable_interpretation",
            adaptation.trace_references,
        )
        self.assertIn(
            "StoryboardScene.visual_constraints",
            adaptation.trace_references,
        )

    def test_runtime_narrative_reading_uses_visual_truth_as_primary_source(self):
        scene = StoryboardScene(
            scene_number=9,
            text="Una entrega cambia la relacion entre dos personas.",
            subject="legacy subject must not be used",
            action="legacy action must not be used",
            setting="legacy setting must not be used",
            narrative_role="revelacion",
            narrative_moment="punto de giro",
            visible_subject="archivista con guantes blancos",
            visible_action="entrega una llave antigua",
            visible_environment="sala de archivo subterranea",
            time_context="medianoche",
            key_objects=(
                "llave antigua",
                "sobre lacrado",
            ),
            spatial_relationships=(
                "la llave queda entre ambas manos",
                "el sobre permanece sobre la mesa",
            ),
            continuity_links=(
                "misma archivista",
                "misma llave antigua",
            ),
            abstract_source="confianza transferida",
            filmable_interpretation=(
                "una llave antigua cambia de manos en silencio"
            ),
            visual_constraints=(
                "sin texto legible",
            ),
            visual_truth_status="structured",
        )

        reading = RuntimeCognitiveAdapter.narrative_reading_from_scene(
            scene
        )

        self.assertEqual(
            "archivista con guantes blancos",
            reading.event.subject,
        )
        self.assertEqual(
            "entrega una llave antigua",
            reading.event.action,
        )
        self.assertEqual(
            "llave antigua",
            reading.event.object,
        )
        self.assertEqual(
            "sala de archivo subterranea",
            reading.event.environment,
        )
        self.assertEqual(
            "medianoche",
            reading.event.time_context,
        )
        self.assertEqual(
            scene.key_objects,
            reading.event.key_objects,
        )
        self.assertEqual(
            scene.spatial_relationships,
            reading.event.spatial_relationships,
        )
        self.assertEqual(
            scene.continuity_links,
            reading.event.continuity_links,
        )
        self.assertEqual(
            "confianza transferida",
            reading.event.abstract_source,
        )
        self.assertEqual(
            scene.visual_constraints,
            reading.event.visual_constraints,
        )
        self.assertEqual(
            "structured",
            reading.event.visual_truth_status,
        )
        self.assertEqual(
            "visual_truth_2_0",
            reading.event.source_model,
        )
        self.assertEqual(
            (
                "una llave antigua cambia de manos en silencio",
            ),
            reading.facts.shown,
        )
        self.assertEqual(
            (
                "archivista con guantes blancos",
                "sala de archivo subterranea",
                "llave antigua",
                "sobre lacrado",
            ),
            reading.facts.existing_elements,
        )
        self.assertEqual(
            scene.visual_constraints,
            reading.facts.conditions,
        )
        self.assertEqual(
            (
                "sala de archivo subterranea",
            ),
            reading.entities.places,
        )
        self.assertEqual(
            scene.spatial_relationships,
            reading.relations.relations,
        )
        self.assertEqual(
            scene.continuity_links,
            reading.continuity.continues,
        )
        self.assertEqual(
            (
                "confianza transferida",
            ),
            reading.concepts.explicit,
        )
        self.assertEqual(
            scene.key_objects,
            reading.explicit_symbols.symbols,
        )
        self.assertNotIn(
            "legacy subject must not be used",
            reading.facts.existing_elements,
        )
        self.assertNotEqual(
            "legacy action must not be used",
            reading.event.action,
        )

    def test_runtime_cognitive_adapter_preserves_legacy_fallbacks(self):
        adaptation = RuntimeCognitiveAdapter.from_storyboard_scene(
            storyboard_scene=StoryboardScene(
                scene_number=8,
                text="Escena legacy.",
                subject="persona legacy",
                action="camina",
                setting="pasillo",
            ),
            legacy_visual_idea="legacy visual idea",
        )
        brief = adaptation.visual_brief

        self.assertEqual(
            "legacy visual idea",
            brief.visible_content,
        )
        self.assertEqual(
            "",
            brief.visible_subject,
        )
        self.assertEqual(
            "legacy",
            brief.visual_truth_status,
        )
        self.assertEqual(
            "persona legacy",
            brief.staging.main_subject,
        )
        self.assertEqual(
            "camina",
            brief.staging.action_or_state,
        )
        self.assertEqual(
            "pasillo",
            brief.staging.environment,
        )
        self.assertEqual(
            "legacy",
            adaptation.narrative_reading.event.source_model,
        )
        self.assertEqual(
            "persona legacy",
            adaptation.narrative_reading.event.subject,
        )
        self.assertEqual(
            "camina",
            adaptation.narrative_reading.event.action,
        )
        self.assertEqual(
            "pasillo",
            adaptation.narrative_reading.event.environment,
        )
        self.assertIn(
            "LegacyStoryboardScene.subject",
            adaptation.trace_references,
        )
        self.assertIn(
            "LegacyStoryboardScene.action",
            adaptation.trace_references,
        )
        self.assertIn(
            "LegacyStoryboardScene.setting",
            adaptation.trace_references,
        )

    def test_runtime_visual_truth_scene_does_not_mix_legacy_fallbacks(self):
        scene = StoryboardScene(
            scene_number=10,
            text="Una escena parcialmente estructurada.",
            subject="legacy subject",
            action="legacy action",
            setting="legacy setting",
            filmable_interpretation="un objeto espera sobre una mesa",
            visual_truth_status="structured",
        )

        adaptation = RuntimeCognitiveAdapter.from_storyboard_scene(
            storyboard_scene=scene,
            legacy_visual_idea="legacy idea",
        )

        self.assertEqual(
            "un objeto espera sobre una mesa",
            adaptation.visual_brief.visible_content,
        )
        self.assertEqual(
            "",
            adaptation.visual_brief.primary_subject,
        )
        self.assertEqual(
            "",
            adaptation.visual_brief.staging.main_subject,
        )
        self.assertEqual(
            "",
            adaptation.visual_brief.staging.action_or_state,
        )
        self.assertEqual(
            "",
            adaptation.visual_brief.staging.environment,
        )
        self.assertEqual(
            "",
            adaptation.narrative_reading.event.subject,
        )
        self.assertEqual(
            "",
            adaptation.narrative_reading.event.action,
        )
        self.assertEqual(
            "",
            adaptation.narrative_reading.event.environment,
        )
        self.assertEqual(
            "visual_truth_2_0",
            adaptation.narrative_reading.event.source_model,
        )
        self.assertNotIn(
            "LegacyStoryboardScene.subject",
            adaptation.trace_references,
        )
        self.assertNotIn(
            "LegacyStoryboardScene.action",
            adaptation.trace_references,
        )
        self.assertNotIn(
            "LegacyStoryboardScene.setting",
            adaptation.trace_references,
        )

    def test_runtime_narrative_reading_is_deterministic_and_does_not_mutate_scene(self):
        scene = StoryboardScene(
            scene_number=11,
            text="Una escena determinista.",
            visible_subject="figura ante una puerta",
            visible_action="abre una puerta metalica",
            visible_environment="pasillo industrial",
            key_objects=(
                "puerta metalica",
            ),
            spatial_relationships=(
                "la figura queda frente a la puerta",
            ),
            continuity_links=(
                "misma puerta",
            ),
            visual_truth_status="structured",
        )

        first = RuntimeCognitiveAdapter.narrative_reading_from_scene(
            scene
        )
        second = RuntimeCognitiveAdapter.narrative_reading_from_scene(
            scene
        )

        self.assertEqual(
            first,
            second,
        )
        self.assertEqual(
            "figura ante una puerta",
            scene.visible_subject,
        )
        self.assertEqual(
            (
                "puerta metalica",
            ),
            scene.key_objects,
        )

    def test_orientation_guidance_is_deterministic_and_explicit(self):
        self.assertEqual(
            "vertical 9:16",
            RuntimeCognitiveAdapter.composition_guidance_from_orientation(
                "vertical"
            ),
        )
        self.assertEqual(
            "wide horizontal 16:9",
            RuntimeCognitiveAdapter.composition_guidance_from_orientation(
                "horizontal"
            ),
        )
        self.assertEqual(
            "",
            RuntimeCognitiveAdapter.composition_guidance_from_orientation(
                "square"
            ),
        )


if __name__ == "__main__":
    unittest.main()
