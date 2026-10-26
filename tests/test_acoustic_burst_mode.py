from app.modules.subtitles.modes.acoustic_burst import AcousticBurstModel
from app.modules.subtitles.modes.registry import CueModelRegistry
from app.modules.subtitles.policies.timing import (
    SpeechSegment,
    SubtitleTiming,
    WordTiming,
)
from app.shared.profile_identity import ProfileComponent
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


PUNCTUATION = {
    "remove_commas": False,
    "remove_periods": False,
    "remove_colons": False,
    "remove_semicolons": False,
    "remove_question_marks": False,
    "remove_exclamation_marks": False,
    "remove_ellipsis": False,
    "remove_hyphens": False,
    "remove_em_dashes": False,
    "remove_double_quotes": False,
    "remove_single_quotes": False,
    "remove_parentheses": False,
}


def _config(**changes):
    config = {
        "mode": "acoustic_burst",
        "significant_gap_threshold": 0.4,
        "hard_max_chars": 80,
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


def _cue_texts(blocks):
    return [block.splitlines()[2] for block in blocks]


def test_registry_resolves_acoustic_burst_once():
    assert CueModelRegistry().resolve("acoustic_burst") is AcousticBurstModel


def test_acoustic_burst_splits_only_on_the_canonical_gap_threshold():
    timing = _timing(
        WordTiming("uno,", 0.0, 0.1),
        WordTiming("dos", 0.11, 0.2),
        WordTiming("tres.", 0.61, 0.7),
        WordTiming("cuatro", 0.71, 0.8),
    )

    blocks = AcousticBurstModel(_config()).optimize([], timing=timing)

    assert _cue_texts(blocks) == ["uno, dos", "tres. cuatro"]


def test_acoustic_burst_uses_hard_max_chars_only_as_a_safety_limit():
    timing = _timing(
        WordTiming("aa", 0.0, 0.1),
        WordTiming("bb", 0.11, 0.2),
        WordTiming("cc", 0.21, 0.3),
        WordTiming("dd", 0.31, 0.4),
    )

    blocks = AcousticBurstModel(_config(hard_max_chars=8)).optimize(
        [], timing=timing
    )

    assert _cue_texts(blocks) == ["aa bb cc", "dd"]
    assert all(len(text) <= 8 for text in _cue_texts(blocks))


def test_acoustic_burst_preserves_real_word_timing_boundaries():
    timing = _timing(
        WordTiming("uno", 0.0, 0.15),
        WordTiming("dos", 0.16, 0.3),
        WordTiming("tres", 0.75, 0.9),
    )

    blocks = AcousticBurstModel(_config()).optimize([], timing=timing)

    assert "00:00:00,000 --> 00:00:00,300" in blocks[0]
    assert "00:00:00,750 --> 00:00:00,900" in blocks[1]


def test_vertical_minimalista_profiles_resolve_declaratively():
    resolver = SubtitleProfileResolver()

    for component in ProfileComponent:
        profile_id = f"subtitulo_{component.value}_vertical_acoustic_burst"
        key = SubtitleProfileKey(
            component=component,
            format="vertical",
            family="minimalista",
            profile_id=profile_id,
        )

        descriptor = next(
            item
            for item in resolver.discover_profiles_for_family(
                component, "vertical", "minimalista"
            )
            if item.key == key
        )
        profile = resolver.load(key)

        assert descriptor.mode == "acoustic_burst"
        assert profile.cue_policy["significant_gap_threshold"] == 0.4
        assert profile.cue_policy["hard_max_chars"] == 28
        assert "pause_split_threshold" not in profile.cue_policy
