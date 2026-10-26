"""Contratos puros e inmutables de interacción STUDIO (Fase 6)."""

import ast
import dataclasses
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.controllers.interaction import contracts
from app.controllers.interaction.contracts import (
    StudioOperationalSelection,
    StudioProfileSelection,
    StudioSubtitleSelection,
)
from app.modules.studio.profile import StudioProfile
from app.shared.profile_identity import OperationalProfileKey, ProfileComponent
from app.shared.subtitle_profile_identity import SubtitleProfileKey


def _operational_key():
    return OperationalProfileKey(
        component=ProfileComponent.STUDIO,
        platform="vertical",
        profile_id="studio_vertical",
    )


def _subtitle_key():
    return SubtitleProfileKey(
        component=ProfileComponent.STUDIO,
        platform="vertical",
        profile_id="subtitle_fixture",
        family="fixture_family",
    )


def _studio_profile():
    return Mock(spec=StudioProfile)


def test_studio_selection_contracts_transport_the_declared_domain_types():
    operational_key = _operational_key()
    studio_profile = _studio_profile()
    subtitle_key = _subtitle_key()

    operational = StudioOperationalSelection(operational_key, studio_profile)
    subtitle = StudioSubtitleSelection(subtitle_key, subtitle_original=True)
    selection = StudioProfileSelection(operational, subtitle)

    assert isinstance(operational.operational_key, OperationalProfileKey)
    assert isinstance(operational.studio_profile, StudioProfile)
    assert isinstance(subtitle.subtitle_key, SubtitleProfileKey)
    assert subtitle.subtitle_original is True
    assert selection.operational is operational
    assert selection.subtitle is subtitle


def test_studio_selection_contracts_are_frozen_and_have_deterministic_equality():
    operational_key = _operational_key()
    studio_profile = _studio_profile()
    subtitle_key = _subtitle_key()
    operational = StudioOperationalSelection(operational_key, studio_profile)
    subtitle = StudioSubtitleSelection(subtitle_key, subtitle_original=False)
    selection = StudioProfileSelection(operational, subtitle)

    assert operational == StudioOperationalSelection(operational_key, studio_profile)
    assert subtitle == StudioSubtitleSelection(subtitle_key, subtitle_original=False)
    assert selection == StudioProfileSelection(operational, subtitle)
    assert subtitle != StudioSubtitleSelection(subtitle_key, subtitle_original=True)

    with pytest.raises(dataclasses.FrozenInstanceError):
        operational.operational_key = _operational_key()
    with pytest.raises(dataclasses.FrozenInstanceError):
        subtitle.subtitle_original = True
    with pytest.raises(dataclasses.FrozenInstanceError):
        selection.subtitle = subtitle


def test_contracts_module_is_data_only_and_has_only_domain_type_dependencies():
    source_path = Path(contracts.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports = {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
    }

    assert imports == {
        "dataclasses",
        "app.modules.studio.profile",
        "app.shared.profile_identity",
        "app.shared.subtitle_profile_identity",
    }
    assert not [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert all(
        dataclasses.is_dataclass(contract)
        and contract.__dataclass_params__.frozen
        for contract in (
            StudioOperationalSelection,
            StudioSubtitleSelection,
            StudioProfileSelection,
        )
    )
