import json

import pytest

from app.shared.config_manager import ConfigManager
from app.shared.profile_identity import OperationalProfileKey, ProfileKey
from app.shared.profile_resolver import ProfileResolver


def _write_operational_profile(root):
    path = root / "guion" / "test_platform" / "profile.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "component": "guion",
                "platform": "test_platform",
                "profile_id": "test_profile",
                "display_name": "Test profile",
            }
        ),
        encoding="utf-8",
    )
    return path


def test_operational_resolver_exposes_only_canonical_operational_apis(tmp_path):
    path = _write_operational_profile(tmp_path)
    resolver = ProfileResolver(tmp_path)
    key = OperationalProfileKey("guion", "test_platform", "test_profile")

    assert resolver.resolve_operational(key) == path
    assert resolver.load_operational(key)["profile_id"] == "test_profile"
    for legacy_api in ("resolve", "load", "discover", "discover_families"):
        assert not hasattr(resolver, legacy_api)


def test_operational_resolver_rejects_family_bearing_legacy_key(tmp_path):
    _write_operational_profile(tmp_path)

    with pytest.raises(TypeError, match="OperationalProfileKey"):
        ProfileResolver(tmp_path).resolve_operational(
            ProfileKey("guion", "test_platform", "test_profile", "test_family")
        )


def test_config_manager_exposes_no_family_bearing_profile_key_accessor():
    assert not hasattr(ConfigManager, "get_profile_key")


def test_wan_resolver_keeps_its_dedicated_contract_and_rejects_legacy_key():
    resolver = ProfileResolver()

    with pytest.raises(TypeError, match="OperationalProfileKey"):
        resolver.resolve_video_component(
            ProfileKey("video", "instagram", "video_instagram", "test_family")
        )
