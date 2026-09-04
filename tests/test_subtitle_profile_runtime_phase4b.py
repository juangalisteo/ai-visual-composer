import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.controllers.run_controller import RunController
from app.modules.subtitles.models.single_line_model import (
    SingleLineModel,
)
from app.modules.subtitles.models.word_by_word_model import (
    WordByWordModel,
)
from app.modules.subtitles.srt_optimizer import SrtOptimizer
from app.modules.video.config.loaders.subtitle_loader import (
    SubtitleConfigLoader,
)
from app.modules.video.subtitles.subtitle_style_builder import (
    SubtitleStyleBuilder,
)
from app.modules.video.video_config import VideoConfigLoader
from app.shared.config_manager import ConfigManager
from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
    ProfilePlatform,
)
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import (
    SubtitleProfileKey,
    SubtitleStyle,
)
from app.shared.subtitle_profile_resolver import (
    SubtitleProfileResolver,
)


class _FontManager:

    def resolve_name(self, name):
        return name


class SubtitleProfileRuntimePhase4BTest(unittest.TestCase):

    COMPONENTS = tuple(ProfileComponent)
    PLATFORMS = tuple(ProfilePlatform)
    STYLES = tuple(SubtitleStyle)

    def setUp(self):
        self.profile_resolver = ProfileResolver()
        self.subtitle_resolver = SubtitleProfileResolver()

    def test_resolves_exact_twelve_profile_matrix(self):
        resolved_paths = set()
        profile_ids = set()

        for component, platform, style in self._cases():
            main_key = ProfileKey.for_component(component, platform)
            key = SubtitleProfileKey.for_profile(main_key, style)
            resolved = self.subtitle_resolver.load(key)

            with self.subTest(profile_id=key.profile_id):
                self.assertEqual(
                    self._expected_path(component, platform, style),
                    resolved.path
                )
                self.assertEqual(key, resolved.key)

            resolved_paths.add(resolved.path)
            profile_ids.add(key.profile_id)

        self.assertEqual(12, len(resolved_paths))
        self.assertEqual(12, len(profile_ids))

    def test_rejects_invalid_component_platform_and_style(self):
        with self.assertRaisesRegex(ValueError, "Componente"):
            SubtitleProfileKey(
                component="design",
                platform="instagram",
                style="single_line",
                profile_id="invalid"
            )

        with self.assertRaisesRegex(ValueError, "Plataforma"):
            SubtitleProfileKey(
                component="video",
                platform="tiktok",
                style="single_line",
                profile_id="invalid"
            )

        with self.assertRaisesRegex(ValueError, "Estilo"):
            SubtitleProfileKey(
                component="video",
                platform="instagram",
                style="karaoke",
                profile_id="invalid"
            )

    def test_rejects_incompatible_profile_id(self):
        with self.assertRaisesRegex(
            ValueError,
            "profile_id de subtitulos incompatible"
        ):
            SubtitleProfileKey(
                component="video",
                platform="instagram",
                style="single_line",
                profile_id=(
                    "subtitulo_video_youtube_linea_unica"
                )
            )

    def test_missing_official_profile_is_explicit_without_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profiles"
            alternatives = (
                (
                    ProfileComponent.VIDEO,
                    ProfilePlatform.YOUTUBE,
                ),
                (
                    ProfileComponent.IMAGEN,
                    ProfilePlatform.INSTAGRAM,
                ),
            )
            for component, platform in alternatives:
                alternative_key = SubtitleProfileKey.for_profile(
                    ProfileKey.for_component(component, platform),
                    "single_line"
                )
                alternative_path = root / alternative_key.relative_path
                alternative_path.parent.mkdir(parents=True)
                alternative_path.write_text(
                    self._expected_path(
                        component,
                        platform,
                        SubtitleStyle.SINGLE_LINE
                    ).read_text(encoding="utf-8"),
                    encoding="utf-8"
                )

            instagram_key = SubtitleProfileKey.for_profile(
                ProfileKey.for_component("video", "instagram"),
                "single_line"
            )
            resolver = SubtitleProfileResolver(root)

            with self.assertRaisesRegex(
                FileNotFoundError,
                "No existe el perfil de subtitulos esperado"
            ):
                resolver.load(instagram_key)

    def test_loaded_profiles_do_not_share_mutable_configuration(self):
        key = SubtitleProfileKey.for_profile(
            ProfileKey.for_component("video", "instagram"),
            "word_by_word"
        )
        first = self.subtitle_resolver.load(key)
        second = self.subtitle_resolver.load(key)

        first.cue_policy["min_duration"] = 99
        first.render_style["font_size"] = 99

        self.assertNotEqual(
            first.cue_policy["min_duration"],
            second.cue_policy["min_duration"]
        )
        self.assertNotEqual(
            first.render_style["font_size"],
            second.render_style["font_size"]
        )
        self.assertEqual(
            self._load(self._expected_path(
                ProfileComponent.VIDEO,
                ProfilePlatform.INSTAGRAM,
                SubtitleStyle.WORD_BY_WORD
            ))["cue_policy"],
            second.cue_policy
        )

    def test_rejects_internal_identity_that_disagrees_with_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profiles"
            key = SubtitleProfileKey.for_profile(
                ProfileKey.for_component("imagen", "instagram"),
                "word_by_word"
            )
            path = root / key.relative_path
            path.parent.mkdir(parents=True)
            data = self._load(
                self._expected_path(
                    key.component,
                    key.platform,
                    key.style
                )
            )
            data["component"] = "video"
            path.write_text(
                json.dumps(data),
                encoding="utf-8"
            )

            with self.assertRaisesRegex(
                ValueError,
                "identidad interna"
            ):
                SubtitleProfileResolver(root).load(key)

    def test_console_keeps_two_styles_and_resolves_selected_identity(self):
        selections = (
            ("1", SubtitleStyle.SINGLE_LINE),
            ("2", SubtitleStyle.WORD_BY_WORD),
        )

        for option, style in selections:
            with self.subTest(style=style.value), patch(
                "builtins.input",
                return_value=option
            ):
                selected = RunController().select_subtitle_config()

            self.assertEqual(style.value, selected)
            key = SubtitleProfileKey.for_profile(
                ProfileKey.for_component("video", "instagram"),
                selected
            )
            self.assertEqual(
                self._expected_path(
                    ProfileComponent.VIDEO,
                    ProfilePlatform.INSTAGRAM,
                    style
                ),
                self.subtitle_resolver.resolve(key)
            )

    def test_official_config_manager_never_loads_legacy_subtitle_json(self):
        for component, platform, style in self._cases():
            environment = self._environment(
                component,
                platform
            )
            with self.subTest(
                component=component.value,
                platform=platform.value,
                style=style.value
            ), patch.dict(os.environ, environment, clear=True):
                manager = ConfigManager()
                with patch.object(
                    manager,
                    "load_json",
                    side_effect=AssertionError(
                        "Official subtitles must not use legacy JSON"
                    )
                ):
                    resolved = manager.get_subtitle_profile(
                        style
                    )

            self.assertEqual(
                self._expected_path(component, platform, style),
                resolved.path
            )

    def test_runtime_effective_behavior_matches_legacy_for_all_profiles(self):
        style_builder = SubtitleStyleBuilder(
            font_manager=_FontManager()
        )

        for component, platform, style in self._cases():
            environment = self._environment(
                component,
                platform
            )
            main_profile = self.profile_resolver.load(
                ProfileKey.for_component(component, platform)
            )
            legacy_cue = self._load(
                Path("config/subtitle_configs")
                / f"{style.value}.json"
            )
            legacy_render = main_profile[
                "video_style"
            ]["subtitles"]
            fps = main_profile["video_style"]["fps"]

            with self.subTest(
                component=component.value,
                platform=platform.value,
                style=style.value
            ), patch.dict(os.environ, environment, clear=True):
                resolved = ConfigManager().get_subtitle_profile(
                    style
                )
                optimizer = SrtOptimizer(
                    subtitle_profile=resolved,
                    render_fps=fps
                )
                video_config = VideoConfigLoader(
                    subtitle_profile=resolved
                ).load()

            self.assertEqual(legacy_cue, resolved.cue_policy)
            self.assertEqual(legacy_render, resolved.render_style)
            self.assertEqual(
                SubtitleConfigLoader().load_render_style(
                    legacy_render
                ),
                video_config.subtitles
            )
            self.assertEqual(
                style_builder.build(legacy_render),
                style_builder.build(video_config.subtitle_style)
            )
            self._assert_model_equivalent(
                optimizer.model,
                style,
                legacy_cue,
                fps
            )

    def test_subtitle_execution_without_identity_fails_explicitly(self):
        environment = {
            "MC_PROFILE_COMPONENT": "",
            "MC_PROFILE_PLATFORM": "",
            "MC_PROFILE_ID": "",
        }

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(
                ValueError,
                "Falta identidad estructurada de perfil"
            ):
                ConfigManager().get_subtitle_profile(
                    "word_by_word"
                )

    def test_video_config_uses_injected_resolved_render_style(self):
        environment = self._environment(
            ProfileComponent.VIDEO,
            ProfilePlatform.YOUTUBE
        )

        with patch.dict(os.environ, environment, clear=True):
            resolved = ConfigManager().get_subtitle_profile(
                SubtitleStyle.SINGLE_LINE
            )
            loaded = VideoConfigLoader(
                subtitle_profile=resolved
            ).load()

        expected = self._load(
            self._expected_path(
                ProfileComponent.VIDEO,
                ProfilePlatform.YOUTUBE,
                SubtitleStyle.SINGLE_LINE
            )
        )["render_style"]
        self.assertEqual(expected, loaded.subtitle_style)

    def test_legacy_runtime_apis_and_sources_are_not_productive(self):
        self.assertFalse(
            hasattr(ConfigManager, "get_subtitle_config")
        )
        self.assertFalse(
            hasattr(SubtitleConfigLoader, "load")
        )

        paths = (
            Path("main.py"),
            *Path("app").rglob("*.py"),
            *Path("certification").rglob("*.py"),
        )
        forbidden = (
            "MC_SUBTITLE_CONFIG",
            "config/subtitle_configs",
            "get_subtitle_config(",
            "video_style.subtitles",
        )

        for path in paths:
            source = path.read_text(encoding="utf-8")
            for value in forbidden:
                with self.subTest(path=path, value=value):
                    self.assertNotIn(value, source)

    def test_optimizer_requires_resolved_subtitle_profile(self):
        with self.assertRaises(TypeError):
            SrtOptimizer()

    def test_design_legacy_files_and_video_srt_boundaries_remain_unchanged(self):
        for component in (
            ProfileComponent.IMAGEN,
            ProfileComponent.VIDEO,
        ):
            for platform in ProfilePlatform:
                with self.subTest(
                    component=component.value,
                    platform=platform.value
                ):
                    legacy_path = (
                        Path("config/profiles/diseno")
                        / component.value
                        / f"{platform.value}.json"
                    )
                    self.assertTrue(
                        legacy_path.is_file()
                    )

        self.assertFalse(
            Path("config/profiles/video_srt").exists()
        )

    def _cases(self):
        for component in self.COMPONENTS:
            for platform in self.PLATFORMS:
                for style in self.STYLES:
                    yield component, platform, style

    def _environment(
        self,
        component,
        platform
    ):
        main_key = ProfileKey.for_component(component, platform)
        return {
            "MC_PROFILE_COMPONENT": component.value,
            "MC_PROFILE_PLATFORM": platform.value,
            "MC_PROFILE_ID": main_key.profile_id,
        }

    def _expected_path(
        self,
        component,
        platform,
        style
    ):
        key = SubtitleProfileKey.for_profile(
            ProfileKey.for_component(component, platform),
            style
        )
        return Path("config/profiles") / key.relative_path

    def _assert_model_equivalent(
        self,
        model,
        style,
        cue_policy,
        fps
    ):
        if style is SubtitleStyle.SINGLE_LINE:
            self.assertIsInstance(model, SingleLineModel)
            self.assertEqual(
                cue_policy["max_chars_per_line"],
                model.max_chars_per_line
            )
            self.assertEqual(
                cue_policy["min_duration"],
                model.min_duration
            )
            self.assertEqual(
                cue_policy["max_duration"],
                model.max_duration
            )
            return

        self.assertIsInstance(model, WordByWordModel)
        self.assertEqual(cue_policy["min_duration"], model.min_duration)
        self.assertEqual(cue_policy["max_duration"], model.max_duration)
        self.assertEqual(cue_policy["micro_cues"], model.micro_cues)
        self.assertEqual(float(fps), model.render_fps)

    def _load(self, path):
        return json.loads(
            Path(path).read_text(encoding="utf-8")
        )


if __name__ == "__main__":
    unittest.main()
