import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from app.evidence import ImageEvidenceWriter
from app.modules.images.image_builder import ImageBuilder
from app.modules.images.prompt_system import ImagePromptSystem
from app.prompt_translation import (
    OperationalPromptBudgetExceededError,
    PromptBudgetPolicy,
    build_operational_prompt_observation,
)


F2_CORPUS = {
    "human": "A scientist studies a constellation in a quiet observatory",
    "object": "An ancient artifact rests on a stone altar",
    "architecture": "A cathedral interior opens into morning light",
    "scientific": "A neuron glows in a laboratory",
    "abstract": "An abstract energy wave crosses a dark field",
    "geometry": "A geometric mandala forms in darkness",
    "environment": "A misty mountain landscape at dawn",
}


class RecordingBackend:

    def __init__(
        self,
    ):
        self.calls = []

    def generate(
        self,
        **kwargs,
    ):
        self.calls.append(kwargs)
        return Path("generated.png")


class OperationalPromptObservationTest(unittest.TestCase):

    def test_deterministic_corpus_has_stable_atomic_composition(self):
        prompt_system = ImagePromptSystem()

        for category, compiled_prompt in F2_CORPUS.items():
            with self.subTest(
                category=category,
            ):
                first = prompt_system.compose_cinematic_backend_prompt_with_parts(
                    compiled_prompt
                )
                second = prompt_system.compose_cinematic_backend_prompt_with_parts(
                    compiled_prompt
                )

                self.assertEqual(first, second)
                self.assertEqual(
                    compiled_prompt,
                    first.parts[0][1],
                )
                self.assertEqual(
                    len(first.rules),
                    len(
                        {
                            rule.id
                            for rule in first.rules
                        }
                    ),
                )
                self.assertEqual(
                    1,
                    sum(
                        rule.id == "safety.no_text"
                        for rule in first.rules
                    ),
                )

    def test_optimised_corpus_preserves_invariants_and_enters_encoder_budget(self):
        prompt_system = ImagePromptSystem()
        policy = PromptBudgetPolicy()

        for category, compiled_prompt in F2_CORPUS.items():
            with self.subTest(
                category=category,
            ):
                composition = (
                    prompt_system.compose_cinematic_backend_prompt_with_parts(
                        compiled_prompt
                    )
                )
                observation = build_operational_prompt_observation(
                    compiled_prompt=compiled_prompt,
                    operational_prompt=composition.prompt,
                    budget_policy=policy,
                    composition_parts=composition.parts,
                )
                rule_ids = {
                    rule.id
                    for rule in composition.rules
                }

                self.assertLessEqual(
                    observation.operational_prompt.token_count,
                    policy.encoder_token_limit,
                )
                self.assertIn("identity.base_visual", rule_ids)
                self.assertIn("identity.cinematic", rule_ids)
                self.assertIn("safety.no_text", rule_ids)
                self.assertIn(
                    "No text, logos, watermarks, or readable writing",
                    composition.prompt,
                )

                if category == "human":
                    self.assertIn("casting.human.subject", rule_ids)
                    self.assertIn("casting.human.anatomy", rule_ids)
                    self.assertIn("safety.human.wardrobe", rule_ids)
                    self.assertNotIn(
                        "casting.non_human.no_extra_people",
                        rule_ids,
                    )
                else:
                    self.assertIn(
                        "casting.non_human.no_extra_people",
                        rule_ids,
                    )
                    self.assertNotIn("casting.human.subject", rule_ids)
                    self.assertNotIn("safety.human.wardrobe", rule_ids)

    def test_compiled_hard_limit_can_still_fit_with_protected_identity(self):
        prompt_system = ImagePromptSystem()
        policy = PromptBudgetPolicy()
        cases = (
            "person " + ("x" * 1529),
            "artifact " + ("x" * 1527),
        )

        for compiled_prompt in cases:
            with self.subTest(
                compiled_prompt_kind=(
                    "human"
                    if compiled_prompt.startswith("person")
                    else "nonhuman"
                ),
            ):
                composition = (
                    prompt_system.compose_cinematic_backend_prompt_with_parts(
                        compiled_prompt
                    )
                )
                observation = build_operational_prompt_observation(
                    compiled_prompt=compiled_prompt,
                    operational_prompt=composition.prompt,
                    budget_policy=policy,
                    composition_parts=composition.parts,
                )

                self.assertEqual(
                    policy.hard_prompt_tokens,
                    observation.compiled_prompt.token_count,
                )
                self.assertLessEqual(
                    observation.operational_prompt.token_count,
                    policy.encoder_token_limit,
                )

    def test_under_limit_prompt_is_sent_unchanged(self):
        prompt_system = ImagePromptSystem()
        compiled_prompt = F2_CORPUS["human"]
        composition = prompt_system.compose_cinematic_backend_prompt_with_parts(
            compiled_prompt
        )
        observation = build_operational_prompt_observation(
            compiled_prompt=compiled_prompt,
            operational_prompt=composition.prompt,
            budget_policy=PromptBudgetPolicy(),
            composition_parts=composition.parts,
        )
        backend = RecordingBackend()
        builder = ImageBuilder(backend=backend)

        result = builder._generate_validated_image(
            prompt=composition.prompt,
            scene_number=1,
            output_dir=Path("images"),
            width=640,
            height=360,
            operational_prompt_observation=observation,
        )

        self.assertEqual(Path("generated.png"), result)
        self.assertEqual(composition.prompt, backend.calls[0]["prompt"])

    def test_operational_overflow_blocks_backend_after_compiled_prompt_passes(self):
        compiled_prompt = "brief compiled direction"
        operational_prompt = "detail " * 513
        observation = build_operational_prompt_observation(
            compiled_prompt=compiled_prompt,
            operational_prompt=operational_prompt,
            budget_policy=PromptBudgetPolicy(
                encoder_token_limit=512,
                hard_prompt_tokens=384,
            ),
            composition_parts=(
                ("casting.human.subject", operational_prompt),
            ),
        )
        backend = RecordingBackend()

        with self.assertRaises(
            OperationalPromptBudgetExceededError
        ) as raised:
            ImageBuilder(backend=backend)._generate_validated_image(
                prompt=operational_prompt,
                scene_number=1,
                output_dir=Path("images"),
                width=640,
                height=360,
                operational_prompt_observation=observation,
            )

        error = raised.exception
        self.assertLessEqual(
            error.compiled_prompt_tokens,
            error.compiled_hard_limit,
        )
        self.assertGreater(
            error.final_prompt_tokens,
            error.encoder_token_limit,
        )
        self.assertEqual(0, len(backend.calls))
        self.assertIn("casting.human.subject", error.dominant_categories)
        self.assertIn("No se enviará a ComfyUI", str(error))

    def test_human_and_nonhuman_rules_are_conditionally_exclusive(self):
        prompt_system = ImagePromptSystem()
        human_ids = {
            rule.id
            for rule in prompt_system.operational_rules_for_prompt(
                F2_CORPUS["human"]
            )
        }
        nonhuman_ids = {
            rule.id
            for rule in prompt_system.operational_rules_for_prompt(
                F2_CORPUS["object"]
            )
        }

        self.assertTrue(
            {
                "casting.human.subject",
                "casting.human.anatomy",
                "safety.human.wardrobe",
            }.issubset(human_ids)
        )
        self.assertIn(
            "casting.non_human.no_extra_people",
            nonhuman_ids,
        )
        self.assertIn(
            "direction.non_human.symbolic_object",
            nonhuman_ids,
        )
        self.assertFalse(
            human_ids & {
                "casting.non_human.no_extra_people",
                "direction.non_human.symbolic_object",
            }
        )
        self.assertFalse(
            nonhuman_ids & {
                "casting.human.subject",
                "casting.human.anatomy",
                "safety.human.wardrobe",
            }
        )

    def test_metrics_and_fingerprint_describe_the_real_operational_prompt(self):
        compiled_prompt = "alpha beta\ngamma"
        operational_prompt = "alpha beta\ngamma, cinematic operational direction"
        observation = build_operational_prompt_observation(
            compiled_prompt=compiled_prompt,
            operational_prompt=operational_prompt,
            budget_policy=PromptBudgetPolicy(),
            composition_parts=(
                (
                    "identity.cinematic",
                    "cinematic operational direction",
                ),
            ),
        )

        metrics = observation.operational_prompt
        self.assertEqual(len(operational_prompt), metrics.char_count)
        self.assertEqual(len(operational_prompt.split()), metrics.word_count)
        self.assertEqual(2, metrics.line_count)
        self.assertEqual(
            max(
                len(operational_prompt.split()),
                len(operational_prompt) // 4,
            ),
            metrics.token_count,
        )
        self.assertEqual(
            hashlib.sha256(
                operational_prompt.encode("utf-8")
            ).hexdigest(),
            metrics.fingerprint,
        )
        self.assertEqual(
            metrics.token_count - observation.compiled_prompt.token_count,
            observation.operational_expansion.token_count,
        )

    def test_overflow_does_not_truncate_or_write_prompt_text_to_evidence(self):
        compiled_prompt = "CONFIDENTIAL-COMPILED-CONTENT-993"
        operational_prompt = "CONFIDENTIAL-OPERATIONAL-CONTENT-771 " * 513
        observation = build_operational_prompt_observation(
            compiled_prompt=compiled_prompt,
            operational_prompt=operational_prompt,
            budget_policy=PromptBudgetPolicy(
                encoder_token_limit=512,
            ),
            composition_parts=(
                ("safety.no_text", operational_prompt),
            ),
        )

        with self.assertRaises(
            OperationalPromptBudgetExceededError
        ):
            ImageBuilder(
                backend=RecordingBackend(),
            )._generate_validated_image(
                prompt=operational_prompt,
                scene_number=1,
                output_dir=Path("images"),
                width=640,
                height=360,
                operational_prompt_observation=observation,
            )

        self.assertEqual(
            hashlib.sha256(
                operational_prompt.encode("utf-8")
            ).hexdigest(),
            observation.operational_prompt.fingerprint,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            result = ImageEvidenceWriter().write_operational_prompt_observation(
                output_dir=Path(temp_dir),
                scene_number=1,
                operational_prompt_observation=observation,
            )
            artifact_text = result.artifact_path.read_text(
                encoding="utf-8",
            )
            artifact = json.loads(artifact_text)

        self.assertNotIn(compiled_prompt, artifact_text)
        self.assertNotIn("CONFIDENTIAL-OPERATIONAL-CONTENT-771", artifact_text)
        self.assertEqual(
            observation.operational_prompt.fingerprint,
            artifact["operational_prompt"]["fingerprint"],
        )


if __name__ == "__main__":
    unittest.main()
