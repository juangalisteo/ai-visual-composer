"""Subtitle fonts declared in config/fonts.json."""

import json
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from app.shared.config_contract import (
    require_mapping,
    require_sequence,
    require_text,
)
from app.shared.operational_error import create_operational_error
from app.shared.progress_logger import ProgressLogger


@dataclass(frozen=True)
class FontDeclaration:
    """One font of the catalog.

    name is the font name written in the subtitle style (FontName= or
    Style:), the one libass looks for in the fonts directory. file is a
    plain file name inside that directory. aliases are lower-case.
    fallback is the name of another font of the catalog, or None.
    """

    name: str
    file: str
    aliases: tuple
    fallback: str | None = None


class FallbackNotices:
    """Fonts already reported as replaced by their fallback.

    FontManager warns once per font and registry. The application shares
    one registry for the whole run (RUN_FALLBACK_NOTICES), because every
    subtitle builder creates its own FontManager; a test passes its own
    registry or resets that one.
    """

    def __init__(self):
        self._reported = set()

    def first_time(self, font_name):
        """True the first time font_name is reported, False afterwards."""
        if font_name in self._reported:
            return False

        self._reported.add(
            font_name
        )

        return True

    def reset(self):
        self._reported.clear()


# The run's registry: one warning per missing font in each run.
RUN_FALLBACK_NOTICES = FallbackNotices()


class FontManager:
    """Resolves the fonts declared in config/fonts.json.

    Each font declares its file in assets/fonts/, its aliases and,
    optionally, a fallback: another font of the catalog used when its
    file is missing (one level only). The catalog is read and checked
    once per instance; main.py checks it before the first menu. Without
    the file the catalog is empty and every name passes through.
    """

    FONTS_DIR = Path(
        "assets/fonts"
    )

    CATALOG_PATH = Path(
        "config/fonts.json"
    )

    def __init__(
        self,
        catalog_path=None,
        fallback_notices=None
    ):
        self.catalog_path = Path(
            catalog_path
            if catalog_path is not None
            else self.CATALOG_PATH
        )
        self.fallback_notices = (
            fallback_notices
            if fallback_notices is not None
            else RUN_FALLBACK_NOTICES
        )
        self._fonts = None
        self._aliases = None

    def validate(
        self
    ):
        """Read and check the catalog; called once before the first menu."""
        self._load()

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

        declaration = self._load().get(
            resolved_name
        )

        if declaration is None:
            raise ValueError(
                "No existe una ruta registrada "
                f"para la fuente: {resolved_name}"
            )

        font_path = self._file_path(
            declaration
        ).resolve()

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

        return self._file_path(
            self._load()[fallback]
        ).resolve()

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
            self._load().keys()
        )

    def declaration(
        self,
        font_name
    ):
        """The catalog entry of a font name or alias, or None."""
        return self._load().get(
            self._registered_name(
                font_name
            )
        )

    def _registered_name(
        self,
        font_name
    ):
        self._load()

        normalized_name = self._normalize_name(
            font_name
        )

        return self._aliases.get(
            normalized_name,
            str(
                font_name
            ).strip()
        )

    def _file_path(
        self,
        declaration
    ):
        return self.FONTS_DIR / declaration.file

    def _fallback_for(
        self,
        resolved_name
    ):
        """Return the declared fallback of a font whose file is missing.

        None when the font has its file, declares no fallback or its
        fallback has no file either.
        """
        fonts = self._load()
        declaration = fonts.get(
            resolved_name
        )

        if (
            declaration is None
            or declaration.fallback is None
            or self._file_path(declaration).exists()
        ):
            return None

        fallback = fonts[
            declaration.fallback
        ]

        if not self._file_path(
            fallback
        ).exists():
            return None

        self._report_fallback(
            declaration,
            fallback.name
        )

        return fallback.name

    def _report_fallback(
        self,
        declaration,
        fallback_name
    ):
        """Warn once per font and registry, always with the relative folder."""
        if not self.fallback_notices.first_time(
            declaration.name
        ):
            return

        ProgressLogger.warning(
            f"falta la fuente «{declaration.file}»; "
            f"los subtítulos usan «{fallback_name}» en su lugar. "
            "Para usar la original, pon ese archivo en "
            f"{self.FONTS_DIR.as_posix()}/."
        )

    def _normalize_name(
        self,
        font_name
    ):
        return str(
            font_name
        ).strip().lower()

    def _load(
        self
    ):
        if self._fonts is None:
            self._fonts, self._aliases = self._read_catalog()

        return self._fonts

    def _read_catalog(
        self
    ):
        # Without the file the catalog is empty, as with config/formats.json:
        # every font name passes through unchanged.
        if not self.catalog_path.is_file():
            return {}, {}

        try:
            with self.catalog_path.open("r", encoding="utf-8") as file:
                data = json.load(file)

            entries = require_mapping(data, "fonts", "fonts")
            fonts = {
                font_name: self._declaration(entries, font_name)
                for font_name in entries
            }
            self._check_fallbacks(fonts)

            return fonts, self._alias_index(fonts)

        except (OSError, TypeError, ValueError) as error:
            raise create_operational_error(
                family="CONFIG",
                user_message=(
                    f"El catálogo de fuentes no es válido: {error}"
                ),
                recommended_action=(
                    "Corrija el archivo: cada fuente necesita file (el nombre "
                    f"de un archivo de {self.FONTS_DIR.as_posix()}/) y "
                    "aliases (lista de textos); fallback, si lo lleva, es "
                    "otra fuente del catálogo sin reserva propia."
                ),
                operation="Leer catálogo de fuentes",
                resource=str(self.catalog_path),
            ) from error

    def _declaration(
        self,
        entries,
        font_name
    ):
        path = f"fonts.{font_name}"

        if not font_name.strip():
            raise ValueError(
                "La configuración fonts tiene una fuente sin nombre."
            )

        entry = require_mapping(entries, font_name, path)
        file_name = require_text(entry, "file", f"{path}.file")

        # libass only reads the fonts directory itself, not subfolders.
        if (
            PureWindowsPath(file_name).name != file_name
            or file_name in (".", "..")
        ):
            raise ValueError(
                f"La configuración {path}.file («{file_name}») queda fuera "
                f"de {self.FONTS_DIR.as_posix()}/: debe ser solo el nombre "
                "del archivo."
            )

        aliases = require_sequence(entry, "aliases", f"{path}.aliases")

        for index, alias in enumerate(aliases):
            if not isinstance(alias, str) or not alias.strip():
                raise ValueError(
                    f"La configuración {path}.aliases[{index}] debe "
                    "contener texto."
                )

        return FontDeclaration(
            name=font_name,
            file=file_name,
            aliases=tuple(
                self._normalize_name(alias)
                for alias in aliases
            ),
            fallback=(
                require_text(entry, "fallback", f"{path}.fallback")
                if "fallback" in entry
                else None
            ),
        )

    @staticmethod
    def _check_fallbacks(
        fonts
    ):
        for declaration in fonts.values():
            if declaration.fallback is None:
                continue

            fallback = fonts.get(
                declaration.fallback
            )

            if fallback is None:
                raise ValueError(
                    f"La reserva «{declaration.fallback}» de la fuente "
                    f"«{declaration.name}» no está en el catálogo."
                )

            if fallback.fallback is not None:
                raise ValueError(
                    f"La reserva «{fallback.name}» de la fuente "
                    f"«{declaration.name}» tiene a su vez reserva "
                    f"(«{fallback.fallback}»); solo se admite un nivel."
                )

    @staticmethod
    def _alias_index(
        fonts
    ):
        index = {}

        for declaration in fonts.values():
            for alias in declaration.aliases:
                owner = index.get(
                    alias
                )

                if owner == declaration.name:
                    raise ValueError(
                        f"El alias «{alias}» está repetido "
                        f"en «{owner}»."
                    )

                if owner is not None:
                    raise ValueError(
                        f"El alias «{alias}» está repetido "
                        f"(en «{owner}» y en «{declaration.name}»)."
                    )

                index[alias] = declaration.name

        return index
