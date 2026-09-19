import inspect
import unittest

from app.modules.images.prompt_system import (
    ImagePromptSystem,
    OperationalPromptRule,
)


class ImagePromptSystemTest(unittest.TestCase):

    def test_human_prompt_preserves_protected_invariants(self):
        prompt = ImagePromptSystem().compose_cinematic_backend_prompt(
            "A person reading an open book"
        )

        self.assertIn(
            "A person reading an open book",
            prompt,
        )
        for invariant in (
            "professional photorealism",
            "Use only described people",
            "declared age, appearance, cultural, historical, narrative, and continuity cues",
            "Natural anatomy, accurate hands, distinctive non-generic faces",
            "Fully clothed, non-revealing, appropriate wardrobe; no sexualization",
            "No text, logos, watermarks, or readable writing",
        ):
            self.assertIn(
                invariant,
                prompt,
            )

    def test_object_scene_uses_nonhuman_guard_instead_of_human_rules(self):
        prompt_system = ImagePromptSystem()
        composition = prompt_system.compose_cinematic_backend_prompt_with_parts(
            "A cracked porcelain cup sits alone on a dusty kitchen table"
        )
        rule_ids = {
            rule.id
            for rule in composition.rules
        }

        self.assertTrue(
            composition.prompt.startswith(
                "A cracked porcelain cup sits alone on a dusty kitchen table"
            )
        )
        self.assertIn(
            "casting.non_human.no_extra_people",
            rule_ids,
        )
        self.assertNotIn(
            "casting.human.subject",
            rule_ids,
        )
        self.assertNotIn(
            "safety.human.wardrobe",
            rule_ids,
        )

    def test_human_scene_does_not_receive_nonhuman_direction(self):
        composition = ImagePromptSystem().compose_cinematic_backend_prompt_with_parts(
            "A person reading an open book"
        )
        rule_ids = {
            rule.id
            for rule in composition.rules
        }

        self.assertIn(
            "casting.human.subject",
            rule_ids,
        )
        self.assertFalse(
            any(
                rule_id.startswith(
                    "direction.non_human."
                )
                for rule_id in rule_ids
            )
        )

    def test_nonhuman_scene_families_receive_specific_protected_direction(self):
        cases = (
            (
                "An ancient temple rises above a misty valley",
                "direction.non_human.architecture",
                "Credible architectural scale, layered depth",
                "avoid flat generic backdrops",
            ),
            (
                "A weathered bronze amulet rests on dark velvet",
                "direction.non_human.symbolic_object",
                "clear focal point",
                "avoid competing focal points",
            ),
            (
                "A detailed human brain with visible neural pathways",
                "direction.non_human.anatomical_scientific",
                "convincing structure, readable volume",
                "avoid deformed, generic, or chaotic forms",
            ),
            (
                "A controlled field of blue electric energy fills the frame",
                "direction.non_human.energy_abstract",
                "controlled layered composition",
                "avoid chaos, oversaturation",
            ),
            (
                "A luminous geometric symbol is suspended in darkness",
                "direction.non_human.symbolic_geometry",
                "geometry clear and legible through refined balance",
                "avoid floating symbols, visual noise",
            ),
        )

        for source, rule_id, quality, avoidance in cases:
            with self.subTest(
                source=source,
            ):
                composition = (
                    ImagePromptSystem().compose_cinematic_backend_prompt_with_parts(
                        source
                    )
                )

                self.assertTrue(
                    composition.prompt.startswith(source)
                )
                self.assertIn(
                    rule_id,
                    {
                        rule.id
                        for rule in composition.rules
                    },
                )
                self.assertIn(quality, composition.prompt)
                self.assertIn(avoidance, composition.prompt)
                self.assertIn(
                    "professional photorealism",
                    composition.prompt,
                )

    def test_nonhuman_direction_precedes_final_text_safety_rule(self):
        source = "A precise scientific structure of a glowing neuron"
        prompt = ImagePromptSystem().compose_cinematic_backend_prompt(
            source
        )

        self.assertLess(
            prompt.index(source),
            prompt.index("professional photorealism"),
        )
        self.assertLess(
            prompt.index("professional photorealism"),
            prompt.index("Present the declared subject with convincing structure"),
        )
        self.assertLess(
            prompt.index("Present the declared subject with convincing structure"),
            prompt.index("No text, logos, watermarks, or readable writing"),
        )

    def test_context_and_continuity_remain_human_casting_invariants(self):
        for source in (
            "A Mediterranean historian studies a manuscript in a coastal archive",
            "The same research team returns to the laboratory at dawn",
            "A scientist studies a luminous instrument in a quiet laboratory",
        ):
            with self.subTest(
                source=source,
            ):
                prompt = ImagePromptSystem().compose_cinematic_backend_prompt(
                    source
                )
                self.assertIn(
                    "declared age, appearance, cultural, historical, narrative, and continuity cues",
                    prompt,
                )
                self.assertIn(
                    "distinctive non-generic faces",
                    prompt,
                )

    def test_prompt_parts_are_deduplicated_without_reordering(self):
        prompt_system = ImagePromptSystem()

        self.assertEqual(
            [
                "alpha",
                "beta",
                "gamma",
            ],
            prompt_system.dedupe_prompt_parts(
                (
                    "alpha",
                    "beta",
                    "Alpha",
                    "",
                    None,
                    "gamma",
                )
            ),
        )

    def test_atomic_rules_are_protected_and_carry_their_operational_contract(self):
        rules = ImagePromptSystem().operational_rules_for_prompt(
            "A scientist studies an artifact in a laboratory"
        )

        self.assertEqual(
            len(rules),
            len(
                {
                    rule.id
                    for rule in rules
                }
            ),
        )
        for rule in rules:
            self.assertIsInstance(
                rule,
                OperationalPromptRule,
            )
            self.assertTrue(rule.protected)
            self.assertTrue(rule.conditions)
            self.assertEqual(
                "ImagePromptSystem",
                rule.source,
            )
            self.assertGreater(
                rule.estimated_token_cost,
                0,
            )

    def test_prompt_system_has_no_backend_dependencies(self):
        source = inspect.getsource(
            ImagePromptSystem
        )

        for forbidden in (
            "ComfyUI",
            "urllib",
            "Request",
            "workflow",
            "manifest",
            "Wan",
            "VideoPromptTranslator",
        ):
            self.assertNotIn(
                forbidden,
                source,
            )

    def test_prompt_system_has_no_legacy_prompt_api(self):
        prompt_system = ImagePromptSystem()

        self.assertFalse(
            hasattr(
                prompt_system,
                "build_legacy_prompt",
            )
        )
        self.assertFalse(
            hasattr(
                prompt_system,
                "compose_backend_prompt",
            )
        )


if __name__ == "__main__":
    unittest.main()
