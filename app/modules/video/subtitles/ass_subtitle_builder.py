from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re
import tempfile

from app.managers.font_manager import FontManager


class SubtitleRenderBackend(str, Enum):
    STATIC = "STATIC"
    DYNAMIC = "DYNAMIC"


class SubtitleRenderBackendResolver:

    def resolve(self, render_style):
        return (
            SubtitleRenderBackend.DYNAMIC
            if render_style.dynamic
            else SubtitleRenderBackend.STATIC
        )


@dataclass(frozen=True)
class PreparedSubtitle:
    path: Path
    backend: SubtitleRenderBackend
    force_style: str | None
    temporary_path: Path | None = None

    def cleanup(self):
        if self.temporary_path is not None and self.temporary_path.exists():
            self.temporary_path.unlink()


class AssSubtitleBuilder:
    """Construye una representacion ASS temporal de cues SRT ya tratados."""

    _TIMESTAMP = re.compile(
        r"^(?P<hours>\d+):(?P<minutes>\d{2}):(?P<seconds>\d{2})[,.](?P<milliseconds>\d{3})$"
    )

    def __init__(self, font_manager=None):
        self.font_manager = font_manager or FontManager()

    def build_temporary(self, subtitle_path, render_style, width, height):
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".ass",
            prefix="ai_visual_composer_subtitles_",
            delete=False,
            newline="\n",
        ) as stream:
            target = Path(stream.name)
        try:
            self.build(
                subtitle_path=subtitle_path,
                render_style=render_style,
                width=width,
                height=height,
                output_path=target,
            )
        except Exception:
            if target.exists():
                target.unlink()
            raise
        return target

    def build(self, subtitle_path, render_style, width, height, output_path):
        subtitle_path = Path(subtitle_path)
        output_path = Path(output_path)
        cues = self._read_srt(subtitle_path)
        output_path.write_text(
            self._document(cues, render_style, width, height),
            encoding="utf-8",
            newline="\n",
        )
        return output_path

    def _document(self, cues, style, width, height):
        if width <= 0 or height <= 0:
            raise ValueError("La resolucion ASS debe ser positiva.")
        font = self.font_manager.resolve_name(style.font)
        secondary = style.secondary_colour or style.primary_colour
        values = (
            "Default",
            font,
            style.font_size,
            style.primary_colour,
            secondary,
            style.outline_colour,
            style.back_colour,
            -1 if style.bold else 0,
            -1 if style.italic else 0,
            -1 if style.underline else 0,
            -1 if style.strikeout else 0,
            style.scale_x if style.scale_x is not None else 100,
            style.scale_y if style.scale_y is not None else 100,
            style.spacing if style.spacing is not None else 0,
            0,
            style.border_style,
            style.outline,
            style.shadow,
            style.alignment,
            style.margin_l if style.margin_l is not None else 20,
            style.margin_r if style.margin_r is not None else 20,
            style.margin_v,
            1,
        )
        lines = [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {width}",
            f"PlayResY: {height}",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
            "Style: " + ",".join(str(value) for value in values),
            "",
            "[Events]",
            "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
        ]
        lines.extend(
            "Dialogue: 0,"
            f"{self._ass_time(start)},{self._ass_time(end)},Default,,0,0,0,,"
            f"{self._effect_tags(style.cue_effect, start, end, style, width, height)}"
            f"{self._word_effect_tags(style.word_effect, start, end, text)}"
            f"{self._escape_text(text)}"
            for start, end, text in cues
        )
        return "\n".join(lines) + "\n"

    def _read_srt(self, subtitle_path):
        if not subtitle_path.is_file():
            raise FileNotFoundError(f"No existe el SRT: {subtitle_path}")
        content = subtitle_path.read_text(encoding="utf-8-sig")
        blocks = re.split(r"\r?\n\s*\r?\n", content.strip())
        cues = []
        for block in blocks:
            lines = block.splitlines()
            if len(lines) < 3:
                raise ValueError("El SRT contiene un cue incompleto para ASS.")
            if "-->" not in lines[1]:
                raise ValueError("El SRT contiene un timing invalido para ASS.")
            start, end = (part.strip() for part in lines[1].split("-->", 1))
            cues.append((
                self._milliseconds(start),
                self._milliseconds(end),
                "\n".join(lines[2:]),
            ))
        return tuple(cues)

    def _milliseconds(self, value):
        match = self._TIMESTAMP.fullmatch(value)
        if match is None:
            raise ValueError(f"Timestamp SRT invalido para ASS: {value!r}.")
        parts = {key: int(item) for key, item in match.groupdict().items()}
        if parts["minutes"] >= 60 or parts["seconds"] >= 60:
            raise ValueError(f"Timestamp SRT invalido para ASS: {value!r}.")
        return (
            parts["hours"] * 3_600_000
            + parts["minutes"] * 60_000
            + parts["seconds"] * 1_000
            + parts["milliseconds"]
        )

    @staticmethod
    def _ass_time(milliseconds):
        centiseconds = milliseconds // 10
        hours, remainder = divmod(centiseconds, 360_000)
        minutes, remainder = divmod(remainder, 6_000)
        seconds, centiseconds = divmod(remainder, 100)
        return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

    @staticmethod
    def _escape_text(text):
        return (
            text.replace("\\", r"\\")
            .replace("{", r"\{")
            .replace("}", r"\}")
            .replace("\n", r"\N")
        )

    def _effect_tags(self, effect, start, end, style, width, height):
        if effect is None:
            return ""
        duration = end - start
        if duration <= 0:
            raise ValueError("El cue ASS debe tener duracion positiva.")
        name = effect.name
        parameters = effect.parameters
        if name == "fade":
            fade_in, fade_out = self._fit_windows(
                parameters["in_ms"], parameters["out_ms"], duration
            )
            return f"{{\\fad({fade_in},{fade_out})}}"
        if name in ("pop", "zoom"):
            target_x = style.scale_x if style.scale_x is not None else 100
            target_y = style.scale_y if style.scale_y is not None else 100
            if name == "zoom":
                target_x = target_y = parameters["to_scale"]
            window = min(parameters["in_ms"], duration)
            scale = parameters["from_scale"]
            return (
                f"{{\\fscx{self._number(scale)}\\fscy{self._number(scale)}"
                f"\\t(0,{window},\\fscx{self._number(target_x)}"
                f"\\fscy{self._number(target_y)})}}"
            )
        if name == "slide":
            base_x, base_y = self._base_position(style, width, height)
            start_x, start_y = self._slide_origin(
                parameters["direction"], base_x, base_y, width, height
            )
            window = min(parameters["duration_ms"], duration)
            return (
                f"{{\\move({self._number(start_x)},{self._number(start_y)},"
                f"{self._number(base_x)},{self._number(base_y)},0,{window})}}"
            )
        raise ValueError(f"Efecto ASS no soportado: {name!r}.")

    def _word_effect_tags(self, effect, start, end, text):
        if effect is None:
            return ""
        if len(text.split()) != 1:
            raise ValueError(
                "Los word effects requieren cues finales de una sola palabra; "
                "no se resegmenta el SRT para ASS."
            )
        duration = end - start
        if duration <= 0:
            raise ValueError("El cue ASS debe tener duracion positiva.")
        if effect.name == "karaoke":
            return f"{{\\kf{self._karaoke_centiseconds(duration)}}}"
        if effect.name == "highlight":
            return f"{{\\1c{effect.parameters['active_colour']}}}"
        if effect.name == "progressive_reveal":
            reveal = min(effect.parameters["reveal_ms"], duration)
            return f"{{\\1a&HFF&\\t(0,{reveal},\\1a&H00&)}}"
        raise ValueError(f"Word effect ASS no soportado: {effect.name!r}.")

    @staticmethod
    def _karaoke_centiseconds(milliseconds):
        # ASS karaoke uses centiseconds. Ceiling preserves a nonzero visual
        # duration for source cues shorter than one centisecond.
        return max(1, (milliseconds + 9) // 10)

    @staticmethod
    def _fit_windows(fade_in, fade_out, duration):
        total = fade_in + fade_out
        if total <= duration:
            return fade_in, fade_out
        if total == 0:
            return 0, 0
        fitted_in = round(fade_in * duration / total)
        return fitted_in, duration - fitted_in

    @staticmethod
    def _base_position(style, width, height):
        alignment = style.alignment
        column = (alignment - 1) % 3
        row = (alignment - 1) // 3
        if column == 0:
            x = style.margin_l if style.margin_l is not None else 20
        elif column == 1:
            x = width / 2
        else:
            x = width - (style.margin_r if style.margin_r is not None else 20)
        if row == 0:
            y = height - style.margin_v
        elif row == 1:
            y = height / 2
        else:
            y = style.margin_v
        return x, y

    @staticmethod
    def _slide_origin(direction, x, y, width, height):
        if direction == "left":
            return x - width, y
        if direction == "right":
            return x + width, y
        if direction == "up":
            return x, y - height
        if direction == "down":
            return x, y + height
        raise ValueError(f"Direccion slide no soportada: {direction!r}.")

    @staticmethod
    def _number(value):
        return str(int(value)) if float(value).is_integer() else str(value)
