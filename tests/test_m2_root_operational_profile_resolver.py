import json
from pathlib import Path

import pytest

from app.shared.operational_error import OperationalError
from app.shared.profile_identity import OperationalProfileKey
from app.shared.profile_resolver import ProfileResolver


def test_root_operational_profile_is_discovered_and_resolved_by_canonical_key(
    tmp_path,
):
    path = _write_root_profile(
        tmp_path,
        component="guion",
        profile_format="test_format",
        profile_id="test_profile",
        display_name="Human readable label",
    )
    resolver = ProfileResolver(tmp_path)

    descriptors = resolver.discover_operational_profiles(
        "guion",
        "test_format",
    )

    assert len(descriptors) == 1
    assert descriptors[0].key == OperationalProfileKey(
        "guion",
        "test_format",
        "test_profile",
    )
    assert descriptors[0].display_name == "Human readable label"
    assert descriptors[0].path == path
    assert resolver.resolve_operational(descriptors[0].key) == path


def test_root_operational_profile_does_not_require_a_family_field(tmp_path):
    _write_root_profile(
        tmp_path,
        component="imagen",
        profile_format="test_format",
        profile_id="test_profile",
    )

    descriptor = ProfileResolver(tmp_path).discover_operational_profiles(
        "imagen",
        "test_format",
    )[0]

    assert descriptor.key == OperationalProfileKey(
        "imagen",
        "test_format",
        "test_profile",
    )


def test_canonical_resolution_ignores_subtitle_family_documents(tmp_path):
    root_path = _write_root_profile(
        tmp_path,
        component="studio",
        profile_format="test_format",
        profile_id="test_profile",
    )
    _write_legacy_profile(
        tmp_path,
        component="studio",
        profile_format="test_format",
        family="test_family",
        profile_id="test_profile",
    )
    resolver = ProfileResolver(tmp_path)
    key = OperationalProfileKey("studio", "test_format", "test_profile")

    assert resolver.resolve_operational(key) == root_path


def test_duplicate_root_profiles_are_never_selected_by_filesystem_order(tmp_path):
    _write_root_profile(
        tmp_path,
        component="guion",
        profile_format="test_format",
        profile_id="test_profile",
        filename="a.json",
    )
    _write_root_profile(
        tmp_path,
        component="guion",
        profile_format="test_format",
        profile_id="test_profile",
        filename="z.json",
    )

    with pytest.raises(OperationalError) as captured:
        ProfileResolver(tmp_path).discover_operational_profiles(
            "guion",
            "test_format",
        )

    assert captured.value.context.family == "AMBIGUITY"
    assert isinstance(captured.value.__cause__, ValueError)


def test_root_technical_wan_document_is_not_an_operational_profile():
    descriptors = ProfileResolver().discover_operational_profiles(
        "video",
        "vertical",
    )

    assert tuple(descriptor.key.profile_id for descriptor in descriptors) == (
        "video_vertical",
    )


def _write_root_profile(
    root,
    component,
    profile_format,
    profile_id,
    display_name=None,
    filename=None,
):
    path = (
        Path(root)
        / component
        / profile_format
        / (filename or f"{profile_id}.json")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "component": component,
        "format": profile_format,
        "profile_id": profile_id,
    }
    if display_name is not None:
        payload["display_name"] = display_name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
def _write_legacy_profile(root, component, profile_format, family, profile_id):
    path = (
        Path(root)
        / component
        / profile_format
        / family
        / f"{profile_id}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "component": component,
                "format": profile_format,
                "family": family,
                "profile_id": profile_id,
            }
        ),
        encoding="utf-8",
    )
    return path


# Test helpers end here.
