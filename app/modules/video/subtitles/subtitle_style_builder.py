from app.managers.font_manager import FontManager


class SubtitleStyleBuilder:

    def __init__(
        self,
        font_manager=None
    ):
        self.font_manager = (
            font_manager
            or FontManager()
        )

    def build(
        self,
        subtitle_style
    ):
        if subtitle_style is None:
            subtitle_style = {}

        if not isinstance(
            subtitle_style,
            dict
        ):
            raise TypeError(
                "La configuración de subtítulos "
                "debe ser un diccionario."
            )

        font_name = subtitle_style.get(
            "font",
            "Arial"
        )

        font = self.font_manager.resolve_name(
            font_name
        )

        font_size = int(
            subtitle_style.get(
                "font_size",
                20
            )
        )

        bold = (
            1
            if subtitle_style.get(
                "bold",
                True
            )
            else 0
        )

        primary_colour = str(
            subtitle_style.get(
                "primary_colour",
                "&H00FFFFFF"
            )
        )

        outline_colour = str(
            subtitle_style.get(
                "outline_colour",
                "&H00000000"
            )
        )

        back_colour = str(
            subtitle_style.get(
                "back_colour",
                "&H00000000"
            )
        )

        border_style = int(
            subtitle_style.get(
                "border_style",
                1
            )
        )

        outline = int(
            subtitle_style.get(
                "outline",
                0
            )
        )

        shadow = int(
            subtitle_style.get(
                "shadow",
                1
            )
        )

        alignment = int(
            subtitle_style.get(
                "alignment",
                2
            )
        )

        margin_v = int(
            subtitle_style.get(
                "margin_v",
                25
            )
        )

        optional_ass = []
        if "italic" in subtitle_style:
            optional_ass.append(
                f"Italic={1 if subtitle_style['italic'] else 0}"
            )
        if "underline" in subtitle_style:
            optional_ass.append(
                f"Underline={1 if subtitle_style['underline'] else 0}"
            )
        if "strikeout" in subtitle_style:
            optional_ass.append(
                f"StrikeOut={1 if subtitle_style['strikeout'] else 0}"
            )
        if "secondary_colour" in subtitle_style:
            optional_ass.append(
                "SecondaryColour="
                f"{subtitle_style['secondary_colour']}"
            )
        if "margin_l" in subtitle_style:
            optional_ass.append(f"MarginL={subtitle_style['margin_l']}")
        if "margin_r" in subtitle_style:
            optional_ass.append(f"MarginR={subtitle_style['margin_r']}")
        if "scale_x" in subtitle_style:
            optional_ass.append(f"ScaleX={subtitle_style['scale_x']}")
        if "scale_y" in subtitle_style:
            optional_ass.append(f"ScaleY={subtitle_style['scale_y']}")
        if "spacing" in subtitle_style:
            optional_ass.append(f"Spacing={subtitle_style['spacing']}")

        if font_size <= 0:
            raise ValueError(
                "El tamaño de fuente debe ser "
                "superior a cero."
            )

        if alignment < 1 or alignment > 9:
            raise ValueError(
                "La alineación de subtítulos debe "
                "estar entre 1 y 9."
            )

        style = (
            f"FontName={font},"
            f"FontSize={font_size},"
            f"Bold={bold},"
            f"PrimaryColour={primary_colour},"
            f"OutlineColour={outline_colour},"
            f"BackColour={back_colour},"
            f"BorderStyle={border_style},"
            f"Outline={outline},"
            f"Shadow={shadow},"
            f"Alignment={alignment},"
            f"MarginV={margin_v}"
        )
        if optional_ass:
            style += "," + ",".join(optional_ass)
        return style
