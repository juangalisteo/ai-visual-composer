import inspect
import unittest
from dataclasses import FrozenInstanceError, is_dataclass
from pathlib import Path

from app.backend_adapters import (
    BackendAdapterTrace,
    BackendAdapterTraceItem,
    ComfyUIAdapter,
    ComfyUIPayload,
)
from app.prompt_translation import (
    BackendPrompt,
    BackendPromptInstruction,
    BackendPromptTrace,
    BackendPromptTraceItem,
)


def backend_prompt():
    return BackendPrompt(
        instructions=(
            BackendPromptInstruction(
                id="visible_content",
                category="content",
                source_field="VisualBrief.visible_content",
                value="A person receives an old key."
            ),
            BackendPromptInstruction(
                id="felt_experience",
                category="experience",
                source_field="VisualBrief.felt_experience",
                value="contained solemnity"
            ),
            BackendPromptInstruction(
                id="visual_priority",
                category="priority",
                source_field="VisualBrief.visual_priority",
                value="consequence over object"
            ),
            BackendPromptInstruction(
                id="duplicate",
                category="coherence",
                source_field="VisualBrief.narrative_coherence",
                value="contained solemnity"
            ),
        ),
        trace=BackendPromptTrace(
            source_visual_brief_fingerprint="visual-brief-fingerprint",
            items=(
                BackendPromptTraceItem(
                    instruction_id="visible_content",
                    source_fields=(
                        "VisualBrief.visible_content",
                    ),
                    transformation="normalize_text"
                ),
                BackendPromptTraceItem(
                    instruction_id="felt_experience",
                    source_fields=(
                        "VisualBrief.felt_experience",
                    ),
                    transformation="normalize_text"
                ),
                BackendPromptTraceItem(
                    instruction_id="visual_priority",
                    source_fields=(
                        "VisualBrief.visual_priority",
                    ),
                    transformation="normalize_text"
                ),
            )
        ),
        source_id="scene_001",
        source_version="1.0.0",
        fingerprint="backend-prompt-fingerprint",
    )


class BackendAdapterTest(unittest.TestCase):

    def test_backend_adapter_models_are_passive_dataclasses(self):
        for model in (
            BackendAdapterTraceItem,
            BackendAdapterTrace,
            ComfyUIPayload,
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

    def test_comfyui_payload_is_immutable(self):
        payload = ComfyUIAdapter().adapt(
            backend_prompt()
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            payload.prompt = "changed"

    def test_adapts_backend_prompt_to_comfyui_payload(self):
        payload = ComfyUIAdapter().adapt(
            backend_prompt()
        )

        self.assertEqual(
            payload.provider,
            "comfyui"
        )
        self.assertEqual(
            payload.prompt,
            "A person receives an old key., contained solemnity, consequence over object"
        )
        self.assertEqual(
            payload.source_id,
            "scene_001"
        )
        self.assertEqual(
            payload.source_version,
            "1.0.0"
        )

    def test_adaptation_is_deterministic(self):
        prompt = backend_prompt()

        first = ComfyUIAdapter().adapt(
            prompt
        )
        second = ComfyUIAdapter().adapt(
            prompt
        )

        self.assertEqual(
            first,
            second
        )
        self.assertEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_fingerprint_changes_when_payload_changes(self):
        first = ComfyUIAdapter().adapt(
            backend_prompt()
        )
        changed = BackendPrompt(
            instructions=(
                BackendPromptInstruction(
                    id="visible_content",
                    category="content",
                    source_field="VisualBrief.visible_content",
                    value="A different image instruction."
                ),
            ),
            trace=BackendPromptTrace(),
            fingerprint="changed-prompt",
        )
        second = ComfyUIAdapter().adapt(
            changed
        )

        self.assertNotEqual(
            first.fingerprint,
            second.fingerprint
        )

    def test_trace_connects_payload_to_backend_prompt_and_visual_brief(self):
        payload = ComfyUIAdapter().adapt(
            backend_prompt()
        )
        trace_item = payload.trace.items[0]

        self.assertEqual(
            payload.trace.source_backend_prompt_fingerprint,
            "backend-prompt-fingerprint"
        )
        self.assertEqual(
            trace_item.payload_field,
            "prompt"
        )
        self.assertIn(
            "visible_content",
            trace_item.instruction_ids
        )
        self.assertIn(
            "VisualBrief.visible_content",
            trace_item.source_fields
        )

    def test_comfyui_payload_is_compatible_with_current_runtime_prompt_input(self):
        payload = ComfyUIAdapter().adapt(
            backend_prompt()
        )

        self.assertIsInstance(
            payload.prompt,
            str
        )
        self.assertTrue(
            payload.prompt
        )

    def test_backend_adapter_has_no_cognitive_or_runtime_dependencies(self):
        source = inspect.getsource(
            __import__(
                "app.backend_adapters",
                fromlist=[
                    "x"
                ]
            )
        )
        forbidden = (
            "VisualBible",
            "NarrativeReading",
            "Intention",
            "VisualDirector",
            "VisualBrief",
            "PromptTranslator",
            "ImageBuilder",
            "ImagePromptSystem",
            "ComfyUIBackend",
            "ImageManifestWriter",
            "workflow",
            "manifest",
            "requests",
            "urllib",
            "FFmpeg",
            "client_id",
            "output_dir",
        )

        for item in forbidden:
            with self.subTest(
                item=item
            ):
                self.assertNotIn(
                    item,
                    source
                )

    def test_runtime_imports_backend_adapters_only_from_image_builder(self):
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
                if "app.backend_adapters" in source:
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
