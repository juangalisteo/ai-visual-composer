"""Etiqueta y orden de los formatos declarados en la configuración."""

import json
from dataclasses import dataclass
from pathlib import Path

from app.controllers.interaction import labels
from app.shared.config_contract import (
    require_int,
    require_mapping,
    require_text,
)
from app.shared.operational_error import create_operational_error
from app.shared.profile_identity import ProfileComponent
from app.shared.profile_resolver import ProfileResolver


@dataclass(frozen=True)
class FormatDeclaration:
    display_name: str
    order: int


class FormatCatalog:
    """Presenta los formatos descubiertos según config/formats.json.

    Un formato declarado sale con su display_name y en su order. Uno
    descubierto sin declaración sale con labels.label y detrás de los
    declarados, por orden alfabético. Sin el archivo, todos salen así.
    Solo es presentación: nunca decide qué formatos existen.
    """

    def __init__(
        self,
        catalog_path=Path("config/formats.json"),
        profiles_root=Path("config/profiles"),
    ):
        self.catalog_path = Path(catalog_path)
        self.profiles_root = Path(profiles_root)
        self._declarations = None

    def label(self, profile_format):
        declaration = self._load().get(profile_format)
        if declaration is None:
            return labels.label(profile_format)
        return declaration.display_name

    def ordered(self, profile_formats):
        declarations = self._load()

        def sort_key(profile_format):
            declaration = declarations.get(profile_format)
            if declaration is None:
                return (1, 0, profile_format)
            return (0, declaration.order, profile_format)

        return tuple(sorted(profile_formats, key=sort_key))

    def _load(self):
        if self._declarations is None:
            self._declarations = self._read_declarations()
        return self._declarations

    def _read_declarations(self):
        if not self.catalog_path.is_file():
            return {}
        try:
            with self.catalog_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            formats = require_mapping(data, "formats", "formats")
            declarations = {
                profile_format: self._declaration(formats, profile_format)
                for profile_format in formats
            }
        except (OSError, TypeError, ValueError) as error:
            raise create_operational_error(
                family="CONFIG",
                user_message=(
                    f"El catálogo de formatos no es válido: {error}"
                ),
                recommended_action=(
                    "Corrija el archivo: cada formato necesita display_name "
                    "(texto) y order (entero)."
                ),
                operation="Leer catálogo de formatos",
                resource=str(self.catalog_path),
            ) from error

        undiscovered = sorted(set(declarations) - self._format_directories())
        if undiscovered:
            error = ValueError(
                f"Formatos declarados sin carpeta: {', '.join(undiscovered)}"
            )
            raise create_operational_error(
                family="CONFIG",
                user_message=(
                    "El catálogo de formatos declara formatos sin carpeta de "
                    f"perfiles: {', '.join(undiscovered)}."
                ),
                recommended_action=(
                    "Cree la carpeta del formato en "
                    f"{self.profiles_root.as_posix()}/<componente>/ o quite "
                    "su declaración del catálogo de formatos."
                ),
                operation="Leer catálogo de formatos",
                resource=str(self.catalog_path),
                technical_metadata={
                    "formats": undiscovered,
                    "profiles_root": str(self.profiles_root),
                },
            ) from error
        return declarations

    @staticmethod
    def _declaration(formats, profile_format):
        path = f"formats.{profile_format}"
        declaration = require_mapping(formats, profile_format, path)
        return FormatDeclaration(
            display_name=require_text(
                declaration,
                "display_name",
                f"{path}.display_name",
            ),
            order=require_int(declaration, "order", f"{path}.order"),
        )

    def _format_directories(self):
        resolver = ProfileResolver(self.profiles_root)
        return {
            profile_format
            for component in ProfileComponent
            for profile_format in resolver.discover_formats(component)
        }
