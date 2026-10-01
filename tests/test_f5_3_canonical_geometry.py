from copy import deepcopy

from app.modules.images.image_builder import ImageBuilder
from app.modules.studio.profile import StudioProfileLoader
from app.modules.video.video_config import VideoConfigLoader
from app.shared.profile_identity import ProfileComponent, ProfileKey
from app.shared.profile_resolver import ProfileResolver


class _ProfileConfigManager:
    def __init__(self, profile):
        self._profile = profile

    def get_profile_config(self):
        return self._profile


def _video_config(profile):
    return VideoConfigLoader(
        subtitle_profile=None,
        config_manager=_ProfileConfigManager(profile),
    ).load(render_subtitles=False)


def test_guion_imagen_and_video_use_video_style_dimensions_without_resolution():
    resolver = ProfileResolver()
    expected_dimensions = {
        "instagram": (1080, 1920),
        "youtube": (1920, 1080),
    }

    for component in (
        ProfileComponent.GUION,
        ProfileComponent.IMAGEN,
        ProfileComponent.VIDEO,
    ):
        for platform, dimensions in expected_dimensions.items():
            key = ProfileKey.for_component(component, platform)
            profile = resolver.load(key)

            assert "resolution" not in profile
            assert (profile["video_style"]["width"], profile["video_style"]["height"]) == dimensions
            assert (_video_config(profile).width, _video_config(profile).height) == dimensions


def test_legacy_resolution_and_format_do_not_determine_runtime_pixels():
    resolver = ProfileResolver()
    profile = resolver.load(ProfileKey.for_component("imagen", "instagram"))
    variant = deepcopy(profile)
    variant["resolution"] = "1x1"
    variant["format"] = "horizontal"

    assert (_video_config(variant).width, _video_config(variant).height) == (1080, 1920)
    assert ImageBuilder.__new__(ImageBuilder)._get_image_dimensions(variant) == (1080, 1920)


def test_studio_output_dimensions_are_the_only_geometry_authority():
    resolver = ProfileResolver()
    expected_dimensions = {
        "instagram": (1080, 1920),
        "youtube": (1920, 1080),
    }

    for platform, dimensions in expected_dimensions.items():
        key = ProfileKey.for_component("studio", platform)
        profile = resolver.load(key)
        variant = deepcopy(profile)
        variant["resolution"] = "1x1"
        variant["format"] = "horizontal" if platform == "instagram" else "vertical"

        loaded = StudioProfileLoader().load(variant, key)

        assert "resolution" not in profile
        assert (loaded.width, loaded.height) == dimensions
        assert not hasattr(loaded, "resolution")
