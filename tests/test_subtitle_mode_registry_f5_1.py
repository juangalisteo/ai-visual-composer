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
        cue_policy={"mode": "test_mode", "text_case": "original"},
    )
    transformer = SubtitleCueTransformer(
        profile,
        30,
        model_registry=CueModelRegistry({"test_mode": _FakeCueModel}),
    )

    assert transformer.mode == "test_mode"
    assert isinstance(transformer.model, _FakeCueModel)


def test_two_profiles_can_share_one_mode_without_sharing_identity(tmp_path):
    source = (
        Path("config/profiles/studio/vertical/estandar/subtitulos/")
        / "subtitulo_studio_vertical_linea_unica.json"
    )
    template = json.loads(source.read_text(encoding="utf-8"))
    template.update(
        component="studio",
        format="test_format",
        family="test_family",
    )
    template["cue_policy"] = dict(template["cue_policy"])
    template["cue_policy"]["mode"] = "word_by_word"

    profiles = (
        ("test_profile_alpha", "Fixture alpha"),
        ("test_profile_beta", "Fixture beta"),
    )
    for profile_id, display_name in profiles:
        data = dict(template)
        data.update(profile_id=profile_id, display_name=display_name)
        target = (
            tmp_path
            / "studio/test_format/test_family/subtitulos"
            / f"{profile_id}.json"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data), encoding="utf-8")

    resolver = SubtitleProfileResolver(tmp_path)
    descriptors = resolver.discover_profiles_for_family(
        "studio", "test_format", "test_family",
    )

    assert {descriptor.key.profile_id for descriptor in descriptors} == {
        profile_id for profile_id, _ in profiles
    }
    assert len({descriptor.key for descriptor in descriptors}) == 2
    assert {descriptor.mode for descriptor in descriptors} == {"word_by_word"}
    for descriptor in descriptors:
        resolved = resolver.load(descriptor.key)
        assert resolved.key == descriptor.key
        assert resolved.cue_policy["mode"] == descriptor.mode
        assert CueModelRegistry().resolve(descriptor.mode) is WordByWordModel


def test_new_profile_with_existing_mode_is_discovered_without_style_field(tmp_path):
    source = (
        Path("config/profiles/studio/vertical/estandar/subtitulos/")
        / "subtitulo_studio_vertical_linea_unica.json"
    )
    data = json.loads(source.read_text(encoding="utf-8"))
    data.update(
        component="studio",
        format="test_format",
        family="test_family",
        profile_id="test_profile",
        display_name="Technical profile",
    )
    target = (
        tmp_path / "studio/test_format/test_family/subtitulos/test_profile.json"
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
        "studio", "test_format", "test_family",
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
    assert descriptor.mode == data["cue_policy"]["mode"]
    assert second_descriptor.mode == descriptor.mode
    assert second_descriptor.key != descriptor.key
    assert CueModelRegistry().resolve(second_descriptor.mode) is CueModelRegistry().resolve(
        descriptor.mode
    )
    assert "style" not in data
