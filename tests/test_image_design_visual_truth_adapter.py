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
            source_path=Path("input/guion_imagen.txt")
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
            text,
            scene["visible_subject"]
        )
        self.assertEqual(
            text,
            scene["visible_action"]
        )
        self.assertEqual(
            text,
            scene["visible_environment"]
        )
        self.assertEqual(
            text,
            scene["filmable_interpretation"]
        )
        self.assertEqual(
            text,
            scene["abstract_source"]
        )
        self.assertEqual(
            "manual_design",
            scene["visual_truth_status"]
        )

    def test_output_is_compatible_with_storyboard_scene_adapter(self):
        prepared = PreparedImageDesign(
            text="Interior realista de laboratorio con luz azul.",
            source_path=Path("input/guion_imagen.txt")
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
            "Interior realista de laboratorio con luz azul.",
            storyboard_scene.visible_subject
        )
        self.assertEqual(
            "manual_design",
            storyboard_scene.visual_truth_status
        )

    def test_fails_when_expected_images_is_not_one(self):
        prepared = PreparedImageDesign(
            text="Una descripcion visual.",
            source_path=Path("input/guion_imagen.txt"),
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
