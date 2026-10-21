import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
)
from app.shared.profile_resolver import ProfileResolver
from app.shared.operational_error import OperationalError
from app.shared.subtitle_profile_identity import (
    SubtitleProfileKey,
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
    STYLES = ("single_line", "word_by_word")
    PROFILE_IDS = {
        (ProfileComponent.GUION, "instagram", "single_line"):
            "subtitulo_guion_instagram_linea_unica",
        (ProfileComponent.GUION, "instagram", "word_by_word"):
            "subtitulo_guion_instagram_palabra_por_palabra",
        (ProfileComponent.GUION, "youtube", "single_line"):
            "subtitulo_guion_youtube_linea_unica",
        (ProfileComponent.GUION, "youtube", "word_by_word"):
            "subtitulo_guion_youtube_palabra_por_palabra",
        (ProfileComponent.IMAGEN, "instagram", "single_line"):
            "subtitulo_imagen_instagram_linea_unica",
        (ProfileComponent.IMAGEN, "instagram", "word_by_word"):
            "subtitulo_imagen_instagram_palabra_por_palabra",
        (ProfileComponent.IMAGEN, "youtube", "single_line"):
            "subtitulo_imagen_youtube_linea_unica",
        (ProfileComponent.IMAGEN, "youtube", "word_by_word"):
            "subtitulo_imagen_youtube_palabra_por_palabra",
        (ProfileComponent.VIDEO, "instagram", "single_line"):
            "subtitulo_video_instagram_linea_unica",
        (ProfileComponent.VIDEO, "instagram", "word_by_word"):
            "subtitulo_video_instagram_palabra_por_palabra",
        (ProfileComponent.VIDEO, "youtube", "single_line"):
            "subtitulo_video_youtube_linea_unica",
        (ProfileComponent.VIDEO, "youtube", "word_by_word"):
            "subtitulo_video_youtube_palabra_por_palabra",
    }

    def setUp(self):
        self.profile_resolver = ProfileResolver()
        self.subtitle_resolver = SubtitleProfileResolver()

    def test_resolves_exact_twelve_profile_matrix(self):
        resolved_paths = set()
        profile_ids = set()

        for component, platform, style in self._cases():
            key = self._key(component, platform, style)
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
                    self.assertEqual(
                        resolved.path,
                        ConfigManager().get_subtitle_profile_by_key(key).path,
                    )

    def test_design_subtitles_do_not_fallback_to_system(self):
        design_key = SubtitleProfileKey(
            "studio", "instagram", "modo_conciencia_reels", "design",
        )
        system_source = self._expected_path(
            ProfileComponent.VIDEO,
            "instagram",
            "single_line",
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

    def test_each_design_profile_resolves_its_declared_mode_from_its_own_contract(self):
        for component in ProfileComponent:
            descriptors = self.subtitle_resolver.discover_profiles_for_family(
                component, "instagram", "design",
            )
            self.assertTrue(descriptors)
            for descriptor in descriptors:
                with self.subTest(
                    component=component.value,
                    profile_id=descriptor.key.profile_id,
                ):
                    subtitle = self.subtitle_resolver.load(descriptor.key)
                    self.assertEqual(descriptor.key, subtitle.key)
                    self.assertEqual(component, subtitle.key.component)
                    self.assertEqual("design", subtitle.key.family)
                    self.assertEqual(descriptor.mode, subtitle.cue_policy["mode"])

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
                alternative_key = self._key(component, platform, "single_line")
                alternative_path = root / alternative_key.relative_path
                alternative_path.parent.mkdir(parents=True)
                alternative_path.write_text(
                    self._expected_path(
                        component,
                        platform,
                        "single_line"
                    ).read_text(encoding="utf-8"),
                    encoding="utf-8"
                )

            instagram_key = self._key(
                ProfileComponent.VIDEO, "instagram", "single_line"
            )
            resolver = SubtitleProfileResolver(root)

            with self.assertRaises(OperationalError) as caught:
                resolver.load(instagram_key)

        self.assertEqual("PROFILE", caught.exception.context.family)
        self.assertIsInstance(caught.exception.__cause__, FileNotFoundError)

    def test_loaded_profiles_do_not_share_mutable_configuration(self):
        key = self._key(ProfileComponent.VIDEO, "instagram", "word_by_word")
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
                "word_by_word"
            ))["cue_policy"],
            second.cue_policy
        )

    def test_rejects_internal_identity_that_disagrees_with_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profiles"
            key = self._key(ProfileComponent.IMAGEN, "instagram", "word_by_word")
            path = root / key.relative_path
            path.parent.mkdir(parents=True)
            data = self._load(
                self._expected_path(
                    key.component,
                    key.platform,
                    "word_by_word",
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

    def test_official_config_manager_never_loads_legacy_subtitle_json(self):
        for component, platform, style in self._cases():
            environment = self._environment(
                component,
                platform
            )
            with self.subTest(
                component=component.value,
                platform=platform,
                style=style
            ), patch.dict(os.environ, environment, clear=True):
                manager = ConfigManager()
                with patch.object(
                    manager,
                    "load_json",
                    side_effect=AssertionError(
                        "Official subtitles must not use legacy JSON"
                    )
                ):
                    resolved = manager.get_subtitle_profile_by_key(
                        self._key(component, platform, style)
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
                style=style
            ), patch.dict(os.environ, environment, clear=True):
                resolved = ConfigManager().get_subtitle_profile_by_key(
                    self._key(component, platform, style)
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

    def test_video_config_uses_injected_resolved_render_style(self):
        environment = self._environment(
            ProfileComponent.VIDEO,
            "youtube"
        )

        with patch.dict(os.environ, environment, clear=True):
            resolved = ConfigManager().get_subtitle_profile_by_key(
                self._key(
                    ProfileComponent.VIDEO,
                    "youtube",
                    "single_line"
                )
            )
            loaded = VideoConfigLoader(
                subtitle_profile=resolved
            ).load()

        expected = self._load(
            self._expected_path(
                ProfileComponent.VIDEO,
                "youtube",
                "single_line"
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
        return {
            "MC_PROFILE_COMPONENT": component.value,
            "MC_PROFILE_PLATFORM": platform,
            "MC_PROFILE_ID": f"{component.value}_{platform}",
        }

    def _key(
        self,
        component,
        platform,
        style
    ):
        return SubtitleProfileKey(
            component=component,
            platform=platform,
            profile_id=self.PROFILE_IDS[(component, platform, style)],
            family="estandar",
        )

    def _expected_path(
        self,
        component,
        platform,
        style
    ):
        key = self._key(component, platform, style)
        return Path("config/profiles") / key.relative_path

    def _assert_model_equivalent(
        self,
        model,
        style,
        cue_policy,
        fps
    ):
        if style == "single_line":
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
