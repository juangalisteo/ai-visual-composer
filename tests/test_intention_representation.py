import inspect
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from app.domain import Intention, IntentionLevel
from app.intentions import (
    EffectiveIntention,
    IntentionDocument,
    IntentionLoader,
    IntentionRegistry,
)


WORK_YAML = """
schema_version: 1
id: work
version: "1.0.0"
type: work
title: Work Intention
extends: null
metadata:
  owner: Test
  status: draft
  source: manual
  description: Work intention.
trace:
  source_document: test.txt
intention:
  communicative:
    understanding: global understanding
    key_message: global message
    emphasis:
      - relation
  emotional:
    desired_effect: contemplative clarity
    emotional_quality: calm attention
  narrative:
    purpose: global purpose
  negative:
    avoid_interpretations:
      - decorative mysticism
"""


SEQUENCE_YAML = """
schema_version: 1
id: sequence
version: "1.0.0"
type: sequence
title: Sequence Intention
extends: work
metadata:
  owner: Test
  status: draft
  source: manual
  description: Sequence intention.
trace:
  source_sequence: intro
  relationship_to_parent: specialization
  justification: narrows the work intention
intention:
  communicative:
    understanding: sequence understanding
  cognitive:
    question: why does the object matter
"""


SCENE_YAML = """
schema_version: 1
id: scene
version: "1.0.0"
type: scene
title: Scene Intention
extends:
  id: sequence
  version: "1.x"
metadata:
  owner: Test
  status: draft
  source: manual
  description: Scene intention.
trace:
  source_scene: key_transfer
  relationship_to_parent: specialization
  justification: concretizes responsibility
intention:
  communicative:
    understanding: receiving the key implies accepting responsibility
  emotional:
    desired_effect: contained solemnity
  symbolic:
    meaning: the key acts as threshold and burden
    allowed_readings:
      - access
      - responsibility
  transformative:
    before: physical exchange
    after: point of no return
    shift: object transfer becomes consequence
  attentional:
    focus: the act of accepting
  negative:
    avoid_interpretations:
      - casual handoff
      - romantic gesture
"""


BEAT_YAML = """
schema_version: 1
id: beat
version: "1.0.0"
type: beat
title: Beat Intention
extends: scene
metadata:
  owner: Test
  status: draft
  source: manual
  description: Beat intention.
trace:
  source_beat: acceptance
  relationship_to_parent: contrast
  justification: hesitation enriches acceptance without breaking responsibility
intention:
  emotional:
    desired_effect: brief hesitation
  transformative:
    before: offered responsibility
    after: accepted responsibility
"""


class IntentionRepresentationTest(unittest.TestCase):

    def _write(
        self,
        directory: Path,
        name: str,
        content: str
    ) -> Path:
        path = directory / name
        path.parent.mkdir(
            parents=True,
            exist_ok=True
        )
        path.write_text(
            textwrap.dedent(
                content
            ).strip()
            + "\n",
            encoding="utf-8"
        )
        return path

    def _write_chain(
        self,
        directory: Path
    ) -> None:
        self._write(
            directory,
            "work.yaml",
            WORK_YAML
        )
        self._write(
            directory,
            "sequences/sequence.yaml",
            SEQUENCE_YAML
        )
        self._write(
            directory,
            "scenes/scene.yaml",
            SCENE_YAML
        )
        self._write(
            directory,
            "beats/beat.yaml",
            BEAT_YAML
        )

    def test_loads_valid_yaml_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                Path(
                    tmp
                ),
                "work.yaml",
                WORK_YAML
            )

            document = IntentionLoader().load_file(
                path
            )

            self.assertIsInstance(
                document,
                IntentionDocument
            )
            self.assertEqual(
                document.id,
                "work"
            )

    def test_rejects_empty_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                Path(
                    tmp
                ),
                "empty.yaml",
                ""
            )

            with self.assertRaises(
                ValueError
            ):
                IntentionLoader().load_file(
                    path
                )

    def test_rejects_non_mapping_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                Path(
                    tmp
                ),
                "list.yaml",
                """
                - item
                """
            )

            with self.assertRaises(
                ValueError
            ):
                IntentionLoader().load_file(
                    path
                )

    def test_rejects_unsupported_schema_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                Path(
                    tmp
                ),
                "work.yaml",
                WORK_YAML.replace(
                    "schema_version: 1",
                    "schema_version: 99"
                )
            )

            with self.assertRaises(
                ValueError
            ):
                IntentionLoader().load_file(
                    path
                )

    def test_rejects_unknown_top_level_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                Path(
                    tmp
                ),
                "work.yaml",
                WORK_YAML + "\nextra: value\n"
            )

            with self.assertRaises(
                ValueError
            ):
                IntentionLoader().load_file(
                    path
                )

    def test_rejects_unknown_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                Path(
                    tmp
                ),
                "work.yaml",
                WORK_YAML.replace(
                    "communicative:",
                    "aesthetic:"
                )
            )

            with self.assertRaises(
                ValueError
            ):
                IntentionLoader().load_file(
                    path
                )

    def test_rejects_unknown_dimension_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                Path(
                    tmp
                ),
                "work.yaml",
                WORK_YAML.replace(
                    "understanding: global understanding",
                    "unknown: value"
                )
            )
            document = IntentionLoader().load_file(
                path
            )

            with self.assertRaises(
                ValueError
            ):
                IntentionRegistry(
                    (
                        document,
                    )
                ).resolve(
                    "work"
                )

    def test_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(
                tmp
            )
            self._write(
                base,
                "a.yaml",
                WORK_YAML
            )
            self._write(
                base,
                "nested/b.yaml",
                WORK_YAML
            )

            with self.assertRaises(
                ValueError
            ):
                IntentionRegistry.from_directory(
                    tmp
                )

    def test_detects_missing_extends_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                Path(
                    tmp
                ),
                "sequence.yaml",
                SEQUENCE_YAML
            )
            registry = IntentionRegistry(
                (
                    IntentionLoader().load_file(
                        path
                    ),
                )
            )

            with self.assertRaises(
                ValueError
            ):
                registry.resolve(
                    "sequence"
                )

    def test_detects_extends_cycles(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(
                tmp
            )
            self._write(
                base,
                "a.yaml",
                WORK_YAML.replace(
                    "id: work",
                    "id: a"
                ).replace(
                    "extends: null",
                    "extends: b"
                )
            )
            self._write(
                base,
                "b.yaml",
                WORK_YAML.replace(
                    "id: work",
                    "id: b"
                ).replace(
                    "extends: null",
                    "extends: a"
                )
            )

            with self.assertRaises(
                ValueError
            ):
                IntentionRegistry.from_directory(
                    tmp
                ).resolve(
                    "a"
                )

    def test_detects_invalid_hierarchy(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(
                tmp
            )
            self._write(
                base,
                "work.yaml",
                WORK_YAML
            )
            invalid = BEAT_YAML.replace(
                "extends: scene",
                "extends: work"
            )
            self._write(
                base,
                "beat.yaml",
                invalid
            )

            with self.assertRaises(
                ValueError
            ):
                IntentionRegistry.from_directory(
                    tmp
                ).resolve(
                    "beat"
                )

    def test_resolves_work_sequence_scene_beat_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_chain(
                Path(
                    tmp
                )
            )

            effective = IntentionRegistry.from_directory(
                tmp
            ).resolve(
                "beat"
            )

            self.assertEqual(
                effective.inheritance_chain,
                (
                    "work",
                    "sequence",
                    "scene",
                    "beat",
                )
            )
            self.assertIs(
                effective.level,
                IntentionLevel.BEAT
            )

    def test_specializes_dimensions_and_preserves_upper_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_chain(
                Path(
                    tmp
                )
            )

            effective = IntentionRegistry.from_directory(
                tmp
            ).resolve(
                "beat"
            )

            self.assertEqual(
                effective.intention.communicative.understanding,
                "receiving the key implies accepting responsibility"
            )
            self.assertEqual(
                effective.intention.narrative.purpose,
                "global purpose"
            )
            self.assertEqual(
                effective.intention.cognitive.question,
                "why does the object matter"
            )
            self.assertEqual(
                effective.intention.emotional.desired_effect,
                "brief hesitation"
            )

    def test_negative_intention_and_active_exclusions_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_chain(
                Path(
                    tmp
                )
            )

            effective = IntentionRegistry.from_directory(
                tmp
            ).resolve(
                "beat"
            )

            self.assertEqual(
                effective.trace.active_exclusions,
                (
                    "decorative mysticism",
                    "casual handoff",
                    "romantic gesture",
                )
            )

    def test_destructive_contradiction_is_marked_as_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(
                tmp
            )
            self._write(
                base,
                "work.yaml",
                WORK_YAML
            )
            conflict = SEQUENCE_YAML.replace(
                "relationship_to_parent: specialization",
                "relationship_to_parent: destructive_contradiction"
            )
            self._write(
                base,
                "sequence.yaml",
                conflict
            )

            effective = IntentionRegistry.from_directory(
                tmp
            ).resolve(
                "sequence"
            )

            self.assertEqual(
                effective.conflicts[0].conflict_type,
                "destructive_contradiction"
            )

    def test_contrast_with_justification_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_chain(
                Path(
                    tmp
                )
            )

            effective = IntentionRegistry.from_directory(
                tmp
            ).resolve(
                "beat"
            )

            self.assertEqual(
                effective.conflicts,
                ()
            )

    def test_unjustified_contrast_is_marked_for_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(
                tmp
            )
            self._write_chain(
                base
            )
            target = base / "beats" / "beat.yaml"
            target.write_text(
                target.read_text(
                    encoding="utf-8"
                ).replace(
                    "  justification: hesitation enriches acceptance without breaking responsibility\n",
                    ""
                ),
                encoding="utf-8"
            )

            effective = IntentionRegistry.from_directory(
                tmp
            ).resolve(
                "beat"
            )

            self.assertEqual(
                effective.conflicts[0].conflict_type,
                "unjustified_deviation"
            )

    def test_constructs_domain_and_effective_intention(self):
        effective = IntentionRegistry.from_directory(
            "data/intentions"
        ).resolve(
            "modo_conciencia.intention.beat.scene_001_acceptance"
        )

        self.assertIsInstance(
            effective.intention,
            Intention
        )
        self.assertIsInstance(
            effective,
            EffectiveIntention
        )

    def test_trace_contains_field_origins_and_references(self):
        effective = IntentionRegistry.from_directory(
            "data/intentions"
        ).resolve(
            "modo_conciencia.intention.beat.scene_001_acceptance"
        )

        self.assertEqual(
            effective.trace.references,
            (
                "modo_conciencia.intention.work",
                "modo_conciencia.intention.sequence.correspondencia_intro",
                "modo_conciencia.intention.scene.scene_001_key_transfer",
            )
        )
        self.assertTrue(
            effective.trace.field_origins
        )

    def test_fingerprint_is_stable_for_identical_effective_content(self):
        first = IntentionRegistry.from_directory(
            "data/intentions"
        ).resolve(
            "modo_conciencia.intention.beat.scene_001_acceptance"
        )
        second = IntentionRegistry.from_directory(
            "data/intentions"
        ).resolve(
            "modo_conciencia.intention.beat.scene_001_acceptance"
        )

        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_fingerprint_changes_when_effective_content_changes(self):
        original = IntentionRegistry.from_directory(
            "data/intentions"
        ).resolve(
            "modo_conciencia.intention.beat.scene_001_acceptance"
        )

        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(
                "data/intentions",
                Path(
                    tmp
                )
                / "intentions"
            )
            target = (
                Path(
                    tmp
                )
                / "intentions"
                / "modo_conciencia"
                / "beats"
                / "scene_001_acceptance.yaml"
            )
            target.write_text(
                target.read_text(
                    encoding="utf-8"
                ).replace(
                    "brief hesitation",
                    "silent hesitation"
                ),
                encoding="utf-8"
            )
            changed = IntentionRegistry.from_directory(
                Path(
                    tmp
                )
                / "intentions"
            ).resolve(
                "modo_conciencia.intention.beat.scene_001_acceptance"
            )

            self.assertNotEqual(
                original.fingerprint,
                changed.fingerprint
            )

    def test_fingerprint_is_independent_of_local_path(self):
        first = IntentionRegistry.from_directory(
            "data/intentions"
        ).resolve(
            "modo_conciencia.intention.beat.scene_001_acceptance"
        )

        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(
                "data/intentions",
                Path(
                    tmp
                )
                / "copy"
            )
            copied = IntentionRegistry.from_directory(
                Path(
                    tmp
                )
                / "copy"
            ).resolve(
                "modo_conciencia.intention.beat.scene_001_acceptance"
            )

            self.assertEqual(
                first.fingerprint,
                copied.fingerprint
            )

    def test_runtime_modules_do_not_import_intention_representation(self):
        source = ""
        for directory in (
            "app/modules",
            "app/managers",
            "app/controllers",
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
            "app.intentions",
            source
        )
        self.assertNotIn(
            "IntentionRegistry",
            source
        )

    def test_representation_has_no_visual_runtime_or_execution_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.intentions",
                fromlist=[
                    "x"
                ]
            )
        )
        forbidden = (
            "ImageBuilder",
            "VisualDirector",
            "ImagePromptSystem",
            "ComfyUIBackend",
            "ImageManifestWriter",
            "positive_prompt",
            "negative_prompt",
            "payload",
            "workflow",
            "manifest",
            "requests",
            "urllib",
        )

        for item in forbidden:
            with self.subTest(
                item=item
            ):
                self.assertNotIn(
                    item,
                    source
                )


if __name__ == "__main__":
    unittest.main()
