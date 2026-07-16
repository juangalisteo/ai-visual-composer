import unittest

from app.modules.images.safe_visual_policy import SafeVisualPolicy


class SafeVisualPolicyTest(unittest.TestCase):

    def test_appends_clothing_guidance_for_human_subjects(self):
        result = SafeVisualPolicy().apply(
            positive_prompt=(
                "A woman walking through a cinematic city street"
            )
        )

        self.assertTrue(
            result.human_subject
        )
        self.assertIn(
            "fully clothed",
            result.positive_prompt
        )
        self.assertIn(
            "elegant clothing",
            result.positive_prompt
        )
        self.assertIn(
            "non-revealing clothing",
            result.positive_prompt
        )

    def test_appends_global_negative_prompt(self):
        result = SafeVisualPolicy().apply(
            positive_prompt="A cinematic mountain landscape",
            negative_prompt="no text"
        )

        for term in (
            "nudity",
            "nude",
            "naked",
            "topless",
            "bottomless",
            "bare breasts",
            "nipples",
            "genitals",
            "transparent clothing",
            "lingerie",
            "underwear",
            "bikini",
            "fetish",
            "erotic",
            "sexualized",
            "suggestive pose",
            "provocative",
            "nsfw",
            "porn",
            "explicit",
            "uncensored"
        ):
            with self.subTest(
                term=term
            ):
                self.assertIn(
                    term,
                    result.negative_prompt
                )

    def test_rewrites_unsafe_positive_prompt(self):
        result = SafeVisualPolicy().apply(
            positive_prompt=(
                "A nude woman in transparent clothing, "
                "suggestive pose, cinematic lighting"
            )
        )

        self.assertTrue(
            result.rewritten
        )
        self.assertIn(
            "nude",
            result.violations
        )
        self.assertIn(
            "transparent clothing",
            result.violations
        )
        self.assertIn(
            "suggestive pose",
            result.violations
        )
        self.assertNotIn(
            "nude woman",
            result.positive_prompt.lower()
        )
        self.assertNotIn(
            "transparent clothing",
            result.positive_prompt.lower()
        )
        self.assertNotIn(
            "suggestive pose",
            result.positive_prompt.lower()
        )
        self.assertIn(
            "fully clothed",
            result.positive_prompt
        )

    def test_validation_rejects_unsafe_prompt(self):
        with self.assertRaises(ValueError):
            SafeVisualPolicy().validate(
                "A topless portrait"
            )


if __name__ == "__main__":
    unittest.main()
