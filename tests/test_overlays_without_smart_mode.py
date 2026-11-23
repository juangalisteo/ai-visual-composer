"""The overlays only have the Sí/No mode of the menu (I5b, N4).

The «smart» mode (the AI chose the overlay folders, with the folder names
written in the code) could not be chosen from the menu and was removed with
its code. No overlay folder name is written in the code: the folders are the
user's (``assets/videos/overlays/<folder>/``).
"""

import importlib.util
import random
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from app.modules.video.config.overlay_config import OverlayConfig
from app.modules.video.overlays.overlay_builder import OverlayBuilder
from app.modules.video.video_build_context_factory import (
    VideoBuildContextFactory,
)


APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def _overlays(directory, **changes):
    config = OverlayConfig(
        enabled=True,
        directory=str(directory),
        folder_selection="random",
        file_selection="random",
        avoid_repeats=True,
        repeat_mode="scene",
        min_seconds=6.0,
        max_seconds=12.0,
        loop_file=True,
        opacity=0.15,
        blend_mode="screen",
        probability=1.0,
        folders=(),
        types=(),
        extensions=(".mov", ".mp4"),
        folder_weights={},
        file_weights={},
    )
    return replace(config, **changes)


@dataclass(frozen=True)
class _VideoConfig:
    overlays: OverlayConfig


def test_the_smart_resolver_module_is_gone():
    assert importlib.util.find_spec(
        "app.modules.video.overlays.overlay_folder_resolver"
    ) is None


@pytest.mark.parametrize("name", ["Light Leaks", "Electricity"])
def test_no_overlay_folder_name_is_written_in_the_code(name):
    found = [
        path.relative_to(APP_ROOT).as_posix()
        for path in APP_ROOT.rglob("*.py")
        if name in path.read_text(encoding="utf-8")
    ]

    assert found == []


@pytest.mark.parametrize("mode", ["smart", "SMART", "test_unknown_mode"])
def test_a_mode_other_than_yes_or_no_keeps_the_profile_overlays(mode):
    for enabled in (True, False):
        config = _VideoConfig(_overlays("test_overlays", enabled=enabled))

        result = VideoBuildContextFactory(
            overlays_mode=mode,
        )._apply_overlay_mode(config)

        assert result is config


@pytest.mark.parametrize(("mode", "enabled"), [("on", True), (" Off ", False)])
def test_yes_and_no_only_switch_the_stage(mode, enabled):
    overlays = _overlays(
        "test_overlays",
        enabled=not enabled,
        folders=("test_family_a",),
        repeat_mode="interval",
        folder_selection="sequence",
    )

    result = VideoBuildContextFactory(
        overlays_mode=mode,
    )._apply_overlay_mode(_VideoConfig(overlays))

    assert result.overlays == replace(overlays, enabled=enabled)


def _write_family(root, name, count):
    folder = root / name
    folder.mkdir(parents=True)
    for index in range(1, count + 1):
        (folder / f"{name}_{index}.mp4").write_bytes(b"test")


def _selections(root, scene_metadata):
    random.seed(20261121)
    builder = OverlayBuilder(_overlays(root))
    builder.reset()
    return [
        builder.build(
            scene_index=index,
            scene_count=6,
            scene_metadata=scene_metadata(index),
        )["overlay_path"]
        for index in range(6)
    ]


def test_the_scene_text_does_not_choose_the_overlay(tmp_path):
    _write_family(tmp_path, "test_family_a", 2)
    _write_family(tmp_path, "test_family_b", 2)

    without_text = _selections(tmp_path, lambda index: {})
    with_text = _selections(
        tmp_path,
        lambda index: {
            "visible_subject": "electric sparks and lightning",
            "key_objects": ["rayo", "chispa"],
        },
    )

    assert with_text == without_text
    assert {Path(overlay).parent.name for overlay in without_text} == {
        "test_family_a",
        "test_family_b",
    }
