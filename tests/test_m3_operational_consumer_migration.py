from unittest.mock import patch

from app.controllers.run_controller import RunController
from app.core.start import _resolve_single_video_operational_key
from app.modules.studio.profile import StudioProfileLoader
from app.shared.config_manager import ConfigManager
from app.shared.profile_identity import OperationalProfileKey, ProfileComponent
from app.shared.profile_resolver import (
    OperationalProfileDescriptor,
    ProfileResolver,
)


class _OperationalResolver:
    def __init__(self, key):
        self.key = key

    def discover_platforms(self, component):
        assert component is self.key.component
        return (self.key.platform,)

    def discover_operational_profiles(self, component, platform):
        assert component is self.key.component
        assert platform == self.key.platform
        return (
            OperationalProfileDescriptor(
                key=self.key,
                path=None,
                display_name="Technical operational profile",
            ),
        )

    def resolve_operational(self, key):
        assert key == self.key
        return "test_operational_profile.json"


def test_m3_config_manager_loads_operational_profile_without_subtitle_family():
    resolver = ProfileResolver()
    manager = ConfigManager(profile_resolver=resolver)
    key = OperationalProfileKey("guion", "instagram", "guion_instagram")

    with patch.dict(
        "os.environ",
        {
            "MC_PROFILE_COMPONENT": "guion",
            "MC_PROFILE_PLATFORM": "instagram",
            "MC_PROFILE_ID": "guion_instagram",
            # A legacy subtitle-family value cannot alter operational loading.
            "MC_PROFILE_FAMILY": "design",
        },
        clear=False,
    ):
        assert manager.get_operational_profile_key() == key
        assert manager.get_profile_config() == resolver.load_operational(key)


def test_m3_run_controller_selects_operational_key_without_family():
    key = OperationalProfileKey("imagen", "test_platform", "test_profile")
    controller = RunController(profile_resolver=_OperationalResolver(key))
    controller._select_from_list = lambda values: tuple(values)[0]
    controller._print = lambda _message: None

    selected = controller._select_profile_identity(
        ProfileComponent.IMAGEN,
        select_subtitles=False,
    )

    assert selected == {
        "path": "test_operational_profile.json",
        "profile_key": key,
    }
    assert not hasattr(selected["profile_key"], "family")


def test_m3_studio_loader_and_guion_video_bridge_transport_operational_keys():
    resolver = ProfileResolver()
    studio_key = OperationalProfileKey("studio", "instagram", "studio_instagram")
    studio = StudioProfileLoader().load(
        resolver.load_operational(studio_key),
        studio_key,
    )
    video_key = _resolve_single_video_operational_key(resolver, "instagram")

    assert studio.profile_id == studio_key.profile_id
    assert video_key == OperationalProfileKey(
        "video",
        "instagram",
        "video_instagram",
    )


def test_m3_wan_loader_remains_dedicated_but_accepts_operational_identity():
    document = ProfileResolver().load_video_component(
        OperationalProfileKey("video", "instagram", "video_instagram"),
    )

    assert document["platform"] == "video"
    assert "video_component" in document
