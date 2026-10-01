import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.controllers.run_controller import RunController
from app.core import start
from app.shared.profile_identity import ProfileComponent, ProfileKey
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


def test_generic_selector_discovers_independent_complete_keys_for_components(
    tmp_path,
):
    for component in (
        ProfileComponent.GUION,
        ProfileComponent.IMAGEN,
        ProfileComponent.VIDEO,
    ):
        operational_key = _write_operational_profile(
            tmp_path,
            component,
            profile_id="test_profile",
            display_name="Human operational label",
        )
        subtitle_key = _write_subtitle_profile(
            tmp_path,
            component,
            profile_id="test_subtitle_profile",
            family="test_subtitle_family",
            display_name="Human subtitle label",
        )
        controller = _controller(tmp_path)

        with (
            patch.object(
                ProfileKey,
                "for_component",
                side_effect=AssertionError("La ruta moderna no usa for_component."),
            ),
            patch("builtins.input", side_effect=("1", "1", "1")),
            patch("builtins.print"),
        ):
            selected = controller._select_profile_identity(component)

        assert selected["profile_key"] == operational_key
        assert selected["path"] == _resolver(tmp_path).resolve(operational_key)
        assert selected["subtitle_profile_key"] == subtitle_key
        assert selected["profile_key"].family == "test_family"
        assert selected["subtitle_profile_key"].family == "test_subtitle_family"
        assert selected["profile_key"].profile_id == "test_profile"
        assert selected["subtitle_profile_key"].profile_id == "test_subtitle_profile"


def test_generic_selector_uses_the_explicit_operational_choice_not_display_name(
    tmp_path,
):
    first_key = _write_operational_profile(
        tmp_path,
        ProfileComponent.GUION,
        profile_id="test_profile_first",
        display_name="Z human label",
    )
    _write_operational_profile(
        tmp_path,
        ProfileComponent.GUION,
        profile_id="test_profile_second",
        display_name="A human label",
    )
    _write_subtitle_profile(
        tmp_path,
        ProfileComponent.GUION,
        profile_id="test_subtitle_profile",
        family="test_subtitle_family",
        display_name="Subtitle label",
    )
    controller = _controller(tmp_path)

    with (
        patch.object(
            ProfileKey,
            "for_component",
            side_effect=AssertionError("La ruta moderna no usa for_component."),
        ),
        patch("builtins.input", side_effect=("1", "2", "1", "1")),
        patch("builtins.print"),
    ):
        selected = controller._select_profile_identity(ProfileComponent.GUION)

    assert selected["profile_key"] == first_key
    assert selected["profile_key"].profile_id == "test_profile_first"


def test_guion_video_bridge_requires_exactly_one_discovered_video_key(tmp_path):
    expected = _write_operational_profile(
        tmp_path,
        ProfileComponent.VIDEO,
        profile_id="test_profile",
        display_name="Technical video profile",
    )

    with patch.object(
        ProfileKey,
        "for_component",
        side_effect=AssertionError("El bridge no fabrica identidad VIDEO."),
    ):
        resolved = start._resolve_single_video_operational_key(
            _resolver(tmp_path),
            "test_platform",
        )

    assert resolved == expected


def test_guion_video_bridge_rejects_missing_video_candidate(tmp_path):
    with pytest.raises(FileNotFoundError, match="perfil operacional VIDEO"):
        start._resolve_single_video_operational_key(
            _resolver(tmp_path),
            "test_platform",
        )


def test_guion_video_bridge_rejects_ambiguous_video_candidates(tmp_path):
    _write_operational_profile(
        tmp_path,
        ProfileComponent.VIDEO,
        profile_id="test_profile_one",
        display_name="One",
    )
    _write_operational_profile(
        tmp_path,
        ProfileComponent.VIDEO,
        profile_id="test_profile_two",
        display_name="Two",
    )

    with pytest.raises(ValueError, match="ambigua"):
        start._resolve_single_video_operational_key(
            _resolver(tmp_path),
            "test_platform",
        )


def _controller(root):
    return RunController(
        profile_resolver=_resolver(root),
        subtitle_profile_resolver=SubtitleProfileResolver(root),
    )


def _resolver(root):
    return ProfileResolver(root)


def _write_operational_profile(root, component, profile_id, display_name):
    key = ProfileKey(
        component,
        "test_platform",
        profile_id,
        "test_family",
    )
    path = (
        Path(root)
        / key.component.value
        / key.platform
        / key.family
        / f"{key.profile_id}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "component": key.component.value,
                "platform": key.platform,
                "family": key.family,
                "profile_id": key.profile_id,
                "display_name": display_name,
            }
        ),
        encoding="utf-8",
    )
    return key


def _write_subtitle_profile(root, component, profile_id, family, display_name):
    source = Path(
        "config/profiles/guion/instagram/estandar/subtitulos/"
        "subtitulo_guion_instagram_linea_unica.json"
    )
    data = json.loads(source.read_text(encoding="utf-8"))
    data.update(
        {
            "component": component.value,
            "platform": "test_platform",
            "family": family,
            "profile_id": profile_id,
            "display_name": display_name,
        }
    )
    key = SubtitleProfileKey(
        component,
        "test_platform",
        profile_id,
        family,
    )
    path = (
        Path(root)
        / key.component.value
        / key.platform
        / key.family
        / "subtitulos"
        / f"{key.profile_id}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return key
