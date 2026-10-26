from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.controllers.interaction.intro_outro_selection import IntroOutroSelector
from app.controllers.interaction.resource_selection import ResourceSelection
from app.controllers.interaction.terminal import Terminal
from app.controllers.run_controller import RunController


def _selector(catalog, answers, messages, on_cancel=None):
    terminal = Terminal(
        reader=lambda prompt: next(answers),
        writer=messages.append,
    )
    return IntroOutroSelector(
        terminal,
        on_cancel or (lambda: pytest.fail("No debe cancelar")),
        catalog,
        ResourceSelection(terminal, on_cancel or (lambda: pytest.fail("No debe cancelar")), Mock()),
    )


def test_intro_outro_keeps_menu_order_assets_and_original_paths():
    intro_first = Path("assets/vertical/intro/a.mp4")
    intro_second = Path("assets/vertical/intro/b.mp4")
    outro = Path("assets/vertical/outro/c.mp4")
    catalog = Mock()
    catalog.discover.side_effect = lambda platform, position: {
        "intro": (intro_first, intro_second),
        "outro": (outro,),
    }[position]
    messages = []

    plan = _selector(catalog, iter(("4", "2", "1")), messages) \
        .select_intro_outro("vertical")

    assert plan.intro.asset_path == intro_second
    assert plan.intro.position == "intro"
    assert plan.outro.asset_path == outro
    assert plan.outro.position == "outro"
    assert messages == [
        "\nINTRO / OUTRO\n",
        "1. NINGUNO",
        "2. SOLO INTRO",
        "3. SOLO OUTRO",
        "4. INTRO + OUTRO",
        "\nSELECCIONAR INTRO\n",
        "1. a.mp4",
        "2. b.mp4",
        "\nSELECCIONAR OUTRO\n",
        "1. c.mp4",
    ]
    assert catalog.discover.call_args_list == [
        (("vertical", "intro"),),
        (("vertical", "outro"),),
    ]


def test_intro_outro_none_skips_discovery_and_returns_none():
    catalog = Mock()
    messages = []

    assert _selector(catalog, iter(("1",)), messages).select_intro_outro(
        "vertical"
    ) is None
    catalog.discover.assert_not_called()
    assert messages == [
        "\nINTRO / OUTRO\n",
        "1. NINGUNO",
        "2. SOLO INTRO",
        "3. SOLO OUTRO",
        "4. INTRO + OUTRO",
    ]


def test_intro_outro_keeps_the_existing_missing_assets_error():
    catalog = Mock()
    catalog.discover.return_value = ()

    with pytest.raises(
        FileNotFoundError,
        match="No hay archivos MP4 disponibles para INTRO.*vertical/intro/",
    ):
        _selector(catalog, iter(("2",)), []).select_intro_outro("vertical")


def test_studio_adapter_derives_the_platform_from_profile_key():
    intro = Path("assets/horizontal/intro/a.mp4")
    catalog = Mock()
    catalog.discover.return_value = (intro,)

    plan = _selector(catalog, iter(("2", "1")), []).select_studio_intro_outro(
        SimpleNamespace(platform="horizontal")
    )

    assert plan.intro.asset_path == intro
    catalog.discover.assert_called_once_with("horizontal", "intro")


def test_intro_outro_keeps_the_terminal_cancellation_callback():
    calls = []

    def cancel():
        calls.append("cancel")
        raise RuntimeError("cancelled")

    with pytest.raises(RuntimeError, match="cancelled"):
        _selector(Mock(), iter(("0",)), [], cancel).select_intro_outro(
            "vertical"
        )
    assert calls == ["cancel"]


def test_run_controller_delegates_all_phase_four_responsibilities():
    interaction = Mock()
    plan = Mock()
    asset = Path("assets/vertical/intro/a.mp4")
    interaction.select_intro_outro.return_value = plan
    interaction.select_studio_intro_outro.return_value = plan
    interaction.require_assets.return_value = (asset,)
    interaction.select_asset.return_value = asset
    controller = RunController(intro_outro_selection=interaction)
    writer = Mock()
    selector = Mock()
    controller._print = writer
    controller._select_from_list = selector
    profile_key = SimpleNamespace(platform="vertical")

    assert controller.select_intro_outro("vertical") is plan
    assert controller.select_studio_intro_outro(profile_key) is plan
    assert controller._require_intro_outro_assets("vertical", "intro") == (asset,)
    assert controller._select_intro_outro_asset((asset,), "INTRO") is asset

    common = {"writer": writer, "selector": selector}
    interaction.select_intro_outro.assert_called_once_with("vertical", **common)
    interaction.select_studio_intro_outro.assert_called_once_with(
        profile_key,
        **common,
    )
    interaction.require_assets.assert_called_once_with("vertical", "intro")
    interaction.select_asset.assert_called_once_with(
        (asset,),
        "INTRO",
        **common,
    )
