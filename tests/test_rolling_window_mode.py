import pytest

from app.modules.subtitles.modes.registry import CueModelRegistry
from app.modules.subtitles.modes.rolling_window import RollingWindowModel
from app.modules.subtitles.policies.timing import (
    SpeechSegment,
    SubtitleTiming,
    WordTiming,
)
from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.shared.profile_identity import ProfileComponent
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


PUNCTUATION = {
    "remove_commas": True, "remove_periods": True,
    "remove_colons": True, "remove_semicolons": True,
    "remove_question_marks": False, "remove_exclamation_marks": False,
    "remove_ellipsis": True, "remove_hyphens": True,
    "remove_em_dashes": True, "remove_double_quotes": True,
    "remove_single_quotes": True, "remove_parentheses": True,
}


def _config(**changes):
    config = {
        "mode": "rolling_window",
        "min_duration": 0.2,
        "max_duration": 2.0,
        "significant_gap_threshold": 0.35,
        "window_size": 5,
        "punctuation": PUNCTUATION,
    }
    config.update(changes)
    return config


def _timing(*words):
    return SubtitleTiming(
        source="test",
        segments=(
            SpeechSegment(start=words[0].start, end=words[-1].end, words=words),
        ),
    )


def _texts(blocks):
    return [block.splitlines()[2] for block in blocks]


def test_registry_resolves_rolling_window_once():
    assert CueModelRegistry().resolve("rolling_window") is RollingWindowModel


def test_rolling_window_emits_fifo_windows_at_their_exact_overlapping_word_ranges():
    timing = _timing(
        WordTiming("uno", 0.0, 0.1),
        WordTiming("dos", 0.1, 0.2),
        WordTiming("tres", 0.2, 0.3),
        WordTiming("cuatro", 0.3, 0.4),
        WordTiming("cinco", 0.4, 0.5),
        WordTiming("seis", 0.5, 0.6),
    )

    blocks = RollingWindowModel(_config(window_size=3)).optimize([], timing=timing)

    assert _texts(blocks) == [
        "uno dos tres",
        "dos tres cuatro",
        "tres cuatro cinco",
        "cuatro cinco seis",
    ]
    assert "00:00:00,000 --> 00:00:00,300" in blocks[0]
    assert "00:00:00,100 --> 00:00:00,400" in blocks[1]
    assert "00:00:00,300 --> 00:00:00,600" in blocks[3]


def test_rolling_window_restarts_after_a_significant_pause_without_crossing_it():
    timing = _timing(
        WordTiming("uno", 0.0, 0.1),
        WordTiming("dos", 0.1, 0.2),
        WordTiming("tres", 0.2, 0.3),
        WordTiming("cuatro", 0.8, 0.9),
        WordTiming("cinco", 0.9, 1.0),
        WordTiming("seis", 1.0, 1.1),
    )

    blocks = RollingWindowModel(_config(window_size=3)).optimize([], timing=timing)

    assert _texts(blocks) == ["uno dos tres", "cuatro cinco seis"]
    assert "00:00:00,000 --> 00:00:00,300" in blocks[0]
    assert "00:00:00,800 --> 00:00:01,100" in blocks[1]


def test_rolling_window_requires_a_complete_fixed_window_and_preserves_fallback_timing():
    model = RollingWindowModel(_config(window_size=3))

    assert model.optimize([
        "1\n00:00:00,000 --> 00:00:00,600\nuno dos tres cuatro cinco"
    ]) == [
        "1\n00:00:00,000 --> 00:00:00,360\nuno dos tres",
        "2\n00:00:00,120 --> 00:00:00,480\ndos tres cuatro",
        "3\n00:00:00,240 --> 00:00:00,600\ntres cuatro cinco",
    ]
    assert RollingWindowModel(_config(window_size=5)).optimize([
        "1\n00:00:00,000 --> 00:00:00,400\nuno dos tres cuatro"
    ]) == []


@pytest.mark.parametrize(
    "changes, message",
    (
        ({"window_size": 1}, "window_size"),
        ({"significant_gap_threshold": 0}, "significant_gap_threshold"),
        ({"min_duration": 3.0, "max_duration": 2.0}, "max_duration"),
    ),
)
def test_rolling_window_validates_its_declared_limits(changes, message):
    with pytest.raises(ValueError, match=message):
        RollingWindowModel(_config(**changes))


def test_instagram_karaoke_rolling_window_profiles_resolve_declaratively():
    resolver = SubtitleProfileResolver()

    for component in ProfileComponent:
        key = SubtitleProfileKey(
            component=component,
            platform="instagram",
            family="karaoke",
            profile_id=f"subtitulo_{component.value}_instagram_rolling_window",
        )
        descriptors = resolver.discover_profiles_for_family(
            component,
            "instagram",
            "karaoke",
        )
        profile = resolver.load(key)
        render_style = SubtitleConfigLoader().load_render_style(profile.render_style)

        assert any(descriptor.key == key for descriptor in descriptors)
        assert profile.display_name == "Ventana deslizante"
        assert profile.cue_policy["mode"] == "rolling_window"
        assert profile.cue_policy["window_size"] == 5
        assert render_style.dynamic is False
        assert render_style.cue_effect is None
        assert render_style.word_effect is None
        assert profile.render_style == {
            "font": "unisans", "font_size": 10, "bold": False,
            "italic": False, "underline": False, "strikeout": False,
            "primary_colour": "&H00FFFFFF", "secondary_colour": "&H00000000",
            "outline_colour": "&H80000000", "back_colour": "&H00000000",
            "border_style": 1, "outline": 0, "shadow": 1, "alignment": 2,
            "margin_v": 55, "margin_l": 0, "margin_r": 0, "spacing": 0.0,
            "offset": 0.0, "dynamic": False, "cue_effect": "none",
            "word_effect": "none",
        }
