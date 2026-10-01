from types import SimpleNamespace

import pytest

from app.modules.subtitles.pipeline.cue_transformer import SubtitleCueTransformer
from app.modules.subtitles.policies.text_case import TextCasePolicy
from app.shared.profile_identity import ProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


SPANISH = chr(0xBF) + "Qu" + chr(0xE9) + " tal, Juan! Ni" + chr(0xF1) + "o u" + chr(0xF1) + "a."
SOURCE = "1\n00:00:00,000 --> 00:00:02,000\n" + SPANISH + "\n"
PUNCTUATION = {key: False for key in (
    "remove_commas", "remove_periods", "remove_colons", "remove_semicolons",
    "remove_question_marks", "remove_exclamation_marks", "remove_ellipsis",
    "remove_hyphens", "remove_em_dashes", "remove_double_quotes",
    "remove_single_quotes", "remove_parentheses",
)}


def _policy(mode, text_case=None, uppercase=None):
    policy = {"mode": mode, "min_duration": .3, "max_duration": 3.0,
              "significant_gap_threshold": .35, "punctuation": PUNCTUATION}
    if mode == "single_line":
        policy["max_chars_per_line"] = 120
    else:
        policy.update({"render_fps": 30, "micro_cues": {"enabled": True, "min_frames": 1,
                       "min_display_seconds": .05, "merge_preference": "next"}})
    if text_case is not None:
        policy["text_case"] = text_case
    if uppercase is not None:
        policy["uppercase"] = uppercase
    return policy


@pytest.mark.parametrize("style", ("single_line", "word_by_word"))
@pytest.mark.parametrize("text_case, expected", (
    ("original", SPANISH),
    ("uppercase", SPANISH.upper()),
    ("lowercase", SPANISH.lower()),
))
def test_text_case_is_common_to_models_and_preserves_timestamps(style, text_case, expected):
    output = SubtitleCueTransformer(SimpleNamespace(cue_policy=_policy(style, text_case)), 30).transform(SOURCE)
    rendered = " ".join(line for line in output.splitlines() if "-->" not in line and not line.isdigit())
    assert " ".join(expected.split()) == " ".join(rendered.split())
    assert "00:00:00,000 --> 00:00:02,000" in output if style == "single_line" else "00:00:00,000" in output


@pytest.mark.parametrize("style", ("single_line", "word_by_word"))
@pytest.mark.parametrize(
    "uppercase, expected",
    ((False, SPANISH), (True, SPANISH.upper())),
)
def test_uppercase_is_a_common_declarative_cue_policy_option(
    style, uppercase, expected,
):
    output = SubtitleCueTransformer(
        SimpleNamespace(cue_policy=_policy(style, uppercase=uppercase)), 30,
    ).transform(SOURCE)
    rendered = " ".join(
        line for line in output.splitlines()
        if "-->" not in line and not line.isdigit()
    )
    assert " ".join(expected.split()) == " ".join(rendered.split())


def test_legacy_and_explicit_contract_validation():
    assert TextCasePolicy.from_cue_policy({"uppercase": True}).mode == "uppercase"
    assert TextCasePolicy.from_cue_policy({"uppercase": False}).mode == "original"
    assert TextCasePolicy.from_cue_policy({}).mode == "original"
    assert TextCasePolicy.from_cue_policy({"text_case": "uppercase", "uppercase": True}).mode == "uppercase"
    with pytest.raises(ValueError, match="Valores permitidos"):
        TextCasePolicy.from_cue_policy({"text_case": "caps"})
    with pytest.raises(ValueError, match="contradictorios"):
        TextCasePolicy.from_cue_policy({"text_case": "lowercase", "uppercase": True})


def test_design_and_standard_profiles_use_the_common_policy_without_original_path():
    resolver = SubtitleProfileResolver()
    standard = resolver.load_selection(ProfileKey.for_component("guion", "instagram"), "subtitulo_guion_instagram_linea_unica")
    design_key = ProfileKey.for_component("studio", "instagram", family="design", profile_id="studio_instagram_design_modo_conciencia_reels")
    design = resolver.load_selection(design_key, "word_by_word")
    standard.cue_policy["text_case"] = "lowercase"
    standard.cue_policy.pop("uppercase")
    design.cue_policy["text_case"] = "uppercase"
    design.cue_policy.pop("uppercase")
    assert SPANISH.lower() in SubtitleCueTransformer(standard, 30).transform(SOURCE)
    assert SPANISH.upper().split()[0] in SubtitleCueTransformer(design, 30).transform(SOURCE)
