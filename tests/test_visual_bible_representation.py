import inspect
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from app.domain import VisualBible
from app.visual_bibles import (
    EffectiveVisualBible,
    VisualBibleDocument,
    VisualBibleLoader,
    VisualBibleRegistry,
)


ROOT_YAML = """
schema_version: 1
id: root
version: "1.0.0"
type: root
title: Root
extends: null
composes:
metadata:
  owner: Test
  status: draft
  description: Test root.
inheritance_policy:
  locked:
    - philosophy.beauty
  appendable:
    - symbolic_system.recurring_symbols
    - creative_limits.cliches
  overridable:
    - cinematic_language.rhythm
    - composition.density
visual_bible:
  philosophy:
    beauty: sober
  identity:
    visual_statement: clear identity
  cinematic_language:
    rhythm: slow
  realism_and_abstraction:
    realism_level: grounded
  symbolic_system:
    recurring_symbols:
      - reflection
  composition:
    density: low
  photography:
    point_of_view: observational
  lighting:
    dominant_source: window
  color:
    dominant_temperature: warm
  texture_and_materiality:
    tactility: visible
  continuity:
    atmosphere: quiet
  creative_limits:
    cliches:
      - portal
  quality:
    coherence: whole
"""


CHILD_YAML = """
schema_version: 1
id: child
version: "1.0.0"
type: sequence
title: Child
extends: root
composes:
metadata:
  owner: Test
  status: draft
  description: Child.
inheritance_policy:
  locked:
  appendable:
  overridable:
visual_bible:
  cinematic_language:
    rhythm: very slow
  symbolic_system:
    recurring_symbols:
      - reflection
      - nested scale
"""


PLATFORM_YAML = """
schema_version: 1
id: platform.instagram
version: "1.0.0"
type: platform
title: Platform
extends: null
composes:
metadata:
  owner: Test
  status: draft
  description: Platform.
inheritance_policy:
  locked:
  appendable:
  overridable:
visual_bible:
  composition:
    density: compact
  creative_limits:
    cliches:
      - crowded collage
"""


COMPOSED_CHILD_YAML = """
schema_version: 1
id: composed_child
version: "1.0.0"
type: sequence
title: Composed Child
extends: root
composes:
  - reference: platform.instagram
    role: platform
metadata:
  owner: Test
  status: draft
  description: Composed child.
inheritance_policy:
  locked:
  appendable:
  overridable:
visual_bible:
  cinematic_language:
    rhythm: very slow
"""


class VisualBibleRepresentationTest(unittest.TestCase):

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

    def test_loads_valid_root_yaml_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                Path(
                    tmp
                ),
                "root.yaml",
                ROOT_YAML
            )

            document = VisualBibleLoader().load_file(
                path
            )

            self.assertIsInstance(
                document,
                VisualBibleDocument
            )
            self.assertEqual(
                document.id,
                "root"
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
                VisualBibleLoader().load_file(
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
                VisualBibleLoader().load_file(
                    path
                )

    def test_rejects_unsupported_schema_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                Path(
                    tmp
                ),
                "root.yaml",
                ROOT_YAML.replace(
                    "schema_version: 1",
                    "schema_version: 99"
                )
            )

            with self.assertRaises(
                ValueError
            ):
                VisualBibleLoader().load_file(
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
                ROOT_YAML
            )
            self._write(
                base,
                "nested/b.yaml",
                ROOT_YAML
            )

            with self.assertRaises(
                ValueError
            ):
                VisualBibleRegistry.from_directory(
                    tmp
                )

    def test_resolves_extends_and_inherits_missing_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(
                tmp
            )
            self._write(
                base,
                "root.yaml",
                ROOT_YAML
            )
            self._write(
                base,
                "child.yaml",
                CHILD_YAML
            )

            effective = VisualBibleRegistry.from_directory(
                tmp
            ).resolve(
                "child"
            )

            self.assertEqual(
                effective.inheritance_chain,
                (
                    "root",
                    "child",
                )
            )
            self.assertEqual(
                effective.visual_bible.identity.visual_statement,
                "clear identity"
            )
            self.assertEqual(
                effective.visual_bible.cinematic_language.rhythm,
                "very slow"
            )

    def test_detects_missing_extends_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                Path(
                    tmp
                ),
                "child.yaml",
                CHILD_YAML
            )
            registry = VisualBibleRegistry(
                (
                    VisualBibleLoader().load_file(
                        path
                    ),
                )
            )

            with self.assertRaises(
                ValueError
            ):
                registry.resolve(
                    "child"
                )

    def test_detects_extends_cycles(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(
                tmp
            )
            self._write(
                base,
                "a.yaml",
                ROOT_YAML.replace(
                    "id: root",
                    "id: a"
                ).replace(
                    "extends: null",
                    "extends: b"
                )
            )
            self._write(
                base,
                "b.yaml",
                CHILD_YAML.replace(
                    "id: child",
                    "id: b"
                ).replace(
                    "extends: root",
                    "extends: a"
                )
            )

            with self.assertRaises(
                ValueError
            ):
                VisualBibleRegistry.from_directory(
                    tmp
                ).resolve(
                    "a"
                )

    def test_rejects_locked_overwrite(self):
        locked_child = CHILD_YAML + """
visual_bible:
  philosophy:
    beauty: loud
"""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(
                tmp
            )
            self._write(
                base,
                "root.yaml",
                ROOT_YAML
            )
            self._write(
                base,
                "child.yaml",
                locked_child
            )

            with self.assertRaises(
                ValueError
            ):
                VisualBibleRegistry.from_directory(
                    tmp
                ).resolve(
                    "child"
                )

    def test_appends_lists_and_deduplicates_deterministically(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(
                tmp
            )
            self._write(
                base,
                "root.yaml",
                ROOT_YAML
            )
            self._write(
                base,
                "child.yaml",
                CHILD_YAML
            )

            effective = VisualBibleRegistry.from_directory(
                tmp
            ).resolve(
                "child"
            )

            self.assertEqual(
                effective.visual_bible.symbolic_system.recurring_symbols,
                (
                    "reflection",
                    "nested scale",
                )
            )

    def test_resolves_composes_after_inheritance(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(
                tmp
            )
            self._write(
                base,
                "root.yaml",
                ROOT_YAML
            )
            self._write(
                base,
                "platform.yaml",
                PLATFORM_YAML
            )
            self._write(
                base,
                "child.yaml",
                COMPOSED_CHILD_YAML
            )

            effective = VisualBibleRegistry.from_directory(
                tmp
            ).resolve(
                "composed_child"
            )

            self.assertEqual(
                effective.composed_layers,
                (
                    "platform.instagram",
                )
            )
            self.assertEqual(
                effective.visual_bible.composition.density,
                "compact"
            )
            self.assertEqual(
                effective.visual_bible.creative_limits.cliches,
                (
                    "portal",
                    "crowded collage",
                )
            )

    def test_detects_missing_compose_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(
                tmp
            )
            self._write(
                base,
                "root.yaml",
                ROOT_YAML
            )
            self._write(
                base,
                "child.yaml",
                COMPOSED_CHILD_YAML
            )

            with self.assertRaises(
                ValueError
            ):
                VisualBibleRegistry.from_directory(
                    tmp
                ).resolve(
                    "composed_child"
                )

    def test_detects_composition_cycles(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(
                tmp
            )
            first = PLATFORM_YAML.replace(
                "id: platform.instagram",
                "id: platform.one"
            ).replace(
                "composes:",
                "composes:\n  - reference: platform.two\n    role: platform",
                1
            )
            second = PLATFORM_YAML.replace(
                "id: platform.instagram",
                "id: platform.two"
            ).replace(
                "composes:",
                "composes:\n  - reference: platform.one\n    role: platform",
                1
            )
            child = COMPOSED_CHILD_YAML.replace(
                "platform.instagram",
                "platform.one"
            )
            self._write(
                base,
                "root.yaml",
                ROOT_YAML
            )
            self._write(
                base,
                "one.yaml",
                first
            )
            self._write(
                base,
                "two.yaml",
                second
            )
            self._write(
                base,
                "child.yaml",
                child
            )

            with self.assertRaises(
                ValueError
            ):
                VisualBibleRegistry.from_directory(
                    tmp
                ).resolve(
                    "composed_child"
                )

    def test_constructs_domain_visual_bible_and_effective_visual_bible(self):
        effective = VisualBibleRegistry.from_directory(
            "config/visual_bibles"
        ).resolve(
            "modo_conciencia.sequence.correspondencia_intro"
        )

        self.assertIsInstance(
            effective.visual_bible,
            VisualBible
        )
        self.assertIsInstance(
            effective,
            EffectiveVisualBible
        )

    def test_trace_contains_inheritance_composition_and_field_origins(self):
        effective = VisualBibleRegistry.from_directory(
            "config/visual_bibles"
        ).resolve(
            "modo_conciencia.sequence.correspondencia_intro"
        )

        self.assertEqual(
            effective.inheritance_chain,
            (
                "modo_conciencia.root",
                "modo_conciencia.series.documental_correspondencia",
                "modo_conciencia.episode.correspondencia_universal",
                "modo_conciencia.sequence.correspondencia_intro",
            )
        )
        self.assertEqual(
            effective.composed_layers,
            (
                "modo_conciencia.platform.instagram",
            )
        )
        self.assertTrue(
            effective.trace.field_origins
        )

    def test_fingerprint_is_stable_for_identical_effective_content(self):
        first = VisualBibleRegistry.from_directory(
            "config/visual_bibles"
        ).resolve(
            "modo_conciencia.sequence.correspondencia_intro"
        )
        second = VisualBibleRegistry.from_directory(
            "config/visual_bibles"
        ).resolve(
            "modo_conciencia.sequence.correspondencia_intro"
        )

        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_fingerprint_changes_when_effective_content_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(
                "config/visual_bibles",
                Path(
                    tmp
                ) / "visual_bibles"
            )
            target = (
                Path(
                    tmp
                )
                / "visual_bibles"
                / "modo_conciencia"
                / "sequences"
                / "correspondencia_intro.yaml"
            )
            original = VisualBibleRegistry.from_directory(
                "config/visual_bibles"
            ).resolve(
                "modo_conciencia.sequence.correspondencia_intro"
            )
            target.write_text(
                target.read_text(
                    encoding="utf-8"
                ).replace(
                    "rhythm: very slow",
                    "rhythm: suspended"
                ),
                encoding="utf-8"
            )
            changed = VisualBibleRegistry.from_directory(
                Path(
                    tmp
                )
                / "visual_bibles"
            ).resolve(
                "modo_conciencia.sequence.correspondencia_intro"
            )

            self.assertNotEqual(
                original.fingerprint,
                changed.fingerprint
            )

    def test_fingerprint_is_independent_of_local_path(self):
        first = VisualBibleRegistry.from_directory(
            "config/visual_bibles"
        ).resolve(
            "modo_conciencia.sequence.correspondencia_intro"
        )

        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(
                "config/visual_bibles",
                Path(
                    tmp
                )
                / "copy"
            )
            copied = VisualBibleRegistry.from_directory(
                Path(
                    tmp
                )
                / "copy"
            ).resolve(
                "modo_conciencia.sequence.correspondencia_intro"
            )

            self.assertEqual(
                first.fingerprint,
                copied.fingerprint
            )

    def test_runtime_modules_do_not_import_visual_bible_representation(self):
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
            "app.visual_bibles",
            source
        )
        self.assertNotIn(
            "VisualBibleRegistry",
            source
        )

    def test_visual_bible_representation_has_no_prompt_backend_or_manifest_dependency(self):
        source = inspect.getsource(
            __import__(
                "app.visual_bibles",
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
