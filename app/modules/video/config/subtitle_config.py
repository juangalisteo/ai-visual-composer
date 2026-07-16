from dataclasses import dataclass


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