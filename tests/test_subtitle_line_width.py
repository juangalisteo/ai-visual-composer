"""Every subtitle profile's widest possible line fits its frame (F5, H7).

Width is measured as libass draws it. libass sizes a font so that the OS/2
``usWinAscent + usWinDescent`` equals the ASS font size, not the em square
that PIL uses. PIL at ``size * unitsPerEm / (usWinAscent + usWinDescent)``
therefore reproduces libass without FFmpeg (checked in F5 against a real
FFmpeg 8 render of the four bundled fonts: within 1 %, STATIC and DYNAMIC
alike).
"""

import json
from pathlib import Path

import pytest
from PIL import ImageFont

from app.managers.font_manager import FontManager
from app.modules.subtitles.rendering.font_metrics import em_per_win_height
from app.modules.subtitles.policies.text_case import TextCasePolicy
from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.modules.video.subtitles.ass_subtitle_builder import (
    SubtitleRenderBackend,
    SubtitleRenderBackendResolver,
)
from app.modules.video.subtitles.ass_visual_scale import AssVisualScaleNormalizer


PROFILES_ROOT = Path("config/profiles")
MAX_WIDTH_RATIO = 0.90
# libavcodec's default style for SRT: MarginL/MarginR 10 on the 384x288 grid.
STATIC_DEFAULT_MARGIN = 10
# AssSubtitleBuilder's default MarginL/MarginR, in output pixels.
DYNAMIC_DEFAULT_MARGIN = 20

# Neutral Spanish text with long words; no word is longer than 20 characters.
CORPUS = (
    "Desafortunadamente, la responsabilidad individual comprende "
    "transformaciones extraordinariamente profundas. Imagina cuidadosamente "
    "cómo reaccionarías: ¿permanecerías tranquilo o buscarías explicaciones "
    "inmediatamente? Nuestras experiencias cotidianas, aparentemente "
    "insignificantes, construyen identidades complejísimas y "
    "contradictorias. Comprenderlo requiere paciencia, constancia y "
    "muchísima generosidad con nosotros mismos. Mañana, quizás, "
    "descubriremos que la tranquilidad también se aprende: respirando "
    "despacio, escuchando atentamente y agradeciendo cada momento "
    "compartido con quienes nos acompañan en este camino."
).split()


def _subtitle_profiles():
    return sorted(PROFILES_ROOT.glob("*/*/*/subtitulos/*.json"))


def _frame_size(component, profile_format):
    sizes = set()
    for path in (PROFILES_ROOT / component / profile_format).glob("*.json"):
        profile = json.loads(path.read_text(encoding="utf-8"))
        for section in (
            profile.get("video_style"),
            profile.get("studio", {}).get("output"),
        ):
            if section and "width" in section and "height" in section:
                sizes.add((section["width"], section["height"]))
    assert len(sizes) == 1, (component, profile_format, sizes)
    return sizes.pop()


def _libass_font(font_name, ass_size):
    path = FontManager().resolve_path(font_name)
    return ImageFont.truetype(str(path), ass_size * em_per_win_height(str(path)))


def _runs(max_chars=None, max_words=None, exact_words=None):
    """Every run of consecutive words the mode may put on one line."""
    for start in range(len(CORPUS)):
        for end in range(start + 1, len(CORPUS) + 1):
            count = end - start
            if max_words is not None and count > max_words:
                break
            text = " ".join(CORPUS[start:end])
            if max_chars is not None and len(text) > max_chars:
                break
            if exact_words is None or count == exact_words:
                yield text
            if exact_words is not None and count >= exact_words:
                break


def _candidate_lines(cue_policy):
    mode = cue_policy["mode"]
    if mode == "word_by_word":
        return _runs(max_words=1)
    if mode == "acoustic_burst":
        return _runs(max_chars=cue_policy["hard_max_chars"])
    if mode == "three_two_words":
        return _runs(
            max_chars=cue_policy["max_chars_per_line"],
            max_words=cue_policy.get("fixed_chunk_size") or 3,
        )
    if mode == "rolling_window":
        return _runs(
            max_chars=cue_policy["max_chars_per_line"],
            max_words=cue_policy["window_size"],
        )
    if mode in ("single_line", "two_lines", "cumulative_line", "roll_up"):
        return _runs(max_chars=cue_policy["max_chars_per_line"])
    raise AssertionError(f"Modo sin regla de ancho: {mode}")


def _effect_extra(style, font, line):
    effect = style.word_effect
    if effect is None:
        return 0.0
    if effect.name == "pop_in_sentence":
        widest = max(font.getlength(word) for word in line.split())
        return widest * (effect.parameters["word_pop_scale"] / 100 - 1)
    if effect.name == "active_pill":
        return 2 * effect.parameters["pill_padding"]
    if effect.name == "typewriter" and effect.parameters["typewriter_cursor"]:
        return font.getlength(effect.parameters["cursor_char"])
    return 0.0


def _widest_line(path):
    profile = json.loads(path.read_text(encoding="utf-8"))
    width, height = _frame_size(profile["component"], profile["format"])
    style = SubtitleConfigLoader().load_render_style(profile["render_style"])
    if SubtitleRenderBackendResolver().resolve(style) is SubtitleRenderBackend.DYNAMIC:
        style = AssVisualScaleNormalizer().normalize(style, width, height)
        font = _libass_font(style.font, style.font_size)
        margins = sum(
            DYNAMIC_DEFAULT_MARGIN if margin is None else margin
            for margin in (style.margin_l, style.margin_r)
        )
    else:
        font = _libass_font(style.font, style.font_size * height / 288)
        margins = sum(
            (STATIC_DEFAULT_MARGIN if margin is None else margin) * width / 384
            for margin in (style.margin_l, style.margin_r)
        )
    case = TextCasePolicy.from_cue_policy(profile["cue_policy"]).mode
    widest = (0.0, "")
    for line in _candidate_lines(profile["cue_policy"]):
        if case == "uppercase":
            line = line.upper()
        elif case == "lowercase":
            line = line.lower()
        line_width = font.getlength(line) + _effect_extra(style, font, line)
        widest = max(widest, (line_width, line))
    return widest, width - margins


@pytest.mark.parametrize(
    "path",
    _subtitle_profiles(),
    ids=lambda path: path.as_posix(),
)
def test_widest_line_fits_ninety_percent_of_the_usable_width(path):
    (line_width, line), usable_width = _widest_line(path)

    assert line_width <= MAX_WIDTH_RATIO * usable_width, (
        f"{line_width:.0f} px de {usable_width:.0f} px útiles "
        f"({100 * line_width / usable_width:.1f} %): «{line}»"
    )
