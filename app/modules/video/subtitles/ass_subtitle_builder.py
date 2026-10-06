from dataclasses import dataclass
from enum import Enum
import math
from pathlib import Path
import re
import tempfile

from app.managers.font_manager import FontManager
from app.modules.subtitles.effects.physics import KineticPhysicsEngine
from app.modules.subtitles.effects.typewriter import TypewriterInterpolator
from app.modules.subtitles.rendering.font_metrics import FontMetricsEngine


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

    def __init__(self, font_manager=None, font_metrics=None, typewriter=None, physics=None):
        self.font_manager = font_manager or FontManager()
        self.font_metrics = font_metrics or FontMetricsEngine(
            font_manager=self.font_manager,
        )
        self.typewriter = typewriter or TypewriterInterpolator()
        self.physics = physics or KineticPhysicsEngine()

    def build_temporary(self, subtitle_path, render_style, width, height, timing=None):
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
                timing=timing,
            )
        except Exception:
            if target.exists():
                target.unlink()
            raise
        return target

    def build(
        self,
        subtitle_path,
        render_style,
        width,
        height,
        output_path,
        timing=None,
    ):
        subtitle_path = Path(subtitle_path)
        output_path = Path(output_path)
        cues = self._read_srt(subtitle_path)
        output_path.write_text(
            self._document(cues, render_style, width, height, timing=timing),
            encoding="utf-8",
            newline="\n",
        )
        return output_path

    def _document(self, cues, style, width, height, timing=None):
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
        for start, end, text in cues:
            kinetic = self._kinetic_dialogues(
                start,
                end,
                text,
                style,
                width,
                height,
            )
            if kinetic:
                lines.extend(kinetic)
                continue
            in_sentence = self._in_sentence_dialogues(
                start,
                end,
                text,
                style,
                timing,
                width,
                height,
            )
            if in_sentence:
                lines.extend(in_sentence)
                continue
            lines.append(
                "Dialogue: 0,"
                f"{self._ass_time(start)},{self._ass_time(end)},Default,,0,0,0,,"
                f"{self._effect_tags(style.cue_effect, start, end, style, width, height)}"
                f"{self._word_effect_tags(style.word_effect, start, end, text)}"
                f"{self._escape_text(text)}"
            )
        return "\n".join(lines) + "\n"

    def _kinetic_dialogues(self, start, end, text, style, width, height):
        effect = style.cue_effect
        if effect is None or effect.name != "gravity_drop":
            return ()
        base_x, base_y = self._base_position(style, width, height)
        segments = self.physics.gravity_drop(
            start,
            end,
            base_y,
            effect.parameters["drop_height_px"],
            effect.parameters["bounce_elasticity"],
        )
        return tuple(
            "Dialogue: 0,"
            f"{self._ass_time(segment.start)},{self._ass_time(segment.end)},"
            "Default,,0,0,0,,"
            f"{{\\move({self._number(base_x)},{self._number(segment.from_y)},"
            f"{self._number(base_x)},{self._number(segment.to_y)},0,"
            f"{segment.end - segment.start})}}{self._escape_text(text)}"
            for segment in segments
        )

    def _in_sentence_dialogues(self, start, end, text, style, timing, width, height):
        effect = style.word_effect
        if effect is None or effect.name not in {
            "highlight_in_sentence",
            "active_pill",
            "pop_in_sentence",
            "typewriter",
            "alpha_fade",
        }:
            return ()
        words = self._words_for_cue(start, end, text, timing)
        if not words:
            return ()
        if effect.name == "typewriter":
            return self._typewriter_dialogues(
                text,
                words,
                start,
                end,
                effect.parameters,
            )

        boxes = (
            self.font_metrics.word_boxes(text, style, width, height)
            if effect.name == "active_pill"
            else ()
        )
        if effect.name == "active_pill" and len(boxes) != len(words):
            return ()

        boundaries = {start, end}
        for word in words:
            boundaries.add(max(start, self._milliseconds_from_seconds(word.start)))
            boundaries.add(min(end, self._milliseconds_from_seconds(word.end)))
        boundaries = sorted(boundaries)
        dialogues = []
        for interval_start, interval_end in zip(boundaries, boundaries[1:]):
            if interval_end <= interval_start:
                continue
            active_index = next(
                (
                    index
                    for index, word in enumerate(words)
                    if self._milliseconds_from_seconds(word.start) <= interval_start
                    and self._milliseconds_from_seconds(word.end) >= interval_end
                ),
                None,
            )
            if effect.name == "active_pill" and active_index is not None:
                dialogues.append(
                    self._pill_dialogue(
                        interval_start,
                        interval_end,
                        boxes[active_index],
                        effect.parameters,
                    )
                )
            layer = 1 if effect.name == "active_pill" else 0
            if effect.name == "pop_in_sentence":
                rendered_text = self._popped_text(
                    text,
                    active_index,
                    interval_end - interval_start,
                    effect.parameters["word_pop_scale"],
                )
            elif effect.name == "alpha_fade":
                rendered_text = self._alpha_faded_text(
                    text,
                    words,
                    interval_start,
                    effect.parameters["fade_duration_ms"],
                )
            else:
                rendered_text = self._highlighted_text(text, active_index, style)
            dialogues.append(
                f"Dialogue: {layer},"
                f"{self._ass_time(interval_start)},{self._ass_time(interval_end)},"
                "Default,,0,0,0,,"
                f"{rendered_text}"
            )
        return tuple(dialogues)

    def _alpha_faded_text(self, text, words, interval_start, fade_duration):
        rendered = []
        for rendered_word, word in zip(text.replace("\n", " ").split(), words):
            word_start = self._milliseconds_from_seconds(word.start)
            escaped = self._escape_text(rendered_word)
            if word_start > interval_start:
                rendered.append(f"{{\\1a&HFF&}}{escaped}{{\\1a&H00&}}")
            elif word_start == interval_start:
                rendered.append(
                    f"{{\\1a&HFF&\\t(0,{fade_duration},\\1a&H00&)}}"
                    f"{escaped}{{\\1a&H00&}}"
                )
            else:
                rendered.append(escaped)
        return " ".join(rendered)

    def _typewriter_dialogues(self, text, words, start, end, parameters):
        steps = self.typewriter.interpolate(
            words,
            text.replace("\n", " ").split(),
            start,
            end,
            cursor=parameters["typewriter_cursor"],
            cursor_char=parameters["cursor_char"],
        )
        return tuple(
            "Dialogue: 0,"
            f"{self._ass_time(step.start)},{self._ass_time(step.end)},"
            "Default,,0,0,0,,"
            f"{self._escape_text(step.text)}"
            for step in steps
        )

    def _popped_text(self, text, active_index, duration, scale):
        words = text.replace("\n", " ").split()
        if active_index is None:
            return self._escape_text(" ".join(words))
        midpoint = max(1, duration // 2)
        rendered = []
        for index, word in enumerate(words):
            escaped = self._escape_text(word)
            if index == active_index:
                rendered.append(
                    f"{{\\t(0,{midpoint},\\fscx{scale}\\fscy{scale})"
                    f"\\t({midpoint},{duration},\\fscx100\\fscy100)}}"
                    f"{escaped}{{\\fscx100\\fscy100}}"
                )
            else:
                rendered.append(escaped)
        return " ".join(rendered)

    def _pill_dialogue(self, start, end, box, parameters):
        padding = parameters["pill_padding"]
        left = box.left - padding
        top = box.top - padding
        right = box.right + padding
        bottom = box.bottom + padding
        drawing = self._rounded_rectangle(
            left,
            top,
            right,
            bottom,
            parameters["pill_radius"],
        )
        return (
            "Dialogue: 0,"
            f"{self._ass_time(start)},{self._ass_time(end)},Default,,0,0,0,,"
            f"{{\\an7\\pos(0,0)\\p1\\1c{parameters['pill_colour']}}}"
            f"{drawing}"
        )

    def _rounded_rectangle(self, left, top, right, bottom, radius):
        radius = min(float(radius), (right - left) / 2, (bottom - top) / 2)
        curve = radius * 0.55228475
        return (
            f"m {self._number(left + radius)} {self._number(top)} "
            f"l {self._number(right - radius)} {self._number(top)} "
            f"b {self._number(right - radius + curve)} {self._number(top)} "
            f"{self._number(right)} {self._number(top + radius - curve)} "
            f"{self._number(right)} {self._number(top + radius)} "
            f"l {self._number(right)} {self._number(bottom - radius)} "
            f"b {self._number(right)} {self._number(bottom - radius + curve)} "
            f"{self._number(right - radius + curve)} {self._number(bottom)} "
            f"{self._number(right - radius)} {self._number(bottom)} "
            f"l {self._number(left + radius)} {self._number(bottom)} "
            f"b {self._number(left + radius - curve)} {self._number(bottom)} "
            f"{self._number(left)} {self._number(bottom - radius + curve)} "
            f"{self._number(left)} {self._number(bottom - radius)} "
            f"l {self._number(left)} {self._number(top + radius)} "
            f"b {self._number(left)} {self._number(top + radius - curve)} "
            f"{self._number(left + radius - curve)} {self._number(top)} "
            f"{self._number(left + radius)} {self._number(top)}"
        )

    def _words_for_cue(self, start, end, text, timing):
        if timing is None or not getattr(timing, "is_usable", lambda: False)():
            return ()
        words = tuple(
            word
            for word in timing.words
            if self._milliseconds_from_seconds(word.start) >= start
            and self._milliseconds_from_seconds(word.end) <= end
            and word.end > word.start
        )
        rendered_words = text.replace("\n", " ").split()
        if len(words) != len(rendered_words):
            return ()
        if any(
            self._normalised_word(word.text) != self._normalised_word(rendered)
            for word, rendered in zip(words, rendered_words)
        ):
            return ()
        return words

    def _highlighted_text(self, text, active_index, style):
        inactive = style.secondary_colour or style.primary_colour
        words = text.replace("\n", " ").split()
        rendered = []
        for index, word in enumerate(words):
            escaped = self._escape_text(word)
            if index == active_index:
                rendered.append(
                    f"{{\\1c{style.primary_colour}}}{escaped}"
                    f"{{\\1c{inactive}}}"
                )
            else:
                rendered.append(escaped)
        return f"{{\\1c{inactive}}}" + " ".join(rendered)

    @staticmethod
    def _milliseconds_from_seconds(seconds):
        return int(math.floor(float(seconds) * 1000.0 + 0.5))

    @staticmethod
    def _normalised_word(text):
        return "".join(character for character in text.casefold() if character.isalnum())

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
        if name == "gravity_drop":
            # Handled as coordinated micro-dialogues by _kinetic_dialogues.
            # A cue shorter than the kinetic safety window falls back to static.
            return ""
        raise ValueError(f"Efecto ASS no soportado: {name!r}.")

    def _word_effect_tags(self, effect, start, end, text):
        if effect is None:
            return ""
        if effect.name in {
            "highlight_in_sentence",
            "active_pill",
            "pop_in_sentence",
            "typewriter",
            "alpha_fade",
        }:
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
