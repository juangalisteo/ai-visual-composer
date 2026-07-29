import unittest

from app.domain import StoryboardScene, VisualPriority
from app.visual_intelligence import (
    VisualPriorityResolver,
    VisualSemanticsResolver,
    VisualTruthInspector,
)


def priority_scene():
    return StoryboardScene(
        scene_number=1,
        text="Una investigadora recibe una llave antigua.",
        visible_subject="investigadora con abrigo gris",
        visible_action="recibe una llave antigua",
        visible_environment="archivo subterraneo",
        key_objects=(
            "llave antigua",
            "sobre lacrado",
        ),
        spatial_relationships=(
            "la llave queda entre ambas manos",
        ),
        filmable_interpretation="una llave cambia de manos",
    )


def resolve_priority(scene):
    inspection = VisualTruthInspector().inspect(
        scene
    )
    semantics = VisualSemanticsResolver().resolve(
        scene,
        inspection
    )
    return VisualPriorityResolver().resolve(
        scene,
        inspection,
        semantics
    )


class VisualPriorityResolverTest(unittest.TestCase):

    def test_prioritizes_object_directly_present_in_action(self):
        priority = resolve_priority(
            priority_scene()
        )

        self.assertIsInstance(
            priority,
            VisualPriority
        )
        self.assertEqual(
            priority.primary_priority,
            "llave antigua"
        )
        self.assertEqual(
            priority.attention_focus,
            "llave antigua"
        )
        self.assertEqual(
            priority.visual_hierarchy[0],
            "llave antigua"
        )

    def test_uses_subject_when_no_object_is_action_target(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Retrato ambiental",
            visible_subject="arquitecta",
            visible_action="observa el horizonte",
            visible_environment="azotea",
            key_objects=(
                "brujula",
            ),
            filmable_interpretation="arquitecta observa el horizonte",
        )

        priority = resolve_priority(
            scene
        )

        self.assertEqual(
            priority.primary_priority,
            "arquitecta"
        )

    def test_single_environment_scene_has_stable_priority(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Escena ambiental",
            visible_environment="bosque nevado",
            filmable_interpretation="bosque nevado en calma",
        )

        priority = resolve_priority(
            scene
        )

        self.assertEqual(
            priority.primary_priority,
            "bosque nevado"
        )

    def test_unknown_priority_when_no_candidates_exist(self):
        scene = StoryboardScene(
            scene_number=1,
            text="Sin datos"
        )

        priority = resolve_priority(
            scene
        )

        self.assertEqual(
            priority.primary_priority,
            "unknown"
        )
        self.assertEqual(
            priority.attention_focus,
            ""
        )

    def test_priority_order_is_deterministic(self):
        scene = priority_scene()

        first = resolve_priority(
            scene
        )
        second = resolve_priority(
            scene
        )

        self.assertEqual(
            first.visual_hierarchy,
            second.visual_hierarchy
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_supporting_elements_exclude_primary(self):
        priority = resolve_priority(
            priority_scene()
        )

        self.assertNotIn(
            priority.primary_priority,
            priority.supporting_elements
        )
        self.assertIn(
            "archivo subterraneo",
            priority.supporting_elements
        )

    def test_rejects_invalid_inputs(self):
        scene = priority_scene()
        inspection = VisualTruthInspector().inspect(
            scene
        )

        with self.assertRaises(
            TypeError
        ):
            VisualPriorityResolver().resolve(
                scene,
                inspection,
                "invalid"
            )


if __name__ == "__main__":
    unittest.main()
