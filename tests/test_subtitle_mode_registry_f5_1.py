from types import SimpleNamespace
import json
from pathlib import Path

import pytest

from app.modules.subtitles.modes.registry import CueModelRegistry
from app.modules.subtitles.modes.single_line import SingleLineModel
from app.modules.subtitles.modes.word_by_word import WordByWordModel
from app.modules.subtitles.pipeline.cue_transformer import SubtitleCueTransformer
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


class _FakeCueModel:
    def __init__(self, cue_policy):
        self.cue_policy = cue_policy

    def optimize(self, blocks, timing=None):
        del timing
        return blocks


def test_registry_is_the_single_dispatch_for_builtin_modes():
    registry = CueModelRegistry()

    assert registry.resolve("single_line") is SingleLineModel
    assert registry.resolve("word_by_word") is WordByWordModel
    assert CueModelRegistry.mode_from({"mode": " WORD_BY_WORD "}) == "word_by_word"
    with pytest.raises(ValueError, match="Capacidad de cues no soportada"):
        registry.resolve("test_mode_inexistente")


def test_registry_extension_requires_one_factory_registration():
    profile = SimpleNamespace(
        cue_policy={"mode": "test_mode", "uppercase": False},
    )
    transformer = SubtitleCueTransformer(
        profile,
        30,
        model_registry=CueModelRegistry({"test_mode": _FakeCueModel}),
    )

    assert transformer.mode == "test_mode"
    assert isinstance(transformer.model, _FakeCueModel)


def test_two_profiles_can_share_one_mode_without_sharing_identity():
    resolver = SubtitleProfileResolver()
    first = resolver.discover_profiles_for_family(
        "studio", "instagram", "estandar",
    )[0]
    design = resolver.discover_profiles_for_family(
        "studio", "instagram", "design",
    )[0]

    first_profile = resolver.load(first.key)
    design_profile = resolver.load(design.key)

    assert first.key != design.key
    assert first.key.profile_id != design.key.profile_id
    standard_word = next(
        descriptor
        for descriptor in resolver.discover_profiles_for_family(
            "studio", "instagram", "estandar",
        )
        if descriptor.mode == "word_by_word"
    )
    standard_profile = resolver.load(standard_word.key)

    assert standard_word.key != design.key
    assert standard_profile.cue_policy["mode"] == design_profile.cue_policy["mode"]


def test_new_profile_with_existing_mode_is_discovered_without_style_field(tmp_path):
    source = (
        Path("config/profiles/studio/instagram/estandar/subtitulos/")
        / "subtitulo_studio_instagram_linea_unica.json"
    )
    data = json.loads(source.read_text(encoding="utf-8"))
    data.update(
        component="studio",
        platform="test_platform",
        family="test_family",
        profile_id="test_profile",
        display_name="Technical profile",
    )
    target = (
        tmp_path / "studio/test_platform/test_family/subtitulos/test_profile.json"
    )
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(data), encoding="utf-8")

    second_data = dict(data)
    second_data.update(
        profile_id="another_test_profile",
        display_name="Another human label",
    )
    second_target = target.with_name("another_test_profile.json")
    second_target.write_text(json.dumps(second_data), encoding="utf-8")

    resolver = SubtitleProfileResolver(tmp_path)
    descriptors = resolver.discover_profiles_for_family(
        "studio", "test_platform", "test_family",
    )
    descriptor = next(
        item for item in descriptors if item.key.profile_id == "test_profile"
    )
    second_descriptor = next(
        item
        for item in descriptors
        if item.key.profile_id == "another_test_profile"
    )

    assert descriptor.key.profile_id == "test_profile"
    assert descriptor.mode == "single_line"
    assert second_descriptor.mode == descriptor.mode
    assert second_descriptor.key != descriptor.key
    assert CueModelRegistry().resolve(second_descriptor.mode) is CueModelRegistry().resolve(
        descriptor.mode
    )
    assert "style" not in data
