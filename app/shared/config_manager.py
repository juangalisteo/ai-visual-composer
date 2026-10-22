import json
from pathlib import Path

from app.modules.audio.voice_configuration import load_tts_voice_configuration
from app.shared.profile_identity import OperationalProfileKey
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
        """Return the injected operational identity, or None without one."""
        return self._operational_profile_key

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
