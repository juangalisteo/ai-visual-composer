from app.shared.profile_identity import ProfileComponent
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


VISUAL_BASE = {
    "font": "unisans",
    "font_size": 10,
    "bold": False,
    "primary_colour": "&H00FFFFFF",
    "outline_colour": "&H80000000",
    "back_colour": "&H00000000",
    "border_style": 1,
    "outline": 0,
    "shadow": 1,
    "alignment": 2,
    "margin_v": 55,
    "offset": 0.0,
}


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
