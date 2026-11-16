from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.modules.video.config.overlay_config import OverlayConfig
from app.modules.video.overlays.overlay_builder import OverlayBuilder
from app.modules.video.overlays.overlay_folder_resolver import (
    OverlayCategoryResolution,
    OverlayFolderResolver,
    _OverlayOllamaProvider,
)


class FakeProvider:

    def __init__(
        self,
        response=None,
        error=None
    ):
        self.response = response
        self.error = error
        self.prompts = []

    def generate(
        self,
        prompt
    ):
        self.prompts.append(
            prompt
        )

        if self.error is not None:
            raise self.error

        return self.response


class FakeOllamaResponse:

    def raise_for_status(self):
        return None

    def json(self):
        return {"response": "Electricity"}


def overlay_config(
    directory,
    enabled=True,
    folders=()
):
    return OverlayConfig(
        enabled=enabled,
        directory=str(
            directory
        ),
        folder_selection="sequence",
        file_selection="sequence",
        avoid_repeats=True,
        repeat_mode="scene",
        min_seconds=1.0,
        max_seconds=1.0,
        loop_file=True,
        opacity=0.5,
        blend_mode="screen",
        probability=1.0,
        folders=folders,
        types=(),
        extensions=(
            ".mp4",
            ".mov"
        ),
        folder_weights={},
        file_weights={}
    )


class OverlayFolderResolverTest(
    unittest.TestCase
):

    def test_ollama_provider_omits_request_timeout(self):
        with patch(
            "app.modules.video.overlays.overlay_folder_resolver.requests.post",
            return_value=FakeOllamaResponse(),
        ) as post_mock:
            response = _OverlayOllamaProvider("fake-model").generate(
                "prompt"
            )

        self.assertEqual("Electricity", response)
        self.assertNotIn("timeout", post_mock.call_args.kwargs)

    def test_discovers_only_real_overlay_folders_with_valid_assets(
        self
    ):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(
                root
            )
            electricity = root_path / "Electricity"
            light_leaks = root_path / "Light Leaks"
            empty = root_path / "Empty"
            electricity.mkdir()
            light_leaks.mkdir()
            empty.mkdir()

            (
                electricity
                / "Electricity 1.mp4"
            ).touch()
            (
                electricity
                / "Electricity 2.mp4"
            ).touch()
            (
                light_leaks
                / "Light Leak 1.mov"
            ).touch()
            (
                empty
                / "notes.txt"
            ).touch()

            folders = (
                OverlayFolderResolver()
                .discover_valid_folders(
                    directory=root_path,
                    extensions=(
                        ".mp4",
                        ".mov"
                    )
                )
            )

        self.assertEqual(
            (
                "Electricity",
                "Light Leaks"
            ),
            folders
        )
        self.assertNotIn(
            "Electricity 1.mp4",
            folders
        )
        self.assertNotIn(
            "Empty",
            folders
        )

    def test_accepts_exact_existing_semantic_folder(
        self
    ):
        resolver = OverlayFolderResolver(
            provider=FakeProvider(
                response="Electricity"
            )
        )

        selected = resolver.resolve(
            topic="Nikola Tesla",
            folders=(
                "Electricity",
                "Light Leaks"
            )
        )

        self.assertEqual(
            "Electricity",
            selected
        )

    def test_resolves_primary_and_secondary_thematic_folders(
        self
    ):
        resolver = OverlayFolderResolver(
            provider=FakeProvider(
                response=(
                    "PRIMARY: Electricity\n"
                    "SECONDARY: Technology, Particles"
                )
            )
        )

        resolution = resolver.resolve_categories(
            topic="Nikola Tesla",
            folders=(
                "Electricity",
                "Technology",
                "Particles",
                "Nature"
            )
        )

        self.assertEqual(
            OverlayCategoryResolution(
                primary="Electricity",
                secondary=(
                    "Technology",
                    "Particles"
                )
            ),
            resolution
        )
        self.assertEqual(
            (
                "Electricity",
                "Technology",
                "Particles"
            ),
            resolution.thematic_folders
        )

    def test_resolves_primary_with_no_secondary_categories(
        self
    ):
        resolver = OverlayFolderResolver(
            provider=FakeProvider(
                response=(
                    "PRIMARY: Electricity\n"
                    "SECONDARY: NONE"
                )
            )
        )

        resolution = resolver.resolve_categories(
            topic="Nikola Tesla",
            folders=(
                "Electricity",
                "Technology"
            )
        )

        self.assertEqual(
            "Electricity",
            resolution.primary
        )
        self.assertEqual(
            (),
            resolution.secondary
        )

    def test_rejects_nonexistent_category(
        self
    ):
        resolver = OverlayFolderResolver(
            provider=FakeProvider(
                response="Technology"
            )
        )

        self.assertIsNone(
            resolver.resolve(
                topic="Nikola Tesla",
                folders=(
                    "Electricity",
                    "Light Leaks"
                )
            )
        )

    def test_rejects_nonexistent_structured_category(
        self
    ):
        resolver = OverlayFolderResolver(
            provider=FakeProvider(
                response=(
                    "PRIMARY: Technology\n"
                    "SECONDARY: Electricity"
                )
            )
        )

        self.assertEqual(
            OverlayCategoryResolution(),
            resolver.resolve_categories(
                topic="Nikola Tesla",
                folders=(
                    "Electricity",
                )
            )
        )

    def test_filters_invalid_secondary_categories(
        self
    ):
        resolver = OverlayFolderResolver(
            provider=FakeProvider(
                response=(
                    "PRIMARY: Electricity\n"
                    "SECONDARY: Technology, Nature"
                )
            )
        )

        resolution = resolver.resolve_categories(
            topic="Nikola Tesla",
            folders=(
                "Electricity",
                "Technology"
            )
        )

        self.assertEqual(
            "Electricity",
            resolution.primary
        )
        self.assertEqual(
            (
                "Technology",
            ),
            resolution.secondary
        )

    def test_rejects_extra_text(
        self
    ):
        resolver = OverlayFolderResolver(
            provider=FakeProvider(
                response=(
                    "Electricity porque Tesla trabajaba "
                    "con electricidad"
                )
            )
        )

        self.assertIsNone(
            resolver.resolve(
                topic="Nikola Tesla",
                folders=(
                    "Electricity",
                    "Light Leaks"
                )
            )
        )

    def test_rejects_empty_response(
        self
    ):
        for response in ("", "   ", " \n "):
            with self.subTest(response=response):
                provider = FakeProvider(
                    response=response
                )
                resolver = OverlayFolderResolver(
                    provider=provider
                )

                resolution = resolver.resolve_categories(
                    topic="Nikola Tesla",
                    folders=(
                        "Electricity",
                        "Light Leaks"
                    )
                )

                self.assertEqual(
                    1,
                    len(provider.prompts)
                )
                self.assertIsNone(
                    resolution.primary
                )
                self.assertEqual(
                    (),
                    resolution.thematic_folders
                )

    def test_none_response_is_valid_neutral_fallback_signal(
        self
    ):
        resolver = OverlayFolderResolver(
            provider=FakeProvider(
                response="NONE"
            )
        )

        self.assertIsNone(
            resolver.resolve(
                topic="Aleister Crowley",
                folders=(
                    "Electricity",
                )
            )
        )

    def test_prompt_allows_none_without_listing_neutral_fallback(
        self
    ):
        provider = FakeProvider(
            response="NONE"
        )
        resolver = OverlayFolderResolver(
            provider=provider
        )

        resolver.resolve(
            topic="Aleister Crowley",
            folders=(
                "Electricity",
            )
        )

        prompt = provider.prompts[0]
        self.assertIn(
            "NONE",
            prompt
        )
        self.assertIn(
            "No incluyas categorias unicamente",
            prompt
        )
        self.assertIn(
            "Electricity",
            prompt
        )
        self.assertNotIn(
            "Light Leaks",
            prompt
        )

        self.assertIsNone(
            resolver.resolve(
                topic="Nikola Tesla",
                folders=(
                    "Electricity",
                )
            )
        )

    def test_ai_failure_returns_none_for_fallback(
        self
    ):
        resolver = OverlayFolderResolver(
            provider=FakeProvider(
                error=RuntimeError(
                    "offline"
                )
            )
        )

        self.assertIsNone(
            resolver.resolve(
                topic="Nikola Tesla",
                folders=(
                    "Electricity",
                )
            )
        )

    def test_existing_overlay_builder_selects_file_inside_selected_folder(
        self
    ):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(
                root
            )
            electricity = root_path / "Electricity"
            light_leaks = root_path / "Light Leaks"
            electricity.mkdir()
            light_leaks.mkdir()

            selected_asset = (
                electricity
                / "Electricity 1.mp4"
            )
            selected_asset.touch()
            (
                light_leaks
                / "Light Leak 1.mp4"
            ).touch()

            builder = OverlayBuilder(
                overlay_config(
                    directory=root_path,
                    folders=(
                        "Electricity",
                    )
                )
            )

            result = builder.build(
                scene_index=0,
                scene_count=1
            )

        self.assertEqual(
            selected_asset.name,
            result["overlay"]
        )
        self.assertEqual(
            selected_asset.resolve(),
            result["overlay_path"]
        )


if __name__ == "__main__":
    unittest.main()
