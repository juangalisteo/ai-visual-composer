import unittest

from app.modules.storyboard.storyboard_response_parser import (
    StoryboardResponseParser,
)


class StoryboardResponseParserTest(unittest.TestCase):

    def test_accepts_one_json_array_with_a_safe_prefix(self):
        self.assertEqual(
            [{"scene": 1}],
            StoryboardResponseParser().parse(
                "Respuesta JSON:\n[{\"scene\": 1}]"
            ),
        )

    def test_accepts_a_valid_multi_scene_json_array(self):
        self.assertEqual(
            [{"scene": 1}, {"scene": 2}],
            StoryboardResponseParser().parse(
                "[{\"scene\": 1}, {\"scene\": 2}]"
            ),
        )

    def test_rejects_extra_json_data_after_the_storyboard(self):
        with self.assertRaisesRegex(ValueError, "datos adicionales"):
            StoryboardResponseParser().parse(
                "[{\"scene\": 1}] [{\"scene\": 2}]"
            )


if __name__ == "__main__":
    unittest.main()
