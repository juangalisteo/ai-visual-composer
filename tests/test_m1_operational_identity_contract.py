import json
from pathlib import Path

from app.core.start import _resolve_single_video_operational_key
from app.modules.studio.profile import StudioProfileLoader
from app.shared.profile_identity import OperationalProfileKey
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


def _canonical_operational_identity(profile_key):
    """M1 target contract: subtitle family is not operational identity."""
    return (
        profile_key.component.value,
        profile_key.platform,
        profile_key.profile_id,
    )


def test_m1_canonical_operational_identity_excludes_legacy_family():
    key = OperationalProfileKey("guion", "vertical", "guion_vertical")

    assert _canonical_operational_identity(key) == (
        "guion", "vertical", "guion_vertical",
    )
    assert not hasattr(key, "family")


def test_m1_root_operational_document_uses_canonical_discovery_only(tmp_path):
    path = (
        tmp_path / "guion" / "test_platform"
        / "perfil_guion_test_platform.json"
    )
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "component": "guion",
                "platform": "test_platform",
                "profile_id": "guion_test_platform",
                "display_name": "Technical test profile",
            }
        ),
        encoding="utf-8",
    )

    resolver = ProfileResolver(tmp_path)

    assert resolver.discover_operational_profiles("guion", "test_platform")[0].path == path
    assert not hasattr(resolver, "discover_families")


def test_m1_subtitle_only_family_requires_no_operational_dummy(tmp_path):
    source = Path(
        "config/profiles/guion/vertical/estandar/subtitulos/"
        "subtitulo_guion_vertical_linea_unica.json"
    )
    data = json.loads(source.read_text(encoding="utf-8"))
    data.update(
        {
            "component": "guion",
            "platform": "test_platform",
            "family": "test_family",
            "profile_id": "test_profile",
            "display_name": "Technical test subtitle",
        }
    )
    path = (
        tmp_path / "guion" / "test_platform" / "test_family"
        / "subtitulos" / "test_profile.json"
    )
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data), encoding="utf-8")

    resolver = SubtitleProfileResolver(tmp_path)

    assert resolver.discover_families("guion", "test_platform") == (
        "test_family",
    )
    descriptor = resolver.discover_profiles_for_family(
        "guion", "test_platform", "test_family",
    )[0]
    assert descriptor.key == SubtitleProfileKey(
        "guion", "test_platform", "test_profile", "test_family",
    )
    assert resolver.load(descriptor.key).path == path


def test_m1_subtitle_key_family_is_independent_of_operational_legacy_family():
    operational_key = OperationalProfileKey(
        "studio", "vertical", "studio_vertical",
    )
    subtitle_key = SubtitleProfileKey(
        "studio", "vertical", "modo_conciencia_reels", "design",
    )

    resolved = SubtitleProfileResolver().load(subtitle_key)

    assert _canonical_operational_identity(operational_key) == (
        "studio", "vertical", "studio_vertical",
    )
    assert subtitle_key.family == "design"
    assert resolved.key == subtitle_key


def test_m1_studio_baseline_uses_general_operational_payload():
    key = OperationalProfileKey("studio", "vertical", "studio_vertical")
    profile = ProfileResolver().load_operational(key)
    resolved = StudioProfileLoader().load(profile, key)

    assert resolved.width == 1080
    assert resolved.height == 1920
    assert resolved.fps == 30
    assert "cue_policy" not in profile
    assert "render_style" not in profile


def test_m1_guion_video_bridge_remains_explicit_and_unambiguous():
    key = _resolve_single_video_operational_key(
        ProfileResolver(),
        "vertical",
    )

    assert _canonical_operational_identity(key) == (
        "video", "vertical", "video_vertical",
    )


def test_m1_wan_i2v_remains_outside_operational_profile_contract():
    video_key = OperationalProfileKey("video", "vertical", "video_vertical")
    document = ProfileResolver().load_video_component(video_key)

    assert document["kind"] == "video_component"
    assert document["operational_profile_id"] == video_key.profile_id
    assert document["platform"] == video_key.platform
    assert "video_component" in document
    assert "component" not in document
    assert "family" not in document
    assert "profile_id" not in document
