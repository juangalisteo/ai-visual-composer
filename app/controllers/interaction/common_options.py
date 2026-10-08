"""Opciones comunes reutilizables para los flujos de ejecución."""

from pathlib import Path

from app.controllers.interaction import labels


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

    def select_voice_config(self, writer=None, selector=None, voice_label=None):
        configs = sorted(self._voice_configs_path.glob("*.json"))
        if not configs:
            raise FileNotFoundError(
                "No se encontraron configuraciones en "
                "config/voice_configs."
            )

        voice_label = voice_label or labels.voice_label
        self._write("\nVOZ\n", writer)
        for index, config in enumerate(configs, start=1):
            self._write(f"{index}. {voice_label(config.stem)}", writer)
        return self._select(configs, selector).stem

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

    def ask_clear_output(self, writer=None):
        self._write("\nELIMINAR OUTPUT\n", writer)
        self._write("1. Sí", writer)
        self._write("2. No", writer)
        while True:
            option = self._terminal.read("\n> ").strip()
            if option == "0":
                self._on_cancel()
            if option == "1":
                return True
            if option == "2":
                return False
            self._write("\nOpción no válida.", writer)
