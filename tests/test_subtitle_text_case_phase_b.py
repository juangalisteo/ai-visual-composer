from types import SimpleNamespace

import pytest

from app.modules.subtitles.pipeline.cue_transformer import SubtitleCueTransformer
from app.modules.subtitles.policies.text_case import TextCasePolicy
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


SPANISH = chr(0xBF) + "Qu" + chr(0xE9) + " tal, Juan! Ni" + chr(0xF1) + "o u" + chr(0xF1) + "a."
SOURCE = "1\n00:00:00,000 --> 00:00:02,000\n" + SPANISH + "\n"
PUNCTUATION = {key: False for key in (
    "remove_commas", "remove_periods", "remove_colons", "remove_semicolons",
    "remove_question_marks", "remove_exclamation_marks", "remove_ellipsis",
    "remove_hyphens", "remove_em_dashes", "remove_double_quotes",
    "remove_single_quotes", "remove_parentheses",
)}


def _policy(mode, text_case=None):
    policy = {"mode": mode, "min_duration": .3, "max_duration": 3.0,
              "significant_gap_threshold": .35, "punctuation": PUNCTUATION}
    if mode == "single_line":
        policy["max_chars_per_line"] = 120
    else:
        policy.update({"render_fps": 30, "micro_cues": {"enabled": True, "min_frames": 1,
                       "min_display_seconds": .05, "merge_preference": "next"}})
    if text_case is not None:
        policy["text_case"] = text_case
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


def test_text_case_contract_validation():
    assert TextCasePolicy.from_cue_policy({}).mode == "original"
    assert TextCasePolicy.from_cue_policy({"text_case": "uppercase"}).mode == "uppercase"
    assert TextCasePolicy.from_cue_policy({"text_case": "lowercase"}).mode == "lowercase"
    with pytest.raises(ValueError, match="Valores permitidos"):
        TextCasePolicy.from_cue_policy({"text_case": "caps"})


def test_design_and_standard_profiles_use_the_common_policy_without_original_path():
    resolver = SubtitleProfileResolver()
    standard = resolver.load(SubtitleProfileKey(
        component="guion",
        platform="instagram",
        family="estandar",
        profile_id="subtitulo_guion_instagram_linea_unica",
    ))
    design = resolver.load(SubtitleProfileKey(
        component="studio",
        platform="instagram",
        family="design",
        profile_id="modo_conciencia_reels",
    ))
    standard.cue_policy["text_case"] = "lowercase"
    design.cue_policy["text_case"] = "uppercase"
    standard_output = SubtitleCueTransformer(standard, 30).transform(SOURCE)
    standard_text = " ".join(
        line for line in standard_output.splitlines()
        if "-->" not in line and not line.isdigit()
    )
    assert SPANISH.lower() == " ".join(standard_text.split())
    assert SPANISH.upper().split()[0] in SubtitleCueTransformer(design, 30).transform(SOURCE)
