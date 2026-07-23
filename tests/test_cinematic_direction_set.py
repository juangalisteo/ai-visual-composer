import inspect
import unittest
from dataclasses import FrozenInstanceError, replace, is_dataclass
from pathlib import Path

from app.cinematic_direction import (
    CinematicDirectionComponentTrace,
    CinematicDirectionSet,
    CinematicDirectionSetTrace,
    create_cinematic_direction_set,
)
from app.color_direction import ColorDirection
from app.composition_direction import CompositionDirection
from app.continuity_direction import ContinuityDirection
from app.lighting_direction import LightingDirection
from app.movement_direction import MovementDirection
from app.photography_direction import PhotographyDirection


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


class CinematicDirectionSetTest(unittest.TestCase):

    def test_cinematic_direction_set_models_are_passive_dataclasses(self):
        for model in (
            CinematicDirectionComponentTrace,
            CinematicDirectionSetTrace,
            CinematicDirectionSet,
        ):
            with self.subTest(
                model=model.__name__
            ):
                self.assertTrue(
                    is_dataclass(
                        model
                    )
                )
                self.assertTrue(
                    model.__dataclass_params__.frozen
                )

    def test_cinematic_direction_set_is_immutable(self):
        direction_set = create_cinematic_direction_set(
            **direction_fixtures()
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            direction_set.version = "changed"

    def test_aggregates_all_six_directions_without_reinterpretation(self):
        directions = direction_fixtures()
        direction_set = create_cinematic_direction_set(
            **directions
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

    def test_trace_preserves_component_versions_and_fingerprints(self):
        direction_set = create_cinematic_direction_set(
            **direction_fixtures()
        )
        components = {
            component.name: component
            for component in direction_set.trace.components
        }

        self.assertEqual(
            tuple(
                components
            ),
            (
                "photography",
                "lighting",
                "composition",
                "color",
                "movement",
                "continuity",
            )
        )
        self.assertTrue(
            components["photography"].present
        )
        self.assertEqual(
            components["photography"].version,
            "photography-v1"
        )
        self.assertEqual(
            components["photography"].fingerprint,
            "photography-fingerprint"
        )
        self.assertEqual(
            components["continuity"].version,
            "continuity-v1"
        )
        self.assertEqual(
            components["continuity"].fingerprint,
            "continuity-fingerprint"
        )

    def test_absent_directions_are_explicit_without_creating_empty_directions(self):
        direction_set = create_cinematic_direction_set(
            photography=direction_fixtures()["photography"]
        )
        components = {
            component.name: component
            for component in direction_set.trace.components
        }

        self.assertIsNone(
            direction_set.lighting
        )
        self.assertTrue(
            components["photography"].present
        )
        self.assertFalse(
            components["lighting"].present
        )
        self.assertEqual(
            components["lighting"].version,
            ""
        )
        self.assertEqual(
            components["lighting"].fingerprint,
            ""
        )

    def test_fingerprint_is_deterministic(self):
        directions = direction_fixtures()

        first = create_cinematic_direction_set(
            **directions
        )
        second = create_cinematic_direction_set(
            **directions
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_fingerprint_changes_when_any_direction_fingerprint_changes(self):
        directions = direction_fixtures()
        first = create_cinematic_direction_set(
            **directions
        )
        directions["color"] = replace(
            directions["color"],
            fingerprint="changed-color-fingerprint"
        )
        second = create_cinematic_direction_set(
            **directions
        )

        self.assertNotEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_fingerprint_changes_when_component_presence_changes(self):
        directions = direction_fixtures()
        first = create_cinematic_direction_set(
            **directions
        )
        second = create_cinematic_direction_set(
            photography=directions["photography"]
        )

        self.assertNotEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_cinematic_direction_set_contains_no_backend_runtime_or_prompt_fields(self):
        field_names = set(
            CinematicDirectionSet.__dataclass_fields__
        )
        forbidden = {
            "prompt",
            "payload",
            "workflow",
            "backend",
            "runtime",
            "manifest",
            "path",
            "timestamp",
            "log",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                {
                    field.lower()
                    for field in field_names
                }
            )
        )

    def test_cinematic_direction_set_has_no_runtime_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.cinematic_direction",
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
                if "app.cinematic_direction" in source:
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
