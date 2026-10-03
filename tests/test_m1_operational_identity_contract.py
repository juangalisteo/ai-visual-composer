import json
from pathlib import Path

from app.core.start import _resolve_single_video_operational_key
from app.modules.studio.profile import StudioProfileLoader
from app.shared.profile_identity import OperationalProfileKey, ProfileKey
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
    standard = ProfileKey(
        "guion", "instagram", "guion_instagram", "estandar",
    )
    design_context = ProfileKey(
        "guion", "instagram", "guion_instagram", "design",
    )

    assert _canonical_operational_identity(standard) == (
        "guion", "instagram", "guion_instagram",
    )
    assert _canonical_operational_identity(design_context) == (
        "guion", "instagram", "guion_instagram",
    )
    # The different legacy route context remains observable until M2/M5.
    assert standard.family != design_context.family


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
        "config/profiles/guion/instagram/estandar/subtitulos/"
        "subtitulo_guion_instagram_linea_unica.json"
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
    operational_key = ProfileKey(
        "studio", "instagram", "studio_instagram", "estandar",
    )
    subtitle_key = SubtitleProfileKey(
        "studio", "instagram", "modo_conciencia_reels", "design",
    )

    resolved = SubtitleProfileResolver().load(subtitle_key)

    assert _canonical_operational_identity(operational_key) == (
        "studio", "instagram", "studio_instagram",
    )
    assert subtitle_key.family == "design"
    assert resolved.key == subtitle_key


def test_m1_studio_baseline_uses_general_operational_payload():
    key = OperationalProfileKey("studio", "instagram", "studio_instagram")
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
        "instagram",
    )

    assert _canonical_operational_identity(key) == (
        "video", "instagram", "video_instagram",
    )


def test_m1_wan_i2v_remains_outside_operational_profile_contract():
    video_key = OperationalProfileKey("video", "instagram", "video_instagram")
    document = ProfileResolver().load_video_component(video_key)

    assert document["platform"] == "video"
    assert "video_component" in document
    assert "component" not in document
    assert "family" not in document
    assert "profile_id" not in document
