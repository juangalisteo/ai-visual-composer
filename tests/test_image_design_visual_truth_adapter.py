import unittest
from pathlib import Path

from app.domain.adapters import StoryboardSceneAdapter
from app.modules.images import (
    ImageDesignVisualTruthAdapter,
    PreparedImageDesign,
)


class ImageDesignVisualTruthAdapterTest(unittest.TestCase):

    def test_adapts_manual_design_to_single_visual_truth_scene(self):
        text = (
            "Plano hiperrealista de una torre electrica bajo "
            "una tormenta nocturna."
        )
        prepared = PreparedImageDesign(
            text=text,
            source_path=Path("input/guion_imagen.txt"),
            visual_truth={
                "scene": 1,
                "visible_subject": "torre electrica",
                "visible_action": (
                    "permanece bajo una tormenta nocturna"
                ),
                "visible_environment": "paisaje nocturno tormentoso",
                "time_context": "noche",
                "key_objects": (
                    "torre electrica",
                    "rayos",
                ),
                "spatial_relationships": (),
                "continuity_links": (),
                "abstract_source": text,
                "filmable_interpretation": (
                    "Una torre electrica se eleva bajo "
                    "una tormenta nocturna con rayos."
                ),
                "visual_constraints": (),
                "visual_truth_status": (
                    "manual_design_interpreted"
                )
            }
        )

        scenes = ImageDesignVisualTruthAdapter().adapt(
            prepared
        )

        self.assertEqual(
            1,
            len(scenes)
        )
        scene = scenes[0]
        self.assertEqual(
            1,
            scene["scene"]
        )
        self.assertEqual(
            text,
            scene["text"]
        )
        self.assertEqual(
            "torre electrica",
            scene["visible_subject"]
        )
        self.assertIn(
            "tormenta",
            scene["visible_action"]
        )
        self.assertIn(
            "nocturno",
            scene["visible_environment"]
        )
        self.assertIn(
            "rayos",
            scene["filmable_interpretation"]
        )
        self.assertEqual(
            text,
            scene["abstract_source"]
        )
        self.assertEqual(
            "manual_design_interpreted",
            scene["visual_truth_status"]
        )

    def test_output_is_compatible_with_storyboard_scene_adapter(self):
        prepared = PreparedImageDesign(
            text="Interior realista de laboratorio con luz azul.",
            source_path=Path("input/guion_imagen.txt"),
            visual_truth={
                "scene": 1,
                "visible_subject": "laboratorio con luz azul",
                "visible_action": "la luz azul ilumina el interior",
                "visible_environment": "laboratorio realista",
                "time_context": "",
                "key_objects": (
                    "luz azul",
                ),
                "spatial_relationships": (),
                "continuity_links": (),
                "abstract_source": (
                    "Interior realista de laboratorio con luz azul."
                ),
                "filmable_interpretation": (
                    "Un laboratorio realista queda iluminado "
                    "por una luz azul."
                ),
                "visual_constraints": (),
                "visual_truth_status": (
                    "manual_design_interpreted"
                )
            }
        )

        scenes = ImageDesignVisualTruthAdapter().adapt(
            prepared
        )
        storyboard_scene = StoryboardSceneAdapter.from_visual_truth(
            scene=scenes[0],
            default_scene_number=1
        )

        self.assertEqual(
            1,
            storyboard_scene.scene_number
        )
        self.assertEqual(
            "laboratorio con luz azul",
            storyboard_scene.visible_subject
        )
        self.assertEqual(
            "manual_design_interpreted",
            storyboard_scene.visual_truth_status
        )

    def test_fails_when_expected_images_is_not_one(self):
        prepared = PreparedImageDesign(
            text="Una descripcion visual.",
            source_path=Path("input/guion_imagen.txt"),
            visual_truth={
                "scene": 1,
                "visible_subject": "sujeto",
                "visible_action": "accion",
                "visible_environment": "entorno",
                "filmable_interpretation": "escena",
            },
            expected_images=2
        )

        with self.assertRaises(
            ValueError
        ):
            ImageDesignVisualTruthAdapter().adapt(
                prepared
            )


if __name__ == "__main__":
    unittest.main()
