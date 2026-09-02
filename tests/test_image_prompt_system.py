import inspect
import unittest

from app.modules.images.prompt_system import ImagePromptSystem


class ImagePromptSystemTest(unittest.TestCase):

    def test_cinematic_backend_prompt_preserves_payload_and_adds_operational_constraints(self):
        prompt = ImagePromptSystem().compose_cinematic_backend_prompt(
            "A person reading an open book"
        )

        self.assertIn(
            "A person reading an open book",
            prompt,
        )
        self.assertIn(
            "professional cinematic realism",
            prompt,
        )
        self.assertIn(
            "Do not add people, faces, or human figures unless the supplied visual scene explicitly requires them",
            prompt,
        )
        self.assertIn(
            "preserve only those people",
            prompt,
        )
        self.assertIn(
            "stated geographic, cultural, historical, and narrative context",
            prompt,
        )
        self.assertIn(
            "European or Mediterranean, Asian, African, Latin American",
            prompt,
        )
        self.assertIn(
            "natural human variation without making a single phenotype dominant",
            prompt,
        )
        self.assertIn(
            "repeated East Asian facial archetypes when unsupported by the scene context",
            prompt,
        )
        self.assertIn(
            "realistic skin texture, subtle imperfections, expressive eyes",
            prompt,
        )
        self.assertIn(
            "no crop top",
            prompt,
        )
        self.assertIn(
            "no text on books",
            prompt,
        )

    def test_object_scene_explicitly_rejects_unrequested_human_presence(self):
        prompt = ImagePromptSystem().compose_cinematic_backend_prompt(
            "A cracked porcelain cup sits alone on a dusty kitchen table"
        )

        self.assertTrue(
            prompt.startswith(
                "A cracked porcelain cup sits alone on a dusty kitchen table"
            )
        )
        self.assertIn(
            "Do not add people, faces, or human figures unless the supplied visual scene explicitly requires them",
            prompt,
        )

    def test_human_scene_does_not_receive_non_human_direction(self):
        prompt = ImagePromptSystem().compose_cinematic_backend_prompt(
            "A person reading an open book"
        )

        self.assertIn(ImagePromptSystem.human_casting_policy, prompt)
        self.assertNotIn(
            "Non-human architectural direction",
            prompt,
        )
        self.assertNotIn(
            "Non-human symbolic object direction",
            prompt,
        )

    def test_non_human_scene_families_receive_specific_visual_direction(self):
        cases = (
            (
                "An ancient temple rises above a misty valley",
                "Non-human architectural direction",
                "credible spatial scale, layered depth",
                "flat backdrops, generic buildings",
            ),
            (
                "A weathered bronze amulet rests on dark velvet",
                "Non-human symbolic object direction",
                "clear visual protagonist",
                "lost object, flat lighting",
            ),
            (
                "A detailed human brain with visible neural pathways",
                "Non-human scientific and anatomical direction",
                "clean convincing structure, readable volume",
                "soft deformed forms, generic illustration",
            ),
            (
                "A controlled field of blue electric energy fills the frame",
                "Non-human energy and abstraction direction",
                "controlled layered composition",
                "gratuitous chaos, oversaturation",
            ),
            (
                "A luminous geometric symbol is suspended in darkness",
                "Non-human symbolic geometry direction",
                "clear and legible through refined balance",
                "floating symbols without design",
            ),
        )

        for source, title, quality, avoidance in cases:
            with self.subTest(source=source):
                prompt = ImagePromptSystem().compose_cinematic_backend_prompt(
                    source
                )

                self.assertTrue(prompt.startswith(source))
                self.assertIn(title, prompt)
                self.assertIn(quality, prompt)
                self.assertIn(avoidance, prompt)
                self.assertIn(
                    "professional cinematic realism",
                    prompt,
                )

    def test_non_human_direction_keeps_prompt_parts_in_existing_order(self):
        source = "A precise scientific structure of a glowing neuron"
        prompt = ImagePromptSystem().compose_cinematic_backend_prompt(
            source
        )

        self.assertLess(
            prompt.index(source),
            prompt.index("professional cinematic realism"),
        )
        self.assertLess(
            prompt.index("professional cinematic realism"),
            prompt.index("Non-human scientific and anatomical direction"),
        )
        self.assertLess(
            prompt.index("Non-human scientific and anatomical direction"),
            prompt.index("fully clothed"),
        )
    def test_human_casting_policy_preserves_context_and_avoids_generic_archetypes(self):
        prompt = ImagePromptSystem().compose_cinematic_backend_prompt(
            "A Mediterranean historian studies a manuscript in a coastal archive"
        )

        for expected in (
            "Honor explicit European or Mediterranean, Asian, African, Latin American, or other cultural context naturally",
            "do not impose an unrelated default ethnicity",
            "natural human variation without making a single phenotype dominant",
            "distinctive facial structure",
            "generic stock-looking faces",
            "identical-looking characters across scenes",
        ):
            self.assertIn(
                expected,
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
