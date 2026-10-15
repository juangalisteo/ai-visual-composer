from app.modules.subtitles.modes.cumulative_line import CumulativeLineModel
from app.modules.subtitles.modes.registry import CueModelRegistry
from app.modules.subtitles.policies.timing import (
    SpeechSegment,
    SubtitleTiming,
    WordTiming,
)
from app.modules.video.subtitles.subtitle_style_builder import SubtitleStyleBuilder
from app.shared.profile_identity import ProfileComponent
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


PUNCTUATION = {
    "remove_commas": False, "remove_periods": False,
    "remove_colons": False, "remove_semicolons": False,
    "remove_question_marks": False, "remove_exclamation_marks": False,
    "remove_ellipsis": False, "remove_hyphens": False,
    "remove_em_dashes": False, "remove_double_quotes": False,
    "remove_single_quotes": False, "remove_parentheses": False,
}


def _config(**changes):
    config = {
        "mode": "cumulative_line",
        "max_chars_per_line": 60,
        "min_duration": 0.8,
        "max_duration": 5.0,
        "significant_gap_threshold": 0.35,
        "punctuation": PUNCTUATION,
    }
    config.update(changes)
    return config


def _timing(*words):
    return SubtitleTiming(
        source="tts",
        segments=(
            SpeechSegment(start=words[0].start, end=words[-1].end, words=words),
        ),
    )


def _texts(blocks):
    return [block.splitlines()[2] for block in blocks]


def test_registry_resolves_cumulative_line_once():
    assert CueModelRegistry().resolve("cumulative_line") is CumulativeLineModel


def test_cumulative_line_adds_each_word_and_clears_after_a_pause():
    timing = _timing(
        WordTiming("uno", 0.0, 0.1),
        WordTiming("dos", 0.2, 0.3),
        WordTiming("tres", 0.4, 0.5),
        WordTiming("cuatro", 1.0, 1.1),
        WordTiming("cinco", 1.2, 1.3),
    )

    blocks = CumulativeLineModel(_config()).optimize([], timing=timing)

    assert _texts(blocks) == [
        "uno", "uno dos", "uno dos tres", "cuatro", "cuatro cinco",
    ]
    assert "00:00:00,000 --> 00:00:00,500" in blocks[0]
    assert "00:00:00,400 --> 00:00:00,500" in blocks[2]
    assert "00:00:01,000 --> 00:00:01,300" in blocks[3]


def test_cumulative_line_restarts_when_the_semantic_line_reaches_its_limit():
    timing = _timing(
        WordTiming("aa", 0.0, 0.1),
        WordTiming("bb", 0.11, 0.2),
        WordTiming("cc", 0.21, 0.3),
        WordTiming("dd", 0.31, 0.4),
    )

    blocks = CumulativeLineModel(_config(max_chars_per_line=8)).optimize(
        [], timing=timing
    )

    assert _texts(blocks) == ["aa", "aa bb", "cc", "cc dd"]
    assert all(len(text) <= 8 for text in _texts(blocks))


def test_instagram_minimalista_cumulative_profiles_resolve_declaratively():
    resolver = SubtitleProfileResolver()

    for component in ProfileComponent:
        key = SubtitleProfileKey(
            component=component,
            platform="instagram",
            family="minimalista",
            profile_id=(
                f"subtitulo_{component.value}_instagram_cumulative_line"
            ),
        )
        profile = resolver.load(key)

        assert profile.display_name == "Palabra por palabra"
        assert profile.cue_policy["mode"] == "cumulative_line"
        assert profile.render_style["alignment"] == 2


def test_studio_cumulative_uses_static_scale_defaults_without_force_style_overrides():
    profile = SubtitleProfileResolver().load(
        SubtitleProfileKey(
            component=ProfileComponent.STUDIO,
            platform="instagram",
            family="minimalista",
            profile_id="subtitulo_studio_instagram_cumulative_line",
        )
    )

    force_style = SubtitleStyleBuilder().build(profile.render_style)

    assert "ScaleX=" not in force_style
    assert "ScaleY=" not in force_style
