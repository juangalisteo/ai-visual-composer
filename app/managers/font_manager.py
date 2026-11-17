from pathlib import Path

from app.shared.progress_logger import ProgressLogger


# Fonts already reported as replaced by their fallback in this run.
_reported_fallbacks = set()


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

    # Font used instead of a registered font whose file is missing. Only
    # one level: if the fallback's file is missing too, nothing replaces it.
    FONT_FALLBACKS = {
        "Gotham Narrow Bold": "Anton",
        "UniSansHeavyCAPS": "Anton"
    }

    def resolve_name(
        self,
        font_name
    ):
        resolved_name = self._registered_name(
            font_name
        )

        fallback = self._fallback_for(
            resolved_name
        )

        if fallback is not None:
            return fallback

        return resolved_name

    def resolve_path(
        self,
        font_name
    ):
        resolved_name = self._registered_name(
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

        if font_path.exists():
            return font_path

        fallback = self._fallback_for(
            resolved_name
        )

        if fallback is None:
            raise FileNotFoundError(
                f"No existe el archivo de fuente: "
                f"{font_path}"
            )

        return self.FONT_FILES[
            fallback
        ].resolve()

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

    def _registered_name(
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

    def _fallback_for(
        self,
        resolved_name
    ):
        """Return the declared fallback of a font whose file is missing.

        None when the font has its file, declares no fallback or its
        fallback has no file either.
        """
        font_path = self.FONT_FILES.get(
            resolved_name
        )
        fallback = self.FONT_FALLBACKS.get(
            resolved_name
        )

        if (
            font_path is None
            or fallback is None
            or font_path.exists()
        ):
            return None

        fallback_path = self.FONT_FILES.get(
            fallback
        )

        if (
            fallback_path is None
            or not fallback_path.exists()
        ):
            return None

        self._report_fallback(
            resolved_name,
            font_path,
            fallback
        )

        return fallback

    def _report_fallback(
        self,
        resolved_name,
        font_path,
        fallback
    ):
        """Warn once per font and run."""
        if resolved_name in _reported_fallbacks:
            return

        _reported_fallbacks.add(
            resolved_name
        )

        ProgressLogger.warning(
            f"falta la fuente «{font_path.name}»; "
            f"los subtítulos usan «{fallback}» en su lugar. "
            "Para usar la original, pon ese archivo en "
            f"{font_path.parent.as_posix()}/."
        )

    def _normalize_name(
        self,
        font_name
    ):
        return str(
            font_name
        ).strip().lower()
