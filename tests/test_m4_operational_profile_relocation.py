import json
from pathlib import Path

from app.shared.profile_identity import OperationalProfileKey
from app.shared.profile_resolver import ProfileResolver


EXPECTED = {
    ("guion", "vertical"): "guion_vertical",
    ("guion", "horizontal"): "guion_horizontal",
    ("imagen", "vertical"): "imagen_vertical",
    ("imagen", "horizontal"): "imagen_horizontal",
    ("video", "vertical"): "video_vertical",
    ("video", "horizontal"): "video_horizontal",
    ("studio", "vertical"): "studio_vertical",
    ("studio", "horizontal"): "studio_horizontal",
}


def test_m4_operational_profiles_have_one_root_authority_without_family():
    resolver = ProfileResolver()
    actual_paths = set()

    for (component, platform), profile_id in EXPECTED.items():
        key = OperationalProfileKey(component, platform, profile_id)
        expected_path = Path(
            "config/profiles",
            component,
            platform,
            f"perfil_{component}_{platform}.json",
        )
        payload = json.loads(expected_path.read_text(encoding="utf-8"))
        descriptors = resolver.discover_operational_profiles(component, platform)

        assert payload["component"] == component
        assert payload["platform"] == platform
        assert payload["profile_id"] == profile_id
        assert "family" not in payload
        assert resolver.resolve_operational(key) == expected_path
        assert [descriptor.key for descriptor in descriptors] == [key]
        assert not hasattr(resolver, "discover")
        assert not (
            Path("config/profiles", component, platform, "estandar")
            / expected_path.name
        ).exists()
        actual_paths.add(expected_path)

    assert len(actual_paths) == 8
