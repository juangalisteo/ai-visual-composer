import unittest
from pathlib import Path

from app.domain import StoryboardScene
from app.modules.video_component import (
    MinimalVisualContext,
    MotionIntentBuilder,
)


class MotionIntentBuilderTest(unittest.TestCase):

    def _context(self):
        return MinimalVisualContext(
            source_path=Path("tests/fixtures/video/source.png"),
            width=1920,
            height=1080,
            aspect_ratio="16:9",
            orientation="landscape",
            image_format="PNG",
            stability_constraints=(
                "preserve_source_composition",
                "preserve_source_geometry",
            )
        )

    def test_builds_conservative_motion_intent(self):
        motion = MotionIntentBuilder().build(
            self._context()
        )

        self.assertEqual(
            "subtle",
            motion.motion_intensity
        )
        self.assertEqual(
            "subtle",
            motion.motion_level
        )
        self.assertEqual(
            "very high",
            motion.stability
        )
        self.assertEqual(
            "slow micro camera drift",
            motion.camera_motion
        )
        self.assertIn(
            "no invented action",
            motion.avoidance_constraints
        )
        self.assertIn(
            "preserve_original_framing",
            motion.preservation_constraints
        )

    def test_motion_intent_is_deterministic(self):
        storyboard_scene = StoryboardScene(
            scene_number=1,
            text="Una investigadora abre un archivo antiguo.",
            visible_subject="una investigadora",
            visible_action="abre un archivo antiguo",
            visible_environment="archivo historico",
            filmable_interpretation="accion contenida y legible",
        )
        builder = MotionIntentBuilder()
        first = builder.build(
            self._context(),
            storyboard_scene=storyboard_scene,
        )
        second = builder.build(
            self._context(),
            storyboard_scene=storyboard_scene,
        )

        self.assertEqual(
            first,
            second
        )

    def test_portraits_and_static_objects_use_subtle_motion(self):
        scenes = (
            StoryboardScene(
                scene_number=1,
                text="Una mujer contempla el mar.",
                visible_subject="retrato de una mujer",
                visible_action="contempla el mar",
                visible_environment="mirador costero",
                visual_constraints=(
                    "static composition",
                ),
            ),
            StoryboardScene(
                scene_number=2,
                text="Una copa antigua descansa sobre una mesa.",
                visible_subject="una copa antigua",
                visible_action="rests on a table",
                visible_environment="interior silencioso",
            ),
        )

        for storyboard_scene in scenes:
            with self.subTest(
                scene=storyboard_scene.scene_number
            ):
                motion = MotionIntentBuilder().build(
                    self._context(),
                    storyboard_scene=storyboard_scene,
                )

                self.assertEqual(
                    "subtle",
                    motion.motion_level
                )
                self.assertEqual(
                    "slow micro camera drift",
                    motion.camera_motion
                )
                self.assertEqual(
                    "very high",
                    motion.stability
                )

    def test_moderate_action_uses_normal_motion(self):
        motion = MotionIntentBuilder().build(
            self._context(),
            storyboard_scene=StoryboardScene(
                scene_number=1,
                text="Una investigadora abre un archivo.",
                visible_subject="una investigadora",
                visible_action="abre un archivo antiguo",
                visible_environment="archivo historico",
            ),
        )

        self.assertEqual(
            "normal",
            motion.motion_level
        )
        self.assertEqual(
            "gentle slow push-in",
            motion.camera_motion
        )
        self.assertEqual(
            "moderate",
            motion.motion_intensity
        )

    def test_clear_dynamic_action_uses_intense_motion(self):
        motion = MotionIntentBuilder().build(
            self._context(),
            storyboard_scene=StoryboardScene(
                scene_number=1,
                text="Una atleta corre por una pista.",
                visible_subject="una atleta",
                visible_action="corre por una pista mojada",
                visible_environment="estadio nocturno",
            ),
        )

        self.assertEqual(
            "intense",
            motion.motion_level
        )
        self.assertEqual(
            "controlled short tracking move",
            motion.camera_motion
        )
        self.assertEqual(
            "strong but controlled",
            motion.motion_intensity
        )
        self.assertEqual(
            "dynamic but stable",
            motion.temporal_rhythm
        )

    def test_ambiguous_scene_uses_subtle_motion(self):
        motion = MotionIntentBuilder().build(
            self._context(),
            storyboard_scene=StoryboardScene(
                scene_number=1,
                text="Una figura aparece junto a una ventana.",
                visible_subject="una figura",
                visible_environment="habitacion al amanecer",
                filmable_interpretation="escena cinematica contemplativa",
            ),
        )

        self.assertEqual(
            "subtle",
            motion.motion_level
        )

    def test_camera_policy_never_uses_orbit_shake_or_multiple_moves(self):
        scenes = (
            StoryboardScene(
                scene_number=1,
                text="Un retrato contemplativo.",
                visible_subject="un cientifico",
                visible_action="contempla una maquina",
            ),
            StoryboardScene(
                scene_number=2,
                text="Una investigadora abre una puerta.",
                visible_subject="una investigadora",
                visible_action="abre una puerta",
            ),
            StoryboardScene(
                scene_number=3,
                text="Una atleta corre.",
                visible_subject="una atleta",
                visible_action="corre por la pista",
            ),
        )

        for storyboard_scene in scenes:
            with self.subTest(
                scene=storyboard_scene.scene_number
            ):
                camera_motion = MotionIntentBuilder().build(
                    self._context(),
                    storyboard_scene=storyboard_scene,
                ).camera_motion.lower()

                self.assertNotIn("orbit", camera_motion)
                self.assertNotIn("shake", camera_motion)
                self.assertNotIn(" and ", camera_motion)

    def test_motion_intent_does_not_invent_semantic_content(self):
        motion = MotionIntentBuilder().build(
            self._context()
        )
        serialized = " ".join(
            (
                motion.camera_motion,
                motion.motion_intensity,
                motion.stability,
                motion.temporal_rhythm,
                " ".join(
                    motion.preservation_constraints
                ),
                " ".join(
                    motion.avoidance_constraints
                ),
            )
        ).lower()

        for forbidden in (
            "person",
            "lamp",
            "face",
            "breathing",
            "flicker",
        ):
            self.assertNotIn(
                forbidden,
                serialized
            )

    def test_storyboard_scene_adds_preservation_trace(self):
        storyboard_scene = StoryboardScene(
            scene_number=1,
            text="Nikola Tesla en su laboratorio.",
            visible_subject="Nikola Tesla",
            visible_action="sentado junto a una lampara iluminada",
            visible_environment="laboratorio electrico",
            key_objects=(
                "lampara",
                "bobina",
            ),
            filmable_interpretation="escena cinematica realista",
        )

        motion = MotionIntentBuilder().build(
            self._context(),
            storyboard_scene=storyboard_scene
        )

        self.assertIn(
            (
                "preserve_storyboard_visible_subject: "
                "Nikola Tesla"
            ),
            motion.preservation_constraints
        )
        self.assertIn(
            "StoryboardScene.visible_subject",
            motion.source_trace
        )
        self.assertIn(
            "no subject beyond StoryboardScene.visible_subject",
            motion.avoidance_constraints
        )


if __name__ == "__main__":
    unittest.main()
