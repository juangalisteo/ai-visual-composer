"""Formatos declarados en la configuración: etiqueta, orden, orientación, guía de imagen y duración de las escenas."""

import json
from dataclasses import dataclass
from pathlib import Path

from app.shared.config_contract import (
    require_float,
    require_int,
    require_mapping,
    require_text,
)
from app.shared.operational_error import create_operational_error
from app.shared.profile_identity import ProfileComponent


# Vocabulario cerrado de la orientación de un formato (no son nombres de formato).
PORTRAIT = "portrait"
LANDSCAPE = "landscape"
FORMAT_ORIENTATIONS = (PORTRAIT, LANDSCAPE)


def fallback_label(profile_format):
    """Etiqueta de un formato descubierto sin declaración."""
    return profile_format.replace("_", " ").title()


@dataclass(frozen=True)
class SceneSeconds:
    """Duración de cada escena del storyboard, en segundos.

    Las escenas se cortan al final de una frase y duran entre min y max;
    mejor, entre target_min y target_max.
    """

    min: float
    target_min: float
    target_max: float
    max: float


@dataclass(frozen=True)
class FormatDeclaration:
    display_name: str
    order: int
    orientation: str | None = None
    image_guidance: str | None = None
    scene_seconds: SceneSeconds | None = None


class FormatCatalog:
    """Presenta y describe los formatos descubiertos según config/formats.json.

    Un formato declarado sale con su display_name y en su order. Uno
    descubierto sin declaración sale con fallback_label y detrás de los
    declarados, por orden alfabético. Sin el archivo, todos salen así.
    orientation (portrait o landscape), image_guidance y scene_seconds son
    opcionales: sin orientation no se comprueba la orientación de sus
    perfiles, sin image_guidance sus imágenes no se pueden generar y sin
    scene_seconds no se puede hacer su storyboard. Nunca decide qué formatos
    existen.

    Leer el archivo no depende de ProfileResolver (que lo usa para la
    orientación); la comprobación de carpetas, validate, recibe el resolver.
    """

    def __init__(self, catalog_path=Path("config/formats.json")):
        self.catalog_path = Path(catalog_path)
        self._declarations = None

    def label(self, profile_format):
        declaration = self._load().get(profile_format)
        if declaration is None:
            return fallback_label(profile_format)
        return declaration.display_name

    def ordered(self, profile_formats):
        declarations = self._load()

        def sort_key(profile_format):
            declaration = declarations.get(profile_format)
            if declaration is None:
                return (1, 0, profile_format)
            return (0, declaration.order, profile_format)

        return tuple(sorted(profile_formats, key=sort_key))

    def orientation(self, profile_format):
        """Orientación declarada del formato, o None si no la declara."""
        declaration = self._load().get(profile_format)
        if declaration is None:
            return None
        return declaration.orientation

    def image_guidance(self, profile_format):
        """Guía de formato que se añade al prompt de cada imagen."""
        declaration = self._load().get(profile_format)
        if declaration is not None and declaration.image_guidance is not None:
            return declaration.image_guidance
        error = ValueError(
            f"Sin formats.{profile_format}.image_guidance."
        )
        raise create_operational_error(
            family="CONFIG",
            user_message=(
                "El catálogo de formatos no declara la guía de imagen "
                f"(image_guidance) del formato «{profile_format}»."
            ),
            recommended_action=(
                "Declare el formato en el catálogo de formatos con "
                "image_guidance (texto)."
            ),
            operation="Leer catálogo de formatos",
            resource=str(self.catalog_path),
        ) from error

    def scene_seconds(self, profile_format):
        """Duración de las escenas del storyboard de ese formato."""
        declaration = self._load().get(profile_format)
        if declaration is not None and declaration.scene_seconds is not None:
            return declaration.scene_seconds
        error = ValueError(
            f"Sin formats.{profile_format}.scene_seconds."
        )
        raise create_operational_error(
            family="CONFIG",
            user_message=(
                "El catálogo de formatos no declara la duración de las "
                f"escenas (scene_seconds) del formato «{profile_format}»."
            ),
            recommended_action=(
                "Declare en el formato scene_seconds con min, target_min, "
                "target_max y max (segundos)."
            ),
            operation="Leer catálogo de formatos",
            resource=str(self.catalog_path),
        ) from error

    def validate(self, profile_resolver):
        """Lee el catálogo y exige carpeta de perfiles a cada formato declarado.

        Se llama una vez al arrancar, antes del primer menú.
        """
        declarations = self._load()
        discovered = {
            profile_format
            for component in ProfileComponent
            for profile_format in profile_resolver.discover_formats(component)
        }
        undiscovered = sorted(set(declarations) - discovered)
        if not undiscovered:
            return
        profiles_root = Path(profile_resolver.profiles_root)
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
                f"{profiles_root.as_posix()}/<componente>/ o quite "
                "su declaración del catálogo de formatos."
            ),
            operation="Leer catálogo de formatos",
            resource=str(self.catalog_path),
            technical_metadata={
                "formats": undiscovered,
                "profiles_root": str(profiles_root),
            },
        ) from error

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
            return {
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

    @staticmethod
    def _declaration(formats, profile_format):
        path = f"formats.{profile_format}"
        declaration = require_mapping(formats, profile_format, path)
        display_name = require_text(
            declaration,
            "display_name",
            f"{path}.display_name",
        )
        order = require_int(declaration, "order", f"{path}.order")
        orientation = declaration.get("orientation")
        if orientation is not None and orientation not in FORMAT_ORIENTATIONS:
            raise ValueError(
                f"La configuración {path}.orientation debe ser "
                f"{' o '.join(FORMAT_ORIENTATIONS)}."
            )
        return FormatDeclaration(
            display_name=display_name,
            order=order,
            orientation=orientation,
            image_guidance=(
                require_text(
                    declaration,
                    "image_guidance",
                    f"{path}.image_guidance",
                )
                if "image_guidance" in declaration
                else None
            ),
            scene_seconds=(
                _scene_seconds(declaration, f"{path}.scene_seconds")
                if "scene_seconds" in declaration
                else None
            ),
        )


def _scene_seconds(declaration, path):
    values = require_mapping(declaration, "scene_seconds", path)
    seconds = SceneSeconds(
        **{
            key: require_float(values, key, f"{path}.{key}")
            for key in ("min", "target_min", "target_max", "max")
        }
    )
    if not (
        0 < seconds.min <= seconds.target_min
        <= seconds.target_max <= seconds.max
    ):
        raise ValueError(
            f"La configuración {path} debe cumplir "
            "0 < min <= target_min <= target_max <= max."
        )
    return seconds
