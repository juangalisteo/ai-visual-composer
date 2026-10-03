import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.controllers.run_controller import RunController
from app.modules.subtitles.modes.single_line import (
    SingleLineModel,
)
from app.modules.subtitles.modes.word_by_word import (
    WordByWordModel,
)
from app.modules.subtitles.pipeline.srt_optimizer import SrtOptimizer
from app.modules.video.config.loaders.subtitle_loader import (
    SubtitleConfigLoader,
)
from app.modules.video.subtitles.subtitle_style_builder import (
    SubtitleStyleBuilder,
)
from app.modules.video.video_config import VideoConfigLoader
from app.shared.config_manager import ConfigManager
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
    ProfileKey,
)
from app.shared.profile_resolver import ProfileResolver
from app.shared.operational_error import OperationalError
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
    PLATFORMS = ("instagram", "youtube")
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

    def test_design_subtitle_profile_is_autonomous(self):
        for component in ProfileComponent:
            main_key = ProfileKey.for_component(
                component,
                "instagram",
                family="design",
                profile_id=(
                    f"{component.value}_instagram_design_"
                    "modo_conciencia_reels"
                ),
            )
            descriptors = self.subtitle_resolver.discover_profiles_for_family(
                component, "instagram", "design",
            )
            for descriptor in descriptors:
                with self.subTest(component=component.value, mode=descriptor.mode):
                    key = descriptor.key
                    resolved = self.subtitle_resolver.load(key)
                    self.assertEqual("design", resolved.key.family)
                    self.assertEqual(
                        Path("config/profiles")
                        / component.value
                        / "instagram"
                        / "design"
                        / "subtitulos"
                        / f"{key.profile_id}.json",
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
                            ConfigManager().get_subtitle_profile(key.profile_id).path,
                        )

    def test_design_subtitles_do_not_fallback_to_system(self):
        main_key = ProfileKey.for_component(
            "studio",
            "instagram",
            family="design",
            profile_id="studio_instagram_design_modo_conciencia_reels",
        )
        design_key = SubtitleProfileKey(
            "studio", "instagram", "modo_conciencia_reels", "design",
        )
        system_source = self._expected_path(
            ProfileComponent.VIDEO,
            "instagram",
            SubtitleStyle.SINGLE_LINE,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profiles"
            system_path = root / "studio/instagram/estandar/subtitulos/subtitulo_studio_instagram_linea_unica.json"
            system_path.parent.mkdir(parents=True)
            system_path.write_text(system_source.read_text(encoding="utf-8"), encoding="utf-8")

            with self.assertRaises(OperationalError) as caught:
                SubtitleProfileResolver(root).load(design_key)

        self.assertEqual("PROFILE", caught.exception.context.family)
        self.assertIsInstance(caught.exception.__cause__, FileNotFoundError)

    def test_each_design_profile_resolves_word_by_word_from_its_own_contract(self):
        for component in ProfileComponent:
            main_key = ProfileKey.for_component(
                component,
                "instagram",
                family="design",
                profile_id=(
                    f"{component.value}_instagram_design_"
                    "modo_conciencia_reels"
                ),
            )
            with self.subTest(component=component.value):
                descriptor = self.subtitle_resolver.discover_profiles_for_family(
                    component, "instagram", "design",
                )[0]
                subtitle = self.subtitle_resolver.load(descriptor.key)
                self.assertEqual("word_by_word", subtitle.cue_policy["mode"])

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

    def test_rejects_invalid_component_platform_and_profile_id(self):
        with self.assertRaisesRegex(ValueError, "Componente"):
            SubtitleProfileKey(
                component="design",
                platform="instagram",
                profile_id="invalid",
                family="estandar",
            )

        with self.assertRaisesRegex(ValueError, "Plataforma"):
            SubtitleProfileKey(
                component="video",
                platform="instagram reels",
                profile_id="invalid",
                family="estandar",
            )

        with self.assertRaisesRegex(ValueError, "profile_id"):
            SubtitleProfileKey(
                component="video",
                platform="instagram",
                profile_id="invalid profile",
                family="estandar",
            )

    def test_accepts_opaque_subtitle_profile_id(self):
        key = SubtitleProfileKey(
            component="video",
            platform="instagram",
            profile_id="test_profile",
            family="estandar",
        )

        self.assertEqual("test_profile", key.profile_id)

    def test_missing_official_profile_is_explicit_without_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profiles"
            alternatives = (
                (
                    ProfileComponent.VIDEO,
                    "youtube",
                ),
                (
                    ProfileComponent.IMAGEN,
                    "instagram",
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

            with self.assertRaises(OperationalError) as caught:
                resolver.load(instagram_key)

        self.assertEqual("PROFILE", caught.exception.context.family)
        self.assertIsInstance(caught.exception.__cause__, FileNotFoundError)

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
                "instagram",
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
                    SubtitleStyle.WORD_BY_WORD,
                )
            )
            data["component"] = "video"
            path.write_text(
                json.dumps(data),
                encoding="utf-8"
            )

            with self.assertRaises(OperationalError) as caught:
                SubtitleProfileResolver(root).load(key)

        self.assertEqual("PROFILE", caught.exception.context.family)
        self.assertIsInstance(caught.exception.__cause__, ValueError)

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
                    "instagram",
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
                platform=platform,
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
                        self._expected_path(component, platform, style).stem
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
            main_profile = self.profile_resolver.load_operational(
                OperationalProfileKey(
                    component,
                    platform,
                    f"{component.value}_{platform}",
                )
            )
            expected_profile = self._load(
                self._expected_path(component, platform, style)
            )
            expected_cue = expected_profile["cue_policy"]
            expected_render = expected_profile["render_style"]
            fps = main_profile["video_style"]["fps"]

            with self.subTest(
                component=component.value,
                platform=platform,
                style=style.value
            ), patch.dict(os.environ, environment, clear=True):
                resolved = ConfigManager().get_subtitle_profile(
                    self._expected_path(component, platform, style).stem
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
            with self.assertRaises(OperationalError) as caught:
                ConfigManager().get_subtitle_profile(
                    "word_by_word"
                )

        self.assertEqual("CONFIG", caught.exception.context.family)

    def test_video_config_uses_injected_resolved_render_style(self):
        environment = self._environment(
            ProfileComponent.VIDEO,
            "youtube"
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
                "youtube",
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
            "MC_PROFILE_PLATFORM": platform,
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
