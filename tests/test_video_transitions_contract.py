from pathlib import Path
import json
import unittest
from unittest.mock import patch

from app.modules.video.config.loaders.transition_loader import (
    TransitionConfigLoader
)
from app.modules.video.config.transition_config import TransitionConfig
from app.modules.video.config.transition_contract import (
    SUPPORTED_TRANSITION_TYPES
)
from app.modules.video.transitions.transition_builder import (
    TransitionBuilder
)
from app.modules.video.transitions.transition_selector import (
    TransitionSelector
)


class VideoTransitionsContractTest(
    unittest.TestCase
):

    def _build_transition(
        self,
        transition_type
    ):
        with patch(
            "app.modules.video.transitions.transition_builder"
            ".ProgressLogger.info"
        ):
            return TransitionBuilder().build(
                previous_stream="[v0]",
                current_stream="[v1]",
                transition_type=transition_type,
                duration=0.4,
                offset=1.6,
                output_stream="[tx1]",
                from_scene=1,
                to_scene=2
            )

    def _config(
        self,
        types
    ):
        return TransitionConfig(
            enabled=True,
            duration=0.4,
            selection="sequence",
            avoid_repeats=False,
            types=tuple(types),
            weights={
                transition_type: 1.0
                for transition_type in types
            }
        )

    def test_every_config_transition_is_accepted_by_builder(
        self
    ):
        for transition_type in SUPPORTED_TRANSITION_TYPES:
            with self.subTest(
                transition_type=transition_type
            ):
                config = self._config(
                    [
                        transition_type
                    ]
                )

                transition = self._build_transition(
                    transition_type
                )

                self.assertIn(
                    transition_type,
                    config.types
                )
                self.assertEqual(
                    transition["type"],
                    transition_type
                )
                self.assertIn(
                    f"transition={transition_type}",
                    transition["filter"]
                )

    def test_invalid_transition_fails_in_config_validation(
        self
    ):
        with self.assertRaises(
            ValueError
        ):
            self._config(
                [
                    "not_supported"
                ]
            )

    def test_builder_rejects_invalid_transition_as_defense_in_depth(
        self
    ):
        with self.assertRaises(
            ValueError
        ):
            self._build_transition(
                "not_supported"
            )

    def test_existing_transition_filters_are_unchanged(
        self
    ):
        expected = {
            "fade": (
                "[v0][v1]xfade=transition=fade:"
                "duration=0.400:offset=1.600[tx1]"
            ),
            "smoothleft": (
                "[v0][v1]xfade=transition=smoothleft:"
                "duration=0.400:offset=1.600[tx1]"
            ),
            "fadeblack": (
                "[v0][v1]xfade=transition=fadeblack:"
                "duration=0.400:offset=1.600[tx1]"
            )
        }

        for transition_type, filter_value in expected.items():
            with self.subTest(
                transition_type=transition_type
            ):
                self.assertEqual(
                    self._build_transition(
                        transition_type
                    )["filter"],
                    filter_value
                )

    def test_directional_transitions_are_supported(
        self
    ):
        for transition_type in (
            "smoothright",
            "smoothup",
            "smoothdown"
        ):
            with self.subTest(
                transition_type=transition_type
            ):
                self.assertEqual(
                    self._build_transition(
                        transition_type
                    )["filter"],
                    (
                        f"[v0][v1]xfade=transition={transition_type}:"
                        "duration=0.400:offset=1.600[tx1]"
                    )
                )

    def test_selector_only_returns_supported_values(
        self
    ):
        config = self._config(
            SUPPORTED_TRANSITION_TYPES
        )
        selector = TransitionSelector(
            config
        )

        selected = [
            selector.select(
                scene_index=index,
                scene_count=8
            )
            for index in range(
                1,
                7
            )
        ]

        self.assertEqual(
            selected,
            list(
                SUPPORTED_TRANSITION_TYPES
            )
        )

    def test_loader_rejects_missing_transition_contract(
        self
    ):
        with self.assertRaisesRegex(
            ValueError,
            "video_style.transitions.enabled"
        ):
            TransitionConfigLoader().load(
                {
                    "video_style": {
                        "transitions": {}
                    }
                }
            )

    def test_official_profiles_keep_loading_supported_transitions(
        self
    ):
        profile_paths = (
            Path(
                "config/profiles/video/horizontal/"
                "perfil_video_horizontal.json"
            ),
            Path(
                "config/profiles/video/vertical/"
                "perfil_video_vertical.json"
            )
        )

        for profile_path in profile_paths:
            with self.subTest(
                profile_path=profile_path
            ):
                profile = json.loads(
                    profile_path.read_text(
                        encoding="utf-8-sig"
                    )
                )
                config = TransitionConfigLoader().load(
                    profile
                )

                self.assertTrue(
                    set(
                        config.types
                    ).issubset(
                        set(
                            SUPPORTED_TRANSITION_TYPES
                        )
                    )
                )


if __name__ == "__main__":
    unittest.main()
