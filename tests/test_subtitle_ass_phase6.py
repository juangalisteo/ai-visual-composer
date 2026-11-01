from app.modules.subtitles.modes.word_by_word import WordByWordModel


def test_existing_word_by_word_algorithm_remains_upstream_and_uses_its_own_timing():
    config = {
        "min_duration": 0.1, "max_duration": 2.0,
        "punctuation": {
            "remove_commas": False, "remove_periods": False,
            "remove_colons": False, "remove_semicolons": False,
            "remove_question_marks": False, "remove_exclamation_marks": False,
            "remove_ellipsis": False, "remove_hyphens": False,
            "remove_em_dashes": False, "remove_double_quotes": False,
            "remove_single_quotes": False, "remove_parentheses": False,
        },
        "significant_gap_threshold": 0.4, "render_fps": 30,
        "micro_cues": {"enabled": False, "min_frames": 1, "min_display_seconds": 0.05, "merge_preference": "next"},
    }
    rendered = WordByWordModel(config).optimize([
        "1\n00:00:00,000 --> 00:00:01,000\nuno dos"
    ])
    assert rendered == [
        "1\n00:00:00,000 --> 00:00:00,500\nuno",
        "2\n00:00:00,500 --> 00:00:01,000\ndos",
    ]
