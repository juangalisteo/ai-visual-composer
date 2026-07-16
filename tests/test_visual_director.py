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
            "visual interpretation of the scene meaning",
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
