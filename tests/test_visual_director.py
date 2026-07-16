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
                    "Una luz aparece en el cielo "
                    "mientras cambia el paisaje."
                ),
                visual_idea=(
                    "A mountain under a cosmic sky"
                ),
                duration=4.0,
                scene_index=1,
                scene_count=3,
                orientation="horizontal"
            )
        )

        self.assertIn(
            "A mountain under a cosmic sky",
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
            "no distorted forms",
            result.negative_prompt
        )

    def test_keeps_general_visual_direction_only(self):
        director = VisualDirector()

        result = director.direct(
            VisualDirectionContext(
                scene_text="Una silueta avanza en silencio.",
                visual_idea="A figure moving through a quiet station",
                duration=3.0,
                scene_index=1,
                scene_count=1,
                orientation="horizontal"
            )
        )

        self.assertIn(
            "professional art direction",
            result.positive_prompt
        )
        self.assertIn(
            "atmospheric depth",
            result.positive_prompt
        )
        self.assertTrue(
            result.final_prompt
        )

    def test_uses_vertical_orientation_guidance(self):
        director = VisualDirector()

        result = director.direct(
            VisualDirectionContext(
                scene_text="Una figura avanza con calma.",
                visual_idea="A figure moving through morning mist",
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
            "main form kept inside frame",
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
