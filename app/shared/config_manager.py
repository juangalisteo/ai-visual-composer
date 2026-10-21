import json
import os
from pathlib import Path

from app.modules.audio.voice_configuration import load_tts_voice_configuration
from app.shared.profile_identity import OperationalProfileKey, ProfileKey
from app.shared.profile_resolver import ProfileResolver
from app.shared.operational_error import create_operational_error
from app.shared.subtitle_profile_resolver import (
    SubtitleProfileResolver,
)
from app.shared.subtitle_profile_identity import SubtitleProfileKey


class ConfigManager:

    def __init__(
        self,
        profile_resolver=None,
        subtitle_profile_resolver=None,
        operational_profile_key: OperationalProfileKey | None = None,
        voice_config_id: str | None = None,
    ):
        if (
            operational_profile_key is not None
            and not isinstance(operational_profile_key, OperationalProfileKey)
        ):
            raise TypeError(
                "operational_profile_key debe ser OperationalProfileKey o None."
            )
        if voice_config_id is not None:
            if not isinstance(voice_config_id, str):
                raise TypeError("voice_config_id debe ser texto o None.")
            voice_config_id = voice_config_id.strip()
            if not voice_config_id:
                raise ValueError("voice_config_id no puede estar vacio.")
        self.config_path = Path("config")
        self._operational_profile_key = operational_profile_key
        self._voice_config_id = voice_config_id
        self.profile_resolver = (
            profile_resolver
            or ProfileResolver(
                self.config_path / "profiles"
            )
        )
        self.subtitle_profile_resolver = (
            subtitle_profile_resolver
            or SubtitleProfileResolver(
                self.config_path / "profiles"
            )
        )

    def load_json(self, path):
        path = Path(path)
        try:
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError as error:
            raise create_operational_error(
                family="CONFIG",
                user_message="No se encontró el archivo de configuración requerido.",
                recommended_action="Revise que el archivo exista y vuelva a intentarlo.",
                operation="Cargar configuración",
                resource=str(path),
            ) from error
        except json.JSONDecodeError as error:
            raise create_operational_error(
                family="CONFIG",
                user_message="El archivo de configuración no contiene JSON válido.",
                recommended_action="Corrija el JSON indicado y vuelva a intentarlo.",
                operation="Cargar configuración",
                resource=str(path),
                technical_metadata={
                    "line": error.lineno,
                    "column": error.colno,
                },
            ) from error
        except OSError as error:
            raise create_operational_error(
                family="FILESYSTEM",
                user_message="No se pudo leer el archivo de configuración.",
                recommended_action="Revise la ruta, permisos y disponibilidad del archivo.",
                operation="Cargar configuración",
                resource=str(path),
            ) from error

    def get_ai_config(self):
        return self.load_json(self.config_path / "ai.json")

    def get_tts_voice_configuration(self):
        """Load the canonical, backend-neutral configuration of one voice."""
        return load_tts_voice_configuration(
            self._voice_config_document()
        )

    def _voice_config_document(self):
        selected_voice_config = self._voice_config_id
        if selected_voice_config is None:
            selected_voice_config = os.environ.get("MC_VOICE_CONFIG")

            if not selected_voice_config:
                selected_voice_config = "piper_davefx"

        voice_config_path = (
            self.config_path
            / "voice_configs"
            / f"{selected_voice_config}.json"
        )

        return self.load_json(voice_config_path)

    def get_profile_config(self):
        profile_key = self.get_operational_profile_key()
        if profile_key is not None:
            return self.profile_resolver.load_operational(profile_key)

        raise create_operational_error(
            family="CONFIG",
            user_message="Falta la identidad estructurada de perfil.",
            recommended_action=(
                "Configure component, platform y profile_id antes de iniciar "
                "la operación."
            ),
            operation="Resolver configuración de perfil",
        )

    def get_operational_profile_key(self):
        """Read canonical operational identity without subtitle family."""
        if self._operational_profile_key is not None:
            return self._operational_profile_key

        values = (
            os.environ.get("MC_PROFILE_COMPONENT", "").strip(),
            os.environ.get("MC_PROFILE_PLATFORM", "").strip(),
            os.environ.get("MC_PROFILE_ID", "").strip(),
        )
        if not any(values):
            return None
        if not all(values):
            raise create_operational_error(
                family="CONFIG",
                user_message="La identidad operacional esta incompleta.",
                recommended_action=(
                    "Configure component, platform y profile_id antes de "
                    "iniciar la operacion."
                ),
                operation="Leer identidad operacional",
                technical_metadata={
                    "component_present": bool(values[0]),
                    "platform_present": bool(values[1]),
                    "profile_id_present": bool(values[2]),
                },
            )
        try:
            return OperationalProfileKey(*values)
        except (TypeError, ValueError) as error:
            raise create_operational_error(
                family="CONFIG",
                user_message="La identidad operacional configurada no es valida.",
                recommended_action=(
                    "Revise component, platform y profile_id de la "
                    "configuracion activa."
                ),
                operation="Leer identidad operacional",
                resource="MC_PROFILE_COMPONENT/MC_PROFILE_PLATFORM/MC_PROFILE_ID",
            ) from error

    def _get_legacy_subtitle_parent_key(self):
        """Build the isolated parent identity required by legacy subtitles.

        This is not an operational-profile lookup: `family` exists here only
        because old subtitle-selection inputs do not transport a complete
        `SubtitleProfileKey` yet.
        """
        if self._operational_profile_key is not None:
            family = (
                os.environ.get("MC_PROFILE_FAMILY", "estandar").strip()
                or "estandar"
            )
            # LEGACY_ADAPTER: only the historic subtitle-style input still
            # needs a family-bearing parent key. Its operational identity is
            # the explicit injected value, never the MC_PROFILE_* bridge.
            if family.casefold() == "system":
                family = "estandar"
            return ProfileKey(
                component=self._operational_profile_key.component,
                platform=self._operational_profile_key.platform,
                profile_id=self._operational_profile_key.profile_id,
                family=family,
            )

        values = (
            os.environ.get(
                "MC_PROFILE_COMPONENT",
                ""
            ).strip(),
            os.environ.get(
                "MC_PROFILE_PLATFORM",
                ""
            ).strip(),
            os.environ.get(
                "MC_PROFILE_ID",
                ""
            ).strip(),
            os.environ.get("MC_PROFILE_FAMILY", "estandar").strip() or "estandar",
        )

        if not any(values[:3]):
            return None
        if not all(values[:3]):
            raise create_operational_error(
                family="CONFIG",
                user_message="La identidad padre de subtítulos está incompleta.",
                recommended_action=(
                    "Configure component, platform y profile_id antes de "
                    "iniciar la operación."
                ),
                operation="Adaptar selección legacy de subtítulos",
                technical_metadata={
                    "component_present": bool(values[0]),
                    "platform_present": bool(values[1]),
                    "profile_id_present": bool(values[2]),
                },
            )

        # LEGACY_ADAPTER: persisted MC_PROFILE_FAMILY=system predates the
        # physical ESTANDAR family and is normalized at this input boundary.
        family = "estandar" if values[3].casefold() == "system" else values[3]
        try:
            return ProfileKey(
                component=values[0],
                platform=values[1],
                profile_id=values[2],
                family=family,
            )
        except (TypeError, ValueError) as error:
            raise create_operational_error(
                family="CONFIG",
                user_message="La identidad padre de subtítulos no es válida.",
                recommended_action=(
                    "Revise component, platform, family y profile_id de la "
                    "selección legacy de subtítulos."
                ),
                operation="Adaptar selección legacy de subtítulos",
                resource="MC_PROFILE_COMPONENT/MC_PROFILE_PLATFORM/MC_PROFILE_ID",
            ) from error

    def get_subtitle_profile_by_key(self, subtitle_profile_key):
        """Resolve a modern, complete subtitle identity without adaptation."""
        if not isinstance(subtitle_profile_key, SubtitleProfileKey):
            error = TypeError(
                "La ruta moderna requiere una SubtitleProfileKey completa."
            )
            raise create_operational_error(
                family="VALIDATION",
                user_message="La identidad de subtítulos no es válida.",
                recommended_action="Seleccione un perfil de subtítulos completo.",
                operation="Resolver perfil de subtítulos",
            ) from error
        return self.subtitle_profile_resolver.load(subtitle_profile_key)

    def adapt_legacy_subtitle_selection(self, selection):
        """Convert one legacy string/style input at the compatibility boundary."""
        profile_key = self._get_legacy_subtitle_parent_key()
        if profile_key is None:
            raise create_operational_error(
                family="CONFIG",
                user_message="Falta la identidad de perfil para resolver subtítulos.",
                recommended_action=(
                    "Configure component, platform y profile_id antes de "
                    "resolver subtítulos."
                ),
                operation="Resolver perfil de subtítulos",
            )
        return self.subtitle_profile_resolver.adapt_legacy_selection(
            profile_key=profile_key,
            selection=selection,
        )

    def get_subtitle_profile(self, selection, original=False):
        """Legacy public facade; modern callers use ``get_subtitle_profile_by_key``."""
        del original
        subtitle_profile_key = (
            selection
            if isinstance(selection, SubtitleProfileKey)
            else self.adapt_legacy_subtitle_selection(selection)
        )
        return self.get_subtitle_profile_by_key(subtitle_profile_key)
