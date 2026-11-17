"""Contratos inmutables para las selecciones explícitas de STUDIO.

Este módulo solo transporta resultados ya resueltos. ``RunController`` hace
la selección y, con estos resultados, construye la petición STUDIO.
"""

from dataclasses import dataclass

from app.modules.studio.profile import StudioProfile
from app.shared.profile_identity import OperationalProfileKey
from app.shared.subtitle_profile_identity import SubtitleProfileKey


@dataclass(frozen=True)
class StudioOperationalSelection:
    """Resultado operacional ya resuelto para una ejecución STUDIO."""

    operational_key: OperationalProfileKey
    studio_profile: StudioProfile


@dataclass(frozen=True)
class StudioSubtitleSelection:
    """Resultado de subtítulos ya resuelto para una ejecución STUDIO."""

    subtitle_key: SubtitleProfileKey
    subtitle_original: bool


@dataclass(frozen=True)
class StudioProfileSelection:
    """Composición explícita de las selecciones operacional y de subtítulos."""

    operational: StudioOperationalSelection
    subtitle: StudioSubtitleSelection
