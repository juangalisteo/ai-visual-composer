import unittest

from app.modules.visual_director import (
    VisualDirectionContext,
    VisualDirector
)


class VisualDirectorTest(unittest.TestCase):

    def test_builds_directed_prompt_from_scene_context(self):
        director = VisualDirector()

        result = director.direct(
            VisualDirectionContext(
                scene_text=(
                    "Una persona comprende su miedo "
                    "mientras aparece una luz en el cielo."
                ),
                visual_idea=(
                    "A lone person standing on a mountain "
                    "under a cosmic sky"
                ),
                duration=4.0,
                scene_index=1,
                scene_count=3,
                orientation="horizontal"
            )
        )

        self.assertIn(
            "A lone person standing on a mountain",
            result.positive_prompt
        )
        self.assertIn(
            "narrative context",
            result.positive_prompt
        )
        self.assertIn(
            "wide horizontal 16:9",
            result.positive_prompt
        )
        self.assertIn(
            "avoid:",
            result.final_prompt
        )
        self.assertTrue(
            result.directives["composition"]
        )
        self.assertTrue(
            result.directives["camera"]
        )
        self.assertTrue(
            result.directives["lens"]
        )
        self.assertIn(
            "lens",
            result.positive_prompt
        )

    def test_negative_prompt_prevents_text_and_branding(self):
        director = VisualDirector()

        result = director.direct(
            VisualDirectionContext(
                scene_text="Silencio interior.",
                visual_idea="A quiet room with soft light",
                duration=3.0,
                scene_index=1,
                scene_count=1,
                orientation="horizontal"
            )
        )

        self.assertIn(
            "no text",
            result.negative_prompt
        )
        self.assertIn(
            "no logos",
            result.negative_prompt
        )
        self.assertIn(
            "no watermark",
            result.negative_prompt
        )
        self.assertIn(
            "nudity",
            result.negative_prompt
        )
        self.assertIn(
            "nsfw",
            result.negative_prompt
        )

    def test_human_subject_receives_safe_clothing_guidance(self):
        director = VisualDirector()

        result = director.direct(
            VisualDirectionContext(
                scene_text="Una persona camina en silencio.",
                visual_idea="A woman walking through a quiet station",
                duration=3.0,
                scene_index=1,
                scene_count=1,
                orientation="horizontal"
            )
        )

        self.assertIn(
            "fully clothed",
            result.positive_prompt
        )
        self.assertIn(
            "modest clothing",
            result.positive_prompt
        )
        self.assertIn(
            "cinematic wardrobe",
            result.positive_prompt
        )
        self.assertIn(
            "editorial art direction",
            result.positive_prompt
        )

    def test_human_subject_receives_general_human_art_direction(self):
        director = VisualDirector()

        result = director.direct(
            VisualDirectionContext(
                scene_text="Una persona medita antes del amanecer.",
                visual_idea="A person meditating in a minimal room",
                duration=4.0,
                scene_index=1,
                scene_count=1,
                orientation="horizontal"
            )
        )

        self.assertIn(
            "human art direction",
            result.positive_prompt
        )
        self.assertIn(
            "credible human presence",
            result.positive_prompt
        )
        self.assertIn(
            "natural body language",
            result.positive_prompt
        )
        self.assertIn(
            "balanced posture",
            result.positive_prompt
        )
        self.assertIn(
            "believable anatomy",
            result.positive_prompt
        )
        self.assertIn(
            "subtle facial expression",
            result.positive_prompt
        )
        self.assertIn(
            "coherent gaze",
            result.positive_prompt
        )
        self.assertIn(
            "realistic skin and hair",
            result.positive_prompt
        )
        self.assertIn(
            "context-appropriate wardrobe",
            result.positive_prompt
        )

    def test_interiors_are_not_forced_into_urban_environment(self):
        director = VisualDirector()

        result = director.direct(
            VisualDirectionContext(
                scene_text="Una persona espera en una habitacion silenciosa.",
                visual_idea="A person sitting inside a calm interior room",
                duration=4.0,
                scene_index=1,
                scene_count=1,
                orientation="horizontal"
            )
        )

        self.assertEqual(
            "interior environment",
            result.directives["environment"]
        )

    def test_human_context_enriches_identity_without_fixed_cases(self):
        director = VisualDirector()

        contexts = (
            (
                "Una persona avanza por la montana al amanecer.",
                "A person walking on a mountain trail"
            ),
            (
                "Una persona toma una decision en una oficina.",
                "A person standing near an office window"
            ),
            (
                "Una mujer camina por la ciudad al atardecer.",
                "A woman walking through a quiet city street"
            )
        )

        for scene_text, visual_idea in contexts:
            with self.subTest(
                visual_idea=visual_idea
            ):
                result = director.direct(
                    VisualDirectionContext(
                        scene_text=scene_text,
                        visual_idea=visual_idea,
                        duration=4.0,
                        scene_index=1,
                        scene_count=1,
                        orientation="horizontal"
                    )
                )

                self.assertIn(
                    "human art direction",
                    result.positive_prompt
                )
                self.assertIn(
                    "identity, interaction and styling shaped by setting",
                    result.positive_prompt
                )
                self.assertIn(
                    visual_idea,
                    result.positive_prompt
                )

    def test_human_art_direction_prioritizes_person_over_clothing(self):
        director = VisualDirector()

        result = director.direct(
            VisualDirectionContext(
                scene_text="Una persona mira a otra antes de responder.",
                visual_idea="Two people having a quiet conversation",
                duration=4.0,
                scene_index=1,
                scene_count=1,
                orientation="horizontal"
            )
        )

        human_direction = result.directives[
            "human_art_direction"
        ]

        self.assertLess(
            human_direction.count(
                "wardrobe"
            ),
            2
        )
        self.assertIn(
            "credible human presence",
            human_direction
        )
        self.assertIn(
            "subtle facial expression",
            human_direction
        )
        self.assertIn(
            "coherent gaze",
            human_direction
        )
        self.assertIn(
            "professional cinematography",
            result.positive_prompt
        )

    def test_non_human_scene_does_not_force_wardrobe(self):
        director = VisualDirector()

        result = director.direct(
            VisualDirectionContext(
                scene_text="La luz cruza un paisaje abstracto.",
                visual_idea="A symbolic beam of light over a quiet valley",
                duration=4.0,
                scene_index=1,
                scene_count=1,
                orientation="horizontal"
            )
        )

        self.assertEqual(
            "",
            result.directives["human_art_direction"]
        )
        self.assertEqual(
            "",
            result.directives["human_context_direction"]
        )

    def test_uses_vertical_orientation_guidance(self):
        director = VisualDirector()

        result = director.direct(
            VisualDirectionContext(
                scene_text="Una figura avanza con calma.",
                visual_idea="A figure walking through morning mist",
                duration=5.0,
                scene_index=1,
                scene_count=1,
                orientation="vertical"
            )
        )

        self.assertIn(
            "vertical 9:16",
            result.positive_prompt
        )
        self.assertIn(
            "subject safely centered",
            result.positive_prompt
        )

    def test_varies_repeated_directives_against_previous_scene(self):
        director = VisualDirector()
        first = director.direct(
            VisualDirectionContext(
                scene_text="La conciencia despierta.",
                visual_idea="A symbolic light appearing in darkness",
                duration=4.0,
                scene_index=1,
                scene_count=2,
                orientation="horizontal"
            )
        )

        second = director.direct(
            VisualDirectionContext(
                scene_text="La conciencia se expande.",
                visual_idea="A symbolic light expanding in darkness",
                duration=4.0,
                scene_index=1,
                scene_count=2,
                orientation="horizontal",
                previous_directives=first.directives
            )
        )

        self.assertNotEqual(
            first.directives["composition"],
            second.directives["composition"]
        )
        self.assertNotEqual(
            first.directives["camera"],
            second.directives["camera"]
        )

    def test_rejects_empty_visual_idea(self):
        director = VisualDirector()

        with self.assertRaises(ValueError):
            director.direct(
                VisualDirectionContext(
                    scene_text="Escena sin imagen.",
                    visual_idea="",
                    duration=4.0,
                    scene_index=1,
                    scene_count=1,
                    orientation="horizontal"
                )
            )


if __name__ == "__main__":
    unittest.main()
