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

    def test_storyboard_adapter_preserves_visual_truth_contract(self):
        scene = StoryboardSceneAdapter.from_visual_truth(
            scene={
                "scene": "2",
                "text": "La escena conserva su texto.",
                "duration": 4.5,
                "visible_subject": "quiet valley",
                "visible_action": "dawn light spreads slowly",
                "visible_environment": "mountain landscape",
                "filmable_interpretation": "A quiet dawn over a valley",
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
                visible_subject="quiet valley",
                visible_action="dawn light spreads slowly",
                visible_environment="mountain landscape",
                filmable_interpretation="A quiet dawn over a valley",
            ),
        )
        self.assertEqual(
            "structured",
            scene.visual_truth_status,
        )
        self.assertEqual(
            "quiet valley",
            scene.visible_subject,
        )

    def test_storyboard_adapter_preserves_storyboard_scene_2_fields(self):
        scene = StoryboardSceneAdapter.from_visual_truth(
            scene={
                "scene": "3",
                "text": "La escena conserva su texto.",
                "narrative_role": "revelacion",
                "narrative_moment": "inicio",
                "notes": "mantener calma",
                "visible_subject": "investigadora adulta",
                "visible_action": "observa una llave de bronce",
                "visible_environment": "biblioteca antigua",
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
            "biblioteca antigua",
            scene.visible_environment,
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

    def test_storyboard_adapter_rejects_missing_visual_truth(self):
        with self.assertRaisesRegex(
            ValueError,
            "visible_subject",
        ):
            StoryboardSceneAdapter.from_visual_truth(
                scene={
                    "scene": "4",
                    "text": "Escena sin Visual Truth.",
                },
                default_scene_number=1,
            )

    def test_storyboard_adapter_is_deterministic_and_does_not_mutate_input(self):
        raw_scene = {
            "scene": "5",
            "text": " Escena determinista. ",
            "visible_subject": " sujeto ",
            "visible_action": " accion ",
            "visible_environment": " entorno ",
            "filmable_interpretation": " escena filmable ",
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

        first = StoryboardSceneAdapter.from_visual_truth(
            scene=raw_scene,
            default_scene_number=1,
        )
        second = StoryboardSceneAdapter.from_visual_truth(
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
                visible_subject="una persona",
                visible_action="observa una llave",
                visible_environment="una biblioteca",
                filmable_interpretation="A person observing an old key",
                duration=5.0,
                source_index=1,
            ),
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

    def test_runtime_cognitive_adapter_rejects_missing_visual_truth(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Escena sin contrato visual estructurado",
        )

        with self.assertRaisesRegex(
            ValueError,
            "Visual Truth 2.0",
        ):
            RuntimeCognitiveAdapter.from_storyboard_scene(
                scene
            )

    def test_runtime_cognitive_adapter_preserves_visual_truth_2_fields(self):
        scene = StoryboardScene(
            scene_number=7,
            text="Una idea abstracta se vuelve visible.",
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
            "subject/action/setting",
            reading.facts.existing_elements,
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
