from app.shared.profile_identity import ProfileComponent
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


VISUAL_BASE = {
    "font": "unisans",
    "font_size": 10,
    "bold": False,
    "outline_colour": "&H80000000",
    "back_colour": "&H00000000",
    "border_style": 1,
    "outline": 0,
    "shadow": 1,
    "alignment": 2,
    "margin_v": 55,
    "offset": 0.0,
}


def _expected_primary_colour(render_style):
    return (
        "&H0000FFFF"
        if render_style.get("word_effect") == "highlight_in_sentence"
        else "&H00FFFFFF"
    )


def test_instagram_minimalista_profiles_share_the_declared_visual_base():
    resolver = SubtitleProfileResolver()

    for component in ProfileComponent:
        descriptors = resolver.discover_profiles_for_family(
            component,
            "instagram",
            "minimalista",
        )
        assert descriptors

        for descriptor in descriptors:
            profile = resolver.load(descriptor.key)
            actual_base = {
                field: profile.render_style.get(field)
                for field in VISUAL_BASE
            }

            assert actual_base == VISUAL_BASE, profile.path
            assert (
                profile.render_style.get("primary_colour")
                == _expected_primary_colour(profile.render_style)
            ), profile.path


def test_instagram_minimalista_and_karaoke_profiles_share_10_55_reference():
    resolver = SubtitleProfileResolver()

    for family in ("minimalista", "karaoke"):
        for component in ProfileComponent:
            descriptors = resolver.discover_profiles_for_family(
                component,
                "instagram",
                family,
            )
            assert descriptors

            for descriptor in descriptors:
                profile = resolver.load(descriptor.key)
                assert profile.render_style.get("font_size") == 10, profile.path
                assert profile.render_style.get("margin_v") == 55, profile.path

                if profile.render_style.get("word_effect") in {
                    "highlight_in_sentence",
                    "continuous_karaoke",
                }:
                    assert profile.render_style.get("primary_colour") == "&H0000FFFF"
                    assert profile.render_style.get("secondary_colour") == "&H00FFFFFF"
