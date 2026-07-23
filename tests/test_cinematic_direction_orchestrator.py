import inspect
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.cinematic_direction import (
    CinematicDirectionOrchestrator,
    create_cinematic_direction_set,
)
from app.color_direction import ColorDirection
from app.composition_direction import CompositionDirection
from app.continuity_direction import ContinuityDirection
from app.domain import VisualBrief
from app.lighting_direction import LightingDirection
from app.movement_direction import MovementDirection
from app.photography_direction import PhotographyDirection
from app.visual_direction import (
    EffectiveVisualBrief,
    VisualBriefTrace,
)


def effective_visual_brief():
    return EffectiveVisualBrief(
        visual_brief=VisualBrief(
            visible_content="A person receives an old key."
        ),
        trace=VisualBriefTrace(),
        conflicts=(),
        fingerprint="visual-brief-fingerprint",
        source_id="scene_001",
        source_version="1.0.0",
    )


def direction_fixtures():
    return {
        "photography": PhotographyDirection(
            dominant_photographic_language="observational",
            source_version="photography-v1",
            fingerprint="photography-fingerprint"
        ),
        "lighting": LightingDirection(
            dominant_lighting="motivated soft source",
            source_version="lighting-v1",
            fingerprint="lighting-fingerprint"
        ),
        "composition": CompositionDirection(
            dominant_composition="hands first",
            source_version="composition-v1",
            fingerprint="composition-fingerprint"
        ),
        "color": ColorDirection(
            dominant_palette="muted amber",
            source_version="color-v1",
            fingerprint="color-fingerprint"
        ),
        "movement": MovementDirection(
            dominant_movement="inward movement",
            source_version="movement-v1",
            fingerprint="movement-fingerprint"
        ),
        "continuity": ContinuityDirection(
            visual_continuity="recurring object",
            source_version="continuity-v1",
            fingerprint="continuity-fingerprint"
        ),
    }


def director_for(direction):
    director = Mock()
    director.resolve.return_value = direction
    return director


class CinematicDirectionOrchestratorTest(unittest.TestCase):

    def test_builds_cinematic_direction_set_from_effective_visual_brief(self):
        directions = direction_fixtures()
        orchestrator = CinematicDirectionOrchestrator(
            photography_director=director_for(
                directions["photography"]
            ),
            lighting_director=director_for(
                directions["lighting"]
            ),
            composition_director=director_for(
                directions["composition"]
            ),
            color_director=director_for(
                directions["color"]
            ),
            movement_director=director_for(
                directions["movement"]
            ),
            continuity_director=director_for(
                directions["continuity"]
            ),
        )

        direction_set = orchestrator.resolve(
            effective_visual_brief()
        )

        self.assertIs(
            direction_set.photography,
            directions["photography"]
        )
        self.assertIs(
            direction_set.lighting,
            directions["lighting"]
        )
        self.assertIs(
            direction_set.composition,
            directions["composition"]
        )
        self.assertIs(
            direction_set.color,
            directions["color"]
        )
        self.assertIs(
            direction_set.movement,
            directions["movement"]
        )
        self.assertIs(
            direction_set.continuity,
            directions["continuity"]
        )

    def test_invokes_six_directors_in_deterministic_order(self):
        directions = direction_fixtures()
        calls = []

        def ordered_director(
            name,
            direction
        ):
            director = Mock()

            def resolve(_effective):
                calls.append(
                    name
                )
                return direction

            director.resolve.side_effect = resolve
            return director

        orchestrator = CinematicDirectionOrchestrator(
            photography_director=ordered_director(
                "photography",
                directions["photography"]
            ),
            lighting_director=ordered_director(
                "lighting",
                directions["lighting"]
            ),
            composition_director=ordered_director(
                "composition",
                directions["composition"]
            ),
            color_director=ordered_director(
                "color",
                directions["color"]
            ),
            movement_director=ordered_director(
                "movement",
                directions["movement"]
            ),
            continuity_director=ordered_director(
                "continuity",
                directions["continuity"]
            ),
        )

        orchestrator.resolve(
            effective_visual_brief()
        )

        self.assertEqual(
            calls,
            [
                "photography",
                "lighting",
                "composition",
                "color",
                "movement",
                "continuity",
            ]
        )

    def test_passes_same_effective_visual_brief_to_every_director(self):
        directions = direction_fixtures()
        effective = effective_visual_brief()
        directors = {
            name: director_for(
                direction
            )
            for name, direction in directions.items()
        }
        orchestrator = CinematicDirectionOrchestrator(
            photography_director=directors["photography"],
            lighting_director=directors["lighting"],
            composition_director=directors["composition"],
            color_director=directors["color"],
            movement_director=directors["movement"],
            continuity_director=directors["continuity"],
        )

        orchestrator.resolve(
            effective
        )

        for director in directors.values():
            director.resolve.assert_called_once_with(
                effective
            )

    def test_reuses_create_cinematic_direction_set(self):
        directions = direction_fixtures()
        expected = create_cinematic_direction_set(
            **directions
        )
        orchestrator = CinematicDirectionOrchestrator(
            photography_director=director_for(
                directions["photography"]
            ),
            lighting_director=director_for(
                directions["lighting"]
            ),
            composition_director=director_for(
                directions["composition"]
            ),
            color_director=director_for(
                directions["color"]
            ),
            movement_director=director_for(
                directions["movement"]
            ),
            continuity_director=director_for(
                directions["continuity"]
            ),
        )

        with patch(
            "app.cinematic_direction.orchestrator.create_cinematic_direction_set",
            return_value=expected
        ) as factory:
            result = orchestrator.resolve(
                effective_visual_brief()
            )

        factory.assert_called_once_with(
            photography=directions["photography"],
            lighting=directions["lighting"],
            composition=directions["composition"],
            color=directions["color"],
            movement=directions["movement"],
            continuity=directions["continuity"],
        )
        self.assertIs(
            result,
            expected
        )

    def test_preserves_fingerprints_and_traces_from_factory(self):
        directions = direction_fixtures()
        direction_set = CinematicDirectionOrchestrator(
            photography_director=director_for(
                directions["photography"]
            ),
            lighting_director=director_for(
                directions["lighting"]
            ),
            composition_director=director_for(
                directions["composition"]
            ),
            color_director=director_for(
                directions["color"]
            ),
            movement_director=director_for(
                directions["movement"]
            ),
            continuity_director=director_for(
                directions["continuity"]
            ),
        ).resolve(
            effective_visual_brief()
        )
        components = {
            component.name: component
            for component in direction_set.trace.components
        }

        self.assertEqual(
            components["photography"].fingerprint,
            "photography-fingerprint"
        )
        self.assertEqual(
            components["continuity"].fingerprint,
            "continuity-fingerprint"
        )
        self.assertTrue(
            direction_set.fingerprint
        )

    def test_resolution_is_deterministic(self):
        directions = direction_fixtures()
        orchestrator = CinematicDirectionOrchestrator(
            photography_director=director_for(
                directions["photography"]
            ),
            lighting_director=director_for(
                directions["lighting"]
            ),
            composition_director=director_for(
                directions["composition"]
            ),
            color_director=director_for(
                directions["color"]
            ),
            movement_director=director_for(
                directions["movement"]
            ),
            continuity_director=director_for(
                directions["continuity"]
            ),
        )

        first = orchestrator.resolve(
            effective_visual_brief()
        )
        second = orchestrator.resolve(
            effective_visual_brief()
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_orchestrator_has_no_backend_runtime_or_prompt_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.cinematic_direction.orchestrator",
                fromlist=[
                    "x"
                ]
            )
        )
        forbidden = (
            "PromptTranslator",
            "BackendPrompt",
            "BackendAdapter",
            "ImageBuilder",
            "ImagePromptSystem",
            "ComfyUIBackend",
            "ImageManifestWriter",
            "payload",
            "workflow",
            "manifest",
            "requests",
            "urllib",
            "FFmpeg",
        )

        for item in forbidden:
            with self.subTest(
                item=item
            ):
                self.assertNotIn(
                    item,
                    source
                )

    def test_runtime_imports_cinematic_direction_only_from_image_builder(self):
        paths_with_import = []
        for directory in (
            "app/modules",
            "app/managers",
            "app/controllers",
            "app/core",
        ):
            for path in Path(
                directory
            ).rglob(
                "*.py"
            ):
                source = path.read_text(
                    encoding="utf-8"
                )
                if (
                    "app.cinematic_direction" in source
                    or "CinematicDirectionOrchestrator" in source
                ):
                    paths_with_import.append(
                        path.as_posix()
                    )

        self.assertEqual(
            [
                "app/modules/images/image_builder.py",
            ],
            paths_with_import
        )


if __name__ == "__main__":
    unittest.main()
