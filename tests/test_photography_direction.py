import inspect
import unittest
from dataclasses import FrozenInstanceError, is_dataclass
from pathlib import Path

from app.domain import (
    EffectiveVisualBrief,
    CompositionPlan,
    MotionSense,
    PhotographyPlan,
    StagingPlan,
)
from app.photography_direction import (
    PhotographyDecisionTrace,
    PhotographyDirection,
    PhotographyDirectionTrace,
    PhotographyDirector,
)


def effective_brief():
    return EffectiveVisualBrief(
            visible_content="A person receives an old key.",
            felt_experience="contained solemnity",
            narrative_composition="threshold event",
            visual_priority="consequence over object",
            primary_subject="person",
            attention_focus="the act of accepting",
            dominant_visual_intention="initiate a new responsibility",
            visual_reading="the key acts as threshold and burden",
            scene_rhythm="slow | restrained",
            symbolic_weight="access | responsibility",
            visual_bible_coherence="contemplative symbolic realism",
            staging=StagingPlan(
                main_subject="receiver",
                environment="quiet interior",
                spatial_relationship="subject held close to the object",
                human_presence="restrained human presence"
            ),
            photography=PhotographyPlan(
                point_of_view="observational",
                emotional_distance="respectful distance",
                depth="layered but calm",
                photographic_atmosphere="quiet photographic realism",
                photographic_realism="grounded"
            ),
            composition=CompositionPlan(
                visual_hierarchy="gesture first",
                framing="balanced close frame",
                negative_space="controlled surrounding silence",
                frame_scale="human scale",
                figure_ground_relationship="clear separation"
            ),
            motion=MotionSense(
                latent_energy="contained",
                rhythm="slow",
                stillness="held pause",
                direction="inward"
            ),
        fingerprint="visual-brief-fingerprint",
    )


class PhotographyDirectionTest(unittest.TestCase):

    def test_photography_direction_models_are_passive_dataclasses(self):
        for model in (
            PhotographyDecisionTrace,
            PhotographyDirectionTrace,
            PhotographyDirection,
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

    def test_photography_direction_is_immutable(self):
        direction = PhotographyDirector().resolve(
            effective_brief()
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            direction.point_of_view = "changed"

    def test_resolves_photography_direction_from_effective_brief(self):
        direction = PhotographyDirector().resolve(
            effective_brief()
        )

        self.assertEqual(
            direction.dominant_photographic_language,
            "quiet photographic realism | grounded | contemplative symbolic realism"
        )
        self.assertEqual(
            direction.emotional_camera_distance,
            "respectful distance | contained solemnity"
        )
        self.assertEqual(
            direction.narrative_scale,
            "human scale | threshold event | consequence over object"
        )
        self.assertEqual(
            direction.point_of_view,
            "observational | the act of accepting"
        )
        self.assertEqual(
            direction.predominant_framing,
            "balanced close frame | gesture first | consequence over object"
        )

    def test_resolution_is_deterministic(self):
        effective = effective_brief()

        first = PhotographyDirector().resolve(
            effective
        )
        second = PhotographyDirector().resolve(
            effective
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_fingerprint_changes_when_effective_brief_changes(self):
        first = PhotographyDirector().resolve(
            effective_brief()
        )
        changed = EffectiveVisualBrief(
                visible_content="A different resolved scene.",
                felt_experience="quiet dread",
            fingerprint="changed-brief",
        )
        second = PhotographyDirector().resolve(
            changed
        )

        self.assertNotEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_trace_records_origin_transformation_and_justification(self):
        direction = PhotographyDirector().resolve(
            effective_brief()
        )
        decisions = {
            decision.field: decision
            for decision in direction.trace.decisions
        }

        self.assertEqual(
            direction.trace.source_effective_brief_fingerprint,
            "visual-brief-fingerprint"
        )
        self.assertEqual(
            decisions["point_of_view"].source_fields,
            (
                "EffectiveVisualBrief.photography.point_of_view",
                "EffectiveVisualBrief.attention_focus",
            )
        )
        self.assertEqual(
            decisions["point_of_view"].transformation,
            "select_and_combine_resolved_effective_brief_fields"
        )
        self.assertIn(
            "camera stance",
            decisions["point_of_view"].justification
        )

    def test_empty_input_does_not_invent_photography_direction(self):
        direction = PhotographyDirector().resolve(
            EffectiveVisualBrief(visible_content="", fingerprint="empty")
        )

        self.assertEqual(
            direction.dominant_photographic_language,
            ""
        )
        self.assertEqual(
            direction.trace.decisions,
            ()
        )

    def test_photography_direction_contains_no_technical_camera_or_prompt_fields(self):
        field_names = set(
            PhotographyDirection.__dataclass_fields__
        )
        forbidden = {
            "camera",
            "lens",
            "focal",
            "aperture",
            "iso",
            "shutter",
            "prompt",
            "payload",
            "workflow",
            "backend",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                {
                    field.lower()
                    for field in field_names
                }
            )
        )

    def test_photography_direction_has_no_runtime_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.photography_direction",
                fromlist=[
                    "x"
                ]
            )
        )
        forbidden = (
            "VisualBible",
            "NarrativeReading",
            "Intention",
            "PromptTranslator",
            "BackendPrompt",
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
            "ComfyUI",
            "Flux",
        )

        for item in forbidden:
            with self.subTest(
                item=item
            ):
                self.assertNotIn(
                    item,
                    source
                )

    def test_runtime_does_not_import_photography_direction(self):
        source = ""
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
                source += path.read_text(
                    encoding="utf-8"
                )

        self.assertNotIn(
            "app.photography_direction",
            source
        )


if __name__ == "__main__":
    unittest.main()
