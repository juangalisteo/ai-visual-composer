from app.controllers.run_controller import RunController
from app.core.start import _resolve_single_video_operational_key
from app.modules.studio.profile import StudioProfileLoader
from app.shared.config_manager import ConfigManager
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
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


def test_config_manager_without_operational_key_returns_none():
    assert ConfigManager().get_operational_profile_key() is None


def test_explicit_operational_key_is_returned_as_the_same_object():
    resolver = ProfileResolver()
    explicit_key = OperationalProfileKey(
        "guion",
        "vertical",
        "guion_vertical",
    )

    manager = ConfigManager(
        profile_resolver=resolver,
        operational_profile_key=explicit_key,
    )

    assert manager.get_operational_profile_key() is explicit_key
    assert manager.get_profile_config() == resolver.load_operational(explicit_key)


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
    studio_key = OperationalProfileKey("studio", "vertical", "studio_vertical")
    studio = StudioProfileLoader().load(
        resolver.load_operational(studio_key),
        studio_key,
    )
    video_key = _resolve_single_video_operational_key(resolver, "vertical")

    assert studio.profile_id == studio_key.profile_id
    assert video_key == OperationalProfileKey(
        "video",
        "vertical",
        "video_vertical",
    )


def test_m3_wan_loader_remains_dedicated_but_accepts_operational_identity():
    key = OperationalProfileKey("video", "vertical", "video_vertical")
    document = ProfileResolver().load_video_component(
        key,
    )

    assert document["kind"] == "video_component"
    assert document["operational_profile_id"] == key.profile_id
    assert document["platform"] == key.platform
    assert "video_component" in document
