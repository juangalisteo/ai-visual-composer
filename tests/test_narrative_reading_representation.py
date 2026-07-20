import inspect
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from app.domain import NarrativeConfidence, NarrativeReading
from app.narrative_readings import (
    EffectiveNarrativeReading,
    NarrativeReadingDocument,
    NarrativeReadingLoader,
    NarrativeReadingRegistry,
)


WORK_YAML = """
schema_version: 1
id: work
version: "1.0.0"
type: work
title: Work
extends: null
metadata:
  owner: Test
  status: draft
  source: manual
  description: Work reading.
trace:
  source_document: test.txt
narrative_reading:
  facts:
    stated:
      - inherited fact that must not reach scene
    confidence: explicit
  context:
    known_context: global context
    continuity: global continuity
    confidence: contextual
  function:
    primary: global function
    secondary:
      - shared frame
    structural_role: global frame
    confidence: contextual
  relations:
    relations:
      - global relation
    confidence: contextual
  conflict:
    tension: global tension
    confidence: contextual
  concepts:
    contextual:
      - global concept
  explicit_symbols:
    symbols:
      - inherited symbol that must not reach scene
    confidence: explicit
  continuity:
    prepares:
      - global preparation
    confidence: contextual
"""


SEQUENCE_YAML = """
schema_version: 1
id: sequence
version: "1.0.0"
type: sequence
title: Sequence
extends: work
metadata:
  owner: Test
  status: draft
  source: manual
  description: Sequence reading.
trace:
  source_sequence: intro
narrative_reading:
  event:
    action: inherited action that must not reach scene
    confidence: explicit
  context:
    known_context: sequence context
    confidence: contextual
  relations:
    relations:
      - sequence relation
    confidence: contextual
  concepts:
    contextual:
      - sequence concept
  continuity:
    prepares:
      - sequence preparation
    confidence: inferred
"""


SCENE_YAML = """
schema_version: 1
id: scene
version: "1.0.0"
type: scene
title: Scene
extends:
  id: sequence
  version: "1.x"
metadata:
  owner: Test
  status: draft
  source: manual
  description: Scene reading.
trace:
  source_text: Una persona encuentra una llave antigua en una casa abandonada.
narrative_reading:
  facts:
    stated:
      - person finds old key
    existing_elements:
      - person
      - old key
    confidence: explicit
  event:
    action: finds
    subject: person
    object: old key
    initial_state: key unknown
    final_state: key discovered
    confidence: explicit
  context:
    known_context: abandoned house
    confidence: contextual
  change:
    changes:
      - old key enters the narrative
    remains:
      - house remains abandoned
    change_type: factual
    affected_entity: person
    confidence: explicit
  function:
    primary: discovery
    secondary:
      - setup
    confidence: contextual
  entities:
    characters:
      - person
    objects:
      - old key
    places:
      - abandoned house
    confidence: explicit
  relations:
    relations:
      - person finds old key
    confidence: explicit
  conflict:
    tension: uncertainty
    confidence: contextual
  concepts:
    explicit:
      - discovery
    contextual:
      - mystery
  explicit_symbols:
    symbols:
      - old key
    confidence: explicit
  continuity:
    prepares:
      - possible later use of the key
    confidence: inferred
"""


class NarrativeReadingRepresentationTest(unittest.TestCase):

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

    def test_loads_valid_yaml_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                Path(
                    tmp
                ),
                "work.yaml",
                WORK_YAML
            )

            document = NarrativeReadingLoader().load_file(
                path
            )

            self.assertIsInstance(
                document,
                NarrativeReadingDocument
            )
            self.assertEqual(
                document.id,
                "work"
            )
            self.assertEqual(
                document.type,
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
                NarrativeReadingLoader().load_file(
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
                NarrativeReadingLoader().load_file(
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
                NarrativeReadingLoader().load_file(
                    path
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
                NarrativeReadingRegistry.from_directory(
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
            registry = NarrativeReadingRegistry(
                (
                    NarrativeReadingLoader().load_file(
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
                NarrativeReadingRegistry.from_directory(
                    tmp
                ).resolve(
                    "a"
                )

    def test_resolves_work_sequence_scene_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_chain(
                Path(
                    tmp
                )
            )

            effective = NarrativeReadingRegistry.from_directory(
                tmp
            ).resolve(
                "scene"
            )

            self.assertEqual(
                effective.inheritance_chain,
                (
                    "work",
                    "sequence",
                    "scene",
                )
            )

    def test_inherits_contextual_information(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_chain(
                Path(
                    tmp
                )
            )

            effective = NarrativeReadingRegistry.from_directory(
                tmp
            ).resolve(
                "scene"
            )

            self.assertEqual(
                effective.narrative_reading.context.known_context,
                "abandoned house"
            )
            self.assertEqual(
                effective.narrative_reading.relations.relations,
                (
                    "global relation",
                    "sequence relation",
                    "person finds old key",
                )
            )
            self.assertEqual(
                effective.narrative_reading.concepts.contextual,
                (
                    "global concept",
                    "sequence concept",
                    "mystery",
                )
            )
            self.assertEqual(
                effective.narrative_reading.continuity.prepares,
                (
                    "global preparation",
                    "sequence preparation",
                    "possible later use of the key",
                )
            )

    def test_does_not_inherit_factual_local_information(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_chain(
                Path(
                    tmp
                )
            )

            effective = NarrativeReadingRegistry.from_directory(
                tmp
            ).resolve(
                "scene"
            )

            self.assertEqual(
                effective.narrative_reading.facts.stated,
                (
                    "person finds old key",
                )
            )
            self.assertEqual(
                effective.narrative_reading.event.action,
                "finds"
            )
            self.assertEqual(
                effective.narrative_reading.explicit_symbols.symbols,
                (
                    "old key",
                )
            )

    def test_preserves_narrative_confidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_chain(
                Path(
                    tmp
                )
            )

            effective = NarrativeReadingRegistry.from_directory(
                tmp
            ).resolve(
                "scene"
            )

            self.assertIs(
                effective.narrative_reading.facts.confidence,
                NarrativeConfidence.EXPLICIT
            )
            self.assertIs(
                effective.narrative_reading.continuity.confidence,
                NarrativeConfidence.INFERRED
            )

    def test_rejects_invalid_confidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                Path(
                    tmp
                ),
                "work.yaml",
                WORK_YAML.replace(
                    "confidence: explicit",
                    "confidence: maybe",
                    1
                )
            )

            with self.assertRaises(
                ValueError
            ):
                NarrativeReadingLoader().load_file(
                    path
                )

    def test_constructs_domain_and_effective_narrative_reading(self):
        effective = NarrativeReadingRegistry.from_directory(
            "data/narrative_readings"
        ).resolve(
            "modo_conciencia.scene.scene_001_key_discovery"
        )

        self.assertIsInstance(
            effective.narrative_reading,
            NarrativeReading
        )
        self.assertIsInstance(
            effective,
            EffectiveNarrativeReading
        )

    def test_trace_contains_references_and_field_origins(self):
        effective = NarrativeReadingRegistry.from_directory(
            "data/narrative_readings"
        ).resolve(
            "modo_conciencia.scene.scene_001_key_discovery"
        )

        self.assertEqual(
            effective.trace.references,
            (
                "modo_conciencia.work",
                "modo_conciencia.sequence.correspondencia_intro",
            )
        )
        self.assertTrue(
            effective.trace.field_origins
        )
        self.assertIn(
            "inherited",
            {
                origin.action
                for origin in effective.trace.field_origins
            }
        )

    def test_fingerprint_is_stable_for_identical_effective_content(self):
        first = NarrativeReadingRegistry.from_directory(
            "data/narrative_readings"
        ).resolve(
            "modo_conciencia.scene.scene_001_key_discovery"
        )
        second = NarrativeReadingRegistry.from_directory(
            "data/narrative_readings"
        ).resolve(
            "modo_conciencia.scene.scene_001_key_discovery"
        )

        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_fingerprint_changes_when_effective_content_changes(self):
        original = NarrativeReadingRegistry.from_directory(
            "data/narrative_readings"
        ).resolve(
            "modo_conciencia.scene.scene_001_key_discovery"
        )

        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(
                "data/narrative_readings",
                Path(
                    tmp
                )
                / "narrative_readings"
            )
            target = (
                Path(
                    tmp
                )
                / "narrative_readings"
                / "modo_conciencia"
                / "scenes"
                / "scene_001_key_discovery.yaml"
            )
            target.write_text(
                target.read_text(
                    encoding="utf-8"
                ).replace(
                    "person finds old key",
                    "person uncovers old key"
                ),
                encoding="utf-8"
            )
            changed = NarrativeReadingRegistry.from_directory(
                Path(
                    tmp
                )
                / "narrative_readings"
            ).resolve(
                "modo_conciencia.scene.scene_001_key_discovery"
            )

            self.assertNotEqual(
                original.fingerprint,
                changed.fingerprint
            )

    def test_fingerprint_is_independent_of_local_path(self):
        first = NarrativeReadingRegistry.from_directory(
            "data/narrative_readings"
        ).resolve(
            "modo_conciencia.scene.scene_001_key_discovery"
        )

        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(
                "data/narrative_readings",
                Path(
                    tmp
                )
                / "copy"
            )
            copied = NarrativeReadingRegistry.from_directory(
                Path(
                    tmp
                )
                / "copy"
            ).resolve(
                "modo_conciencia.scene.scene_001_key_discovery"
            )

            self.assertEqual(
                first.fingerprint,
                copied.fingerprint
            )

    def test_runtime_modules_do_not_import_narrative_reading_representation(self):
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
            "app.narrative_readings",
            source
        )
        self.assertNotIn(
            "NarrativeReadingRegistry",
            source
        )

    def test_representation_has_no_creative_or_execution_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.narrative_readings",
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
