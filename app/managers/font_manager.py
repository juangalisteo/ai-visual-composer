from pathlib import Path


class FontManager:

    FONTS_DIR = Path(
        "assets/fonts"
    )

    FONT_ALIASES = {
        "gotham": "Gotham Narrow Bold",
        "gotham narrow": "Gotham Narrow Bold",
        "gotham narrow bold": "Gotham Narrow Bold",
        "gotham narrow bold.otf": "Gotham Narrow Bold",

        "unisans": "UniSansHeavyCAPS",
        "uni sans": "UniSansHeavyCAPS",
        "uni sans heavy": "UniSansHeavyCAPS",
        "uni sans heavy.otf": "UniSansHeavyCAPS",
        "unisansheavycaps": "UniSansHeavyCAPS",

        "oswald": "Oswald",
        "oswald variable": "Oswald",
        "oswald-variablefont_wght": "Oswald",
        "oswald-variablefont_wght.ttf": "Oswald",

        "anton": "Anton",
        "anton regular": "Anton",
        "anton-regular": "Anton",
        "anton-regular.ttf": "Anton"
    }

    FONT_FILES = {
        "Gotham Narrow Bold": (
            FONTS_DIR
            / "Gotham Narrow Bold.otf"
        ),

        "UniSansHeavyCAPS": (
            FONTS_DIR
            / "Uni Sans Heavy.otf"
        ),

        "Oswald": (
            FONTS_DIR
            / "Oswald-VariableFont_wght.ttf"
        ),

        "Anton": (
            FONTS_DIR
            / "Anton-Regular.ttf"
        )
    }

    def resolve_name(
        self,
        font_name
    ):
        normalized_name = self._normalize_name(
            font_name
        )

        return self.FONT_ALIASES.get(
            normalized_name,
            str(
                font_name
            ).strip()
        )

    def resolve_path(
        self,
        font_name
    ):
        resolved_name = self.resolve_name(
            font_name
        )

        font_path = self.FONT_FILES.get(
            resolved_name
        )

        if font_path is None:
            raise ValueError(
                "No existe una ruta registrada "
                f"para la fuente: {resolved_name}"
            )

        font_path = font_path.resolve()

        if not font_path.exists():
            raise FileNotFoundError(
                f"No existe el archivo de fuente: "
                f"{font_path}"
            )

        return font_path

    def exists(
        self,
        font_name
    ):
        try:
            self.resolve_path(
                font_name
            )

            return True

        except (
            ValueError,
            FileNotFoundError
        ):
            return False

    def list_fonts(
        self
    ):
        return tuple(
            self.FONT_FILES.keys()
        )

    def _normalize_name(
        self,
        font_name
    ):
        return str(
            font_name
        ).strip().lower()
