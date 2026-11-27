"""Opciones comunes reutilizables para los flujos de ejecución."""

import json
from pathlib import Path

from app.modules.audio.tts_contracts import TtsVoiceConfigurationError
from app.modules.audio.voice_configuration import load_tts_voice_configuration
from app.shared.operational_error import create_operational_error


class CommonOptions:
    """Compone opciones generales sobre la primitive de terminal."""

    def __init__(
        self,
        terminal,
        on_cancel,
        voice_configs_path=Path("config/voice_configs"),
    ):
        self._terminal = terminal
        self._on_cancel = on_cancel
        self._voice_configs_path = voice_configs_path

    def _write(self, message, writer):
        (writer or self._terminal.write)(message)

    def _select(self, items, selector):
        if selector is not None:
            return selector(items)
        return self._terminal.select_from_list(items, self._on_cancel)

    def select_voice_config(self, writer=None, selector=None):
        configs = sorted(self._voice_configs_path.glob("*.json"))
        if not configs:
            raise FileNotFoundError(
                "No se encontraron configuraciones en "
                "config/voice_configs."
            )

        # Declared menu_order first (presentation only); the rest after, in
        # file-name order. sorted() is stable, so ties keep file-name order.
        entries = sorted(
            ((config, self._voice_configuration(config)) for config in configs),
            key=lambda entry: (
                entry[1].menu_order is None,
                entry[1].menu_order or 0,
            ),
        )
        options = tuple(
            (config, configuration.display_name)
            for config, configuration in entries
        )
        self._write("\nVOZ\n", writer)
        for index, (_, display_name) in enumerate(options, start=1):
            self._write(f"{index}. {display_name}", writer)
        return self._select(tuple(config for config, _ in options), selector).stem

    @staticmethod
    def _voice_configuration(config: Path):
        """Read presentation data from the canonical neutral voice document."""
        with config.open(encoding="utf-8") as voice_config_file:
            document = json.load(voice_config_file)
        try:
            return load_tts_voice_configuration(document)
        except TtsVoiceConfigurationError as error:
            raise create_operational_error(
                family="CONFIG",
                user_message=(
                    "La configuración de la voz no es válida: "
                    f"en «{config.as_posix()}», {error}"
                ),
                recommended_action=f"Corrige «{config.as_posix()}».",
                operation="Elegir la voz",
                resource=config.as_posix(),
            ) from error

    def select_music_category(self, writer=None, selector=None):
        options = ["random", None]
        self._write("\nMÚSICA\n", writer)
        self._write("1. Aleatoria", writer)
        self._write("2. Sin música", writer)
        return self._select(options, selector)

    def select_overlays_mode(self, writer=None, selector=None):
        options = ["on", "off"]
        self._write("\nOVERLAYS\n", writer)
        self._write("1. Sí", writer)
        self._write("2. No", writer)
        return self._select(options, selector)

    def ask_project_name(self, writer=None):
        self._write("\nPROYECTO\n", writer)
        while True:
            name = self._terminal.read("Nombre: ").strip()
            if name == "0":
                self._on_cancel()
            if name:
                return name
            self._write("\nOpción no válida.", writer)

    def ask_existing_project(self, project_name, writer=None):
        """True to overwrite the existing project, False to choose another name."""
        self._write(f"\nEl proyecto «{project_name}» ya existe.\n", writer)
        self._write("1. Sobrescribir", writer)
        self._write("2. Poner otro nombre", writer)
        while True:
            option = self._terminal.read("\n> ").strip()
            if option == "0":
                self._on_cancel()
            if option == "1":
                return True
            if option == "2":
                return False
            self._write("\nOpción no válida.", writer)
