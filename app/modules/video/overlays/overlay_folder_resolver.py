from dataclasses import dataclass
from pathlib import Path

import requests

from app.shared.config_manager import ConfigManager
from app.shared.operation_warnings import OperationWarning, OperationWarnings


@dataclass(frozen=True)
class OverlayCategoryResolution:

    primary: str | None = None
    secondary: tuple[str, ...] = ()

    @property
    def thematic_folders(
        self
    ):
        folders = []

        if self.primary:
            folders.append(
                self.primary
            )

        folders.extend(
            self.secondary
        )

        return tuple(
            folders
        )


class OverlayFolderResolver:

    def __init__(
        self,
        provider=None,
        warnings=None,
    ):
        self.provider = provider
        self.warnings = warnings

    def discover_valid_folders(
        self,
        directory,
        extensions,
        types=()
    ):
        root = Path(
            directory
        )

        if not root.exists() or not root.is_dir():
            return ()

        valid_folders = []

        for folder in sorted(
            (
                path
                for path in root.iterdir()
                if path.is_dir()
            ),
            key=lambda path: path.name.lower()
        ):
            if self._folder_has_valid_assets(
                root_directory=root,
                folder=folder,
                extensions=extensions,
                types=types
            ):
                valid_folders.append(
                    folder.name
                )

        return tuple(
            valid_folders
        )

    def resolve(
        self,
        topic,
        folders
    ):
        return (
            self.resolve_categories(
                topic=topic,
                folders=folders
            )
            .primary
        )

    def resolve_categories(
        self,
        topic,
        folders
    ):
        topic = str(
            topic or ""
        ).strip()

        folders = tuple(
            folder
            for folder in folders
            if str(folder).strip()
        )

        if not topic or not folders:
            return OverlayCategoryResolution()

        try:
            response = (
                self._provider()
                .generate(
                    self._build_prompt(
                        topic=topic,
                        folders=folders
                    )
                )
            )
        except Exception as error:
            self._record_provider_degradation(error)
            return OverlayCategoryResolution()

        return self._validate_response(
            response=response,
            folders=folders
        )

    def _record_provider_degradation(self, error):
        """Keep the neutral fallback while exposing the omitted capability."""
        warning = OperationWarning(
            family="DEGRADATION",
            user_message=(
                "Los overlays tem\u00e1ticos por IA fueron omitidos; el video "
                "contin\u00faa sin esa capacidad."
            ),
            recommended_action=(
                "Revisa la disponibilidad del servicio de IA si necesitas "
                "overlays tem\u00e1ticos."
            ),
            operation="Resolver categor\u00edas de overlays IA",
            technical_metadata={
                "cause_type": type(error).__name__,
                "source": "overlay_folder_resolver",
            },
        )
        if isinstance(self.warnings, OperationWarnings):
            self.warnings.add(warning)

    def _provider(
        self
    ):
        if self.provider is not None:
            return self.provider

        ai_config = (
            ConfigManager()
            .get_ai_config()
        )

        return _OverlayOllamaProvider(
            model=ai_config["model"]
        )

    def _build_prompt(
        self,
        topic,
        folders
    ):
        folder_lines = "\n".join(
            f"- {folder}"
            for folder in folders
        )

        return (
            "Selecciona categorias de overlays solo si "
            "existe una relacion tematica clara y directa "
            "con el tema.\n"
            "No incluyas categorias unicamente para aportar "
            "variedad visual.\n\n"
            "TEMA:\n"
            f"{topic}\n\n"
            "CATEGORIAS TEMATICAS DISPONIBLES:\n"
            f"{folder_lines}\n\n"
            "Si ninguna categoria encaja claramente, devuelve "
            "exactamente:\n"
            "PRIMARY: NONE\n"
            "SECONDARY: NONE\n\n"
            "Si hay categorias relacionadas, devuelve exactamente:\n"
            "PRIMARY: nombre exacto de una categoria disponible\n"
            "SECONDARY: nombres exactos de cero o mas categorias "
            "disponibles separados por coma, o NONE\n\n"
            "No expliques.\n"
            "No inventes categorias.\n"
            "No uses categorias que no aparezcan en la lista.\n"
        )

    def _validate_response(
        self,
        response,
        folders
    ):
        response = str(
            response or ""
        ).strip()

        if not response:
            return OverlayCategoryResolution()

        if response == "NONE":
            return OverlayCategoryResolution()

        valid_folders = {
            folder: folder
            for folder in folders
        }

        if response in valid_folders:
            return OverlayCategoryResolution(
                primary=valid_folders[
                    response
                ]
            )

        values = self._parse_structured_response(
            response
        )

        if values is None:
            return OverlayCategoryResolution()

        primary_value = values[
            "primary"
        ]
        secondary_values = values[
            "secondary"
        ]

        if primary_value == "NONE":
            return OverlayCategoryResolution()

        primary = valid_folders.get(
            primary_value
        )

        if primary is None:
            return OverlayCategoryResolution()

        secondary = []

        for value in secondary_values:
            folder = valid_folders.get(
                value
            )

            if (
                folder is None
                or folder == primary
                or folder in secondary
            ):
                continue

            secondary.append(
                folder
            )

        return OverlayCategoryResolution(
            primary=primary,
            secondary=tuple(
                secondary
            )
        )

    def _parse_structured_response(
        self,
        response
    ):
        lines = [
            line.strip()
            for line in response.splitlines()
            if line.strip()
        ]

        if len(lines) != 2:
            return None

        values = {}

        for line in lines:
            if ":" not in line:
                return None

            key, value = line.split(
                ":",
                1
            )

            key = key.strip().upper()
            value = value.strip()

            if key not in {
                "PRIMARY",
                "SECONDARY"
            }:
                return None

            values[key.lower()] = value

        if set(values) != {
            "primary",
            "secondary"
        }:
            return None

        secondary_value = values[
            "secondary"
        ]

        if secondary_value == "NONE":
            secondary = []
        else:
            secondary = [
                item.strip()
                for item in (
                    secondary_value.split(
                        ","
                    )
                )
                if item.strip()
            ]

        return {
            "primary": values["primary"],
            "secondary": secondary
        }

    def _folder_has_valid_assets(
        self,
        root_directory,
        folder,
        extensions,
        types
    ):
        allowed_extensions = {
            extension.lower()
            for extension in extensions
        }

        allowed_types = {
            item.lower()
            for item in types
        }

        for path in folder.iterdir():
            if not path.is_file():
                continue

            if (
                path.suffix.lower()
                not in allowed_extensions
            ):
                continue

            if allowed_types:
                relative_name = (
                    path.relative_to(
                        root_directory
                    )
                    .as_posix()
                    .lower()
                )

                if (
                    path.name.lower()
                    not in allowed_types
                    and relative_name
                    not in allowed_types
                ):
                    continue

            return True

        return False


class _OverlayOllamaProvider:

    def __init__(
        self,
        model
    ):
        self.url = "http://localhost:11434/api/generate"
        self.model = model

    def generate(
        self,
        prompt
    ):
        response = requests.post(
            self.url,
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
        )

        response.raise_for_status()

        return response.json()["response"]
