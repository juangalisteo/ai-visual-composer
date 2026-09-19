from dataclasses import dataclass


@dataclass(frozen=True)
class CueEffectConfig:

    name: str
    parameters: dict[str, object]


@dataclass(frozen=True)
class WordEffectConfig:

    name: str
    parameters: dict[str, object]


@dataclass(frozen=True)
class SubtitleConfig:

    font: str

    font_size: int

    bold: bool

    primary_colour: str

    outline_colour: str

    back_colour: str

    border_style: int

    outline: int

    shadow: int

    alignment: int

    margin_v: int

    offset: float

    italic: bool | None = None

    underline: bool | None = None

    strikeout: bool | None = None

    secondary_colour: str | None = None

    margin_l: int | None = None

    margin_r: int | None = None

    scale_x: float | None = None

    scale_y: float | None = None

    spacing: float | None = None

    dynamic: bool = False

    cue_effect: CueEffectConfig | None = None

    word_effect: WordEffectConfig | None = None
