import pytest

from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.modules.video.subtitles.ass_subtitle_builder import (
    SubtitleRenderBackend,
    SubtitleRenderBackendResolver,
)


STYLE = {
    "font": "unisans",
    "font_size": 14,
    "bold": True,
    "primary_colour": "&H00FFFFFF",
    "outline_colour": "&H80000000",
    "back_colour": "&H00000000",
    "border_style": 1,
    "outline": 1,
    "shadow": 1,
    "alignment": 2,
    "margin_v": 55,
    "offset": 0.0,
    "dynamic": True,
}
STATIC_STYLE = {key: value for key, value in STYLE.items() if key != "dynamic"}


def test_effect_absence_preserves_static_or_explicit_dynamic_phase4_contract():
    static = SubtitleConfigLoader().load_render_style(STATIC_STYLE)
    dynamic_without_effect = SubtitleConfigLoader().load_render_style(STYLE)

    assert static.cue_effect is None
    assert SubtitleRenderBackendResolver().resolve(static) is SubtitleRenderBackend.STATIC
    assert dynamic_without_effect.cue_effect is None
    assert SubtitleRenderBackendResolver().resolve(dynamic_without_effect) is SubtitleRenderBackend.DYNAMIC


@pytest.mark.parametrize(
    "effect",
    (
        {"cue_effect": "gravity_drop"},
        {"word_effect": "highlight_in_sentence"},
    ),
)
def test_effect_requires_explicit_dynamic_render_style(effect):
    with pytest.raises(ValueError, match="requiere render_style.dynamic=true"):
        SubtitleConfigLoader().load_render_style(STATIC_STYLE | effect)


@pytest.mark.parametrize(
    "retired",
    (
        {"effects": {"fade": {"enabled": True, "in_ms": 100, "out_ms": 100}}},
        {"effects": {"fade": {"enabled": False}}},
        {"effects": {}},
        {"word_effects": {"karaoke": {"enabled": True}}},
        {"word_effects": {}},
        {"cue_effect": "gravity_drop", "effects": {}},
    ),
)
def test_retired_structured_effect_keys_fail_with_clear_message(retired):
    with pytest.raises(ValueError, match="claves antiguas effects/word_effects") as captured:
        SubtitleConfigLoader().load_render_style(
            STYLE | retired,
            profile_path="config/profiles/test_profile.json",
        )

    assert "Use cue_effect o word_effect" in str(captured.value)
    assert "test_profile.json" in str(captured.value)
