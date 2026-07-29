import unittest

from app.domain import (
    GenerationResult,
    StoryboardScene,
)
from app.domain.adapters import (
    GenerationResultAdapter,
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

if __name__ == "__main__":
    unittest.main()
