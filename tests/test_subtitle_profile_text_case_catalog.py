import json
from pathlib import Path

from app.modules.subtitles.policies.text_case import VALID_TEXT_CASES
from app.shared.profile_identity import ProfileComponent
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


PROFILES_ROOT = Path("config/profiles")


def _subtitle_profile_paths():
    return tuple(sorted(
        path
        for path in PROFILES_ROOT.rglob("*.json")
        if "subtitulos" in path.parts
    ))


def test_current_subtitle_catalog_uses_only_text_case_contract():
    paths = _subtitle_profile_paths()

    assert paths
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        cue_policy = data["cue_policy"]

        assert "uppercase" not in cue_policy, path
        assert cue_policy["text_case"] in VALID_TEXT_CASES, path


def test_current_subtitle_catalog_remains_discoverable_and_resolvable():
    resolver = SubtitleProfileResolver(PROFILES_ROOT)
    paths = _subtitle_profile_paths()
    discovered_keys = set()

    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        key = SubtitleProfileKey(
            component=ProfileComponent(data["component"]),
            format=data["format"],
            family=data["family"],
            profile_id=data["profile_id"],
        )
        descriptors = resolver.discover_profiles_for_family(
            key.component, key.format, key.family,
        )

        assert key in {descriptor.key for descriptor in descriptors}
        assert resolver.load(key).path == path
        discovered_keys.add(key)

    assert len(discovered_keys) == len(paths)
