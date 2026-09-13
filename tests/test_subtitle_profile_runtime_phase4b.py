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
    ProfileFamily,
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

    COMPONENTS = (
        ProfileComponent.GUION,
        ProfileComponent.IMAGEN,
        ProfileComponent.VIDEO,
    )
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

    def test_design_subtitle_profile_is_embedded_in_one_design_json(self):
        for component in ProfileComponent:
            main_key = ProfileKey.for_component(
                component,
                ProfilePlatform.INSTAGRAM,
                family=ProfileFamily.DESIGN,
                profile_id=(
                    f"{component.value}_instagram_design_"
                    "modo_conciencia_studio_1"
                ),
            )
            for style in (SubtitleStyle.WORD_BY_WORD,):
                with self.subTest(component=component.value, style=style.value):
                    key = SubtitleProfileKey.for_profile(main_key, style)
                    resolved = self.subtitle_resolver.load(key)
                    self.assertEqual(ProfileFamily.DESIGN, resolved.key.family)
                    self.assertEqual(main_key.profile_id, resolved.key.parent_profile_id)
                    self.assertEqual(
                        Path("config/profiles")
                        / component.value
                        / "instagram"
                        / "design"
                        / "modo_conciencia_studio_1.json",
                        resolved.path,
                    )

                    environment = {
                        "MC_PROFILE_COMPONENT": component.value,
                        "MC_PROFILE_PLATFORM": "instagram",
                        "MC_PROFILE_ID": main_key.profile_id,
                        "MC_PROFILE_FAMILY": "design",
                    }
                    with patch.dict(os.environ, environment, clear=True):
                        self.assertEqual(
                            resolved.path,
                            ConfigManager().get_subtitle_profile(style).path,
                        )

    def test_design_subtitles_do_not_fallback_to_system(self):
        main_key = ProfileKey.for_component(
            "studio",
            "instagram",
            family="design",
            profile_id="studio_instagram_design_modo_conciencia_studio_1",
        )
        design_key = SubtitleProfileKey.for_profile(main_key, "single_line")
        system_source = self._expected_path(
            ProfileComponent.VIDEO,
            ProfilePlatform.INSTAGRAM,
            SubtitleStyle.SINGLE_LINE,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profiles"
            system_path = root / "studio/instagram/estandar/subtitulo_studio_instagram_linea_unica.json"
            system_path.parent.mkdir(parents=True)
            system_path.write_text(system_source.read_text(encoding="utf-8"), encoding="utf-8")

            with self.assertRaisesRegex(
                FileNotFoundError,
                "No existe el perfil de subtitulos esperado",
            ):
                SubtitleProfileResolver(root).load(design_key)

    def test_each_design_profile_declares_and_automatically_resolves_word_by_word(self):
        controller = RunController()
        for component in ProfileComponent:
            main_key = ProfileKey.for_component(
                component,
                "instagram",
                family="design",
                profile_id=(
                    f"{component.value}_instagram_design_"
                    "modo_conciencia_studio_1"
                ),
            )
            with self.subTest(component=component.value):
                self.assertEqual(
                    "word_by_word",
                    self.profile_resolver.declared_subtitle_style(main_key),
                )
                self.assertEqual(
                    "word_by_word",
                    controller._select_profile_subtitle_config(main_key),
                )
                subtitle = self.subtitle_resolver.load(
                    SubtitleProfileKey.for_profile(main_key, "word_by_word")
                )
                self.assertEqual(main_key.profile_id, subtitle.key.parent_profile_id)

    def test_system_keeps_the_generic_subtitle_style_selector(self):
        controller = RunController()
        messages = []
        controller._print = messages.append
        controller._select_from_list = lambda items: "single_line"

        style = controller._select_profile_subtitle_config(
            ProfileKey.for_component("video", "instagram")
        )

        self.assertEqual("single_line", style)
        self.assertTrue(any("SUBT" in message for message in messages))

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
                style="invalid style",
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

    def test_runtime_effective_behavior_matches_resolved_profiles(self):
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
            expected_profile = self._load(
                self._expected_path(component, platform, style)
            )
            expected_cue = expected_profile["cue_policy"]
            expected_render = expected_profile["render_style"]
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

            self.assertEqual(expected_cue, resolved.cue_policy)
            self.assertEqual(expected_render, resolved.render_style)
            self.assertEqual(
                SubtitleConfigLoader().load_render_style(
                    expected_render
                ),
                video_config.subtitles
            )
            self.assertEqual(
                style_builder.build(expected_render),
                style_builder.build(video_config.subtitle_style)
            )
            self._assert_model_equivalent(
                optimizer.model,
                style,
                expected_cue,
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

    def test_design_has_no_profile_tree_and_video_srt_remains_unimplemented(self):
        self.assertFalse(Path("config/profiles/diseno").exists())
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
