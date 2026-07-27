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
            "natural anatomy",
            prompt,
        )
        self.assertIn(
            "accurate hands",
            prompt,
        )
        self.assertIn(
            "stable character identity when repeated across scenes",
            prompt,
        )
        self.assertIn(
            "preserve described face, age, hairstyle, body type and clothing across scene sequence",
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
