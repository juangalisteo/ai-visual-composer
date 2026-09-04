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
                self.assertFalse(resolved.legacy)

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
                platform,
                style
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
                    resolved = manager.get_subtitle_profile()

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
                platform,
                style
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
                resolved = ConfigManager().get_subtitle_profile()
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
                SubtitleConfigLoader().load(main_profile),
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

    def test_legacy_execution_without_identity_remains_available(self):
        legacy_path = Path(
            "config/profiles/instagram/modo_conciencia.json"
        )
        environment = {
            "MC_PROFILE_PATH": str(legacy_path),
            "MC_PROFILE_COMPONENT": "",
            "MC_PROFILE_PLATFORM": "",
            "MC_PROFILE_ID": "",
            "MC_SUBTITLE_CONFIG": "word_by_word",
        }

        with patch.dict(os.environ, environment, clear=True):
            resolved = ConfigManager().get_subtitle_profile()

        legacy_profile = self._load(legacy_path)
        self.assertTrue(resolved.legacy)
        self.assertIsNone(resolved.key)
        self.assertEqual(
            self._load(
                "config/subtitle_configs/word_by_word.json"
            ),
            resolved.cue_policy
        )
        self.assertEqual(
            legacy_profile["video_style"]["subtitles"],
            resolved.render_style
        )

    def test_video_config_resolves_new_render_style_when_not_injected(self):
        environment = self._environment(
            ProfileComponent.VIDEO,
            ProfilePlatform.YOUTUBE,
            SubtitleStyle.SINGLE_LINE
        )

        with patch.dict(os.environ, environment, clear=True), patch.object(
            SubtitleConfigLoader,
            "load",
            side_effect=AssertionError(
                "Official render must not read video_style.subtitles"
            )
        ):
            loaded = VideoConfigLoader().load()

        expected = self._load(
            self._expected_path(
                ProfileComponent.VIDEO,
                ProfilePlatform.YOUTUBE,
                SubtitleStyle.SINGLE_LINE
            )
        )["render_style"]
        self.assertEqual(expected, loaded.subtitle_style)

    def test_design_and_video_srt_boundaries_remain_unchanged(self):
        for component in (
            ProfileComponent.IMAGEN,
            ProfileComponent.VIDEO,
        ):
            for platform in ProfilePlatform:
                with self.subTest(
                    component=component.value,
                    platform=platform.value
                ):
                    path = self.profile_resolver.resolve_design(
                        component,
                        platform
                    )
                    self.assertEqual(
                        Path("config/profiles/diseno")
                        / component.value
                        / f"{platform.value}.json",
                        path
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
        platform,
        style
    ):
        main_key = ProfileKey.for_component(component, platform)
        return {
            "MC_PROFILE_COMPONENT": component.value,
            "MC_PROFILE_PLATFORM": platform.value,
            "MC_PROFILE_ID": main_key.profile_id,
            "MC_PROFILE_PATH": str(
                self.profile_resolver.resolve(main_key)
            ),
            "MC_SUBTITLE_CONFIG": style.value,
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
