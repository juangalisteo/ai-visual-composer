import struct
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

from app.managers.font_manager import FontManager


@dataclass(frozen=True)
class WordBox:
    left: float
    top: float
    right: float
    bottom: float


@lru_cache(maxsize=None)
def em_per_win_height(font_path):
    """Return ``unitsPerEm / (usWinAscent + usWinDescent)`` of a font file.

    libass sizes a font so that the OS/2 ``usWinAscent + usWinDescent``
    equals the ASS font size, not the em square that PIL uses. PIL at
    ``size * em_per_win_height`` therefore measures text as libass draws it.
    """
    data = Path(font_path).read_bytes()
    tables = {}
    for index in range(struct.unpack(">H", data[4:6])[0]):
        record = data[12 + 16 * index:28 + 16 * index]
        tag, _, offset, _ = struct.unpack(">4sIII", record)
        tables[tag] = offset
    head, os2 = tables[b"head"], tables[b"OS/2"]
    units_per_em = struct.unpack(">H", data[head + 18:head + 20])[0]
    win_ascent, win_descent = struct.unpack(">HH", data[os2 + 74:os2 + 78])
    return units_per_em / (win_ascent + win_descent)


class FontMetricsEngine:
    """Resolves word bounding boxes in ASS script coordinates."""

    def __init__(self, font_manager=None):
        self.font_manager = font_manager or FontManager()

    def word_boxes(self, text, style, width, height):
        words = text.replace("\n", " ").split()
        if not words:
            return ()
        font_path = str(self.font_manager.resolve_path(style.font))
        font = ImageFont.truetype(font_path, style.font_size)
        # Widths as libass draws them; the line height keeps the em metrics.
        width_font = ImageFont.truetype(
            font_path,
            style.font_size * em_per_win_height(font_path),
        )
        scale_x = (style.scale_x if style.scale_x is not None else 100.0) / 100.0
        scale_y = (style.scale_y if style.scale_y is not None else 100.0) / 100.0
        spacing = style.spacing if style.spacing is not None else 0.0
        word_widths = tuple(
            self._text_width(width_font, word, scale_x, spacing)
            for word in words
        )
        space_width = self._text_width(width_font, " ", scale_x, spacing)
        text_width = sum(word_widths) + space_width * (len(words) - 1)
        ascent, descent = font.getmetrics()
        line_height = (ascent + descent) * scale_y
        x = self._line_left(style, width, text_width)
        y = self._line_top(style, height, line_height)
        boxes = []
        for word_width in word_widths:
            boxes.append(WordBox(x, y, x + word_width, y + line_height))
            x += word_width + space_width
        return tuple(boxes)

    def line_height(self, style):
        font = ImageFont.truetype(
            str(self.font_manager.resolve_path(style.font)),
            style.font_size,
        )
        scale_y = (style.scale_y if style.scale_y is not None else 100.0) / 100.0
        ascent, descent = font.getmetrics()
        return (ascent + descent) * scale_y

    @staticmethod
    def _text_width(font, text, scale_x, spacing):
        return font.getlength(text) * scale_x + max(0, len(text) - 1) * spacing

    @staticmethod
    def _line_left(style, width, text_width):
        column = (style.alignment - 1) % 3
        if column == 0:
            return style.margin_l if style.margin_l is not None else 20
        if column == 1:
            return (width - text_width) / 2
        margin = style.margin_r if style.margin_r is not None else 20
        return width - margin - text_width

    @staticmethod
    def _line_top(style, height, line_height):
        row = (style.alignment - 1) // 3
        if row == 0:
            return height - style.margin_v - line_height
        if row == 1:
            return (height - line_height) / 2
        return style.margin_v
