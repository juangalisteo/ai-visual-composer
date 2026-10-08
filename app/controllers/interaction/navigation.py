"""Selectores de navegación independientes del controlador principal."""

from app.modules.studio import (
    StudioInputMode,
    StudioSubtitleExportMode,
)


class Navigation:
    """Compone los menús simples sobre la primitive de terminal."""

    def __init__(self, terminal, on_cancel):
        self._terminal = terminal
        self._on_cancel = on_cancel

    def _write(self, message, writer):
        (writer or self._terminal.write)(message)

    def _select(self, items, selector):
        if selector is not None:
            return selector(items)
        return self._terminal.select_from_list(items, self._on_cancel)

    def select_visual_pipeline(self, writer=None, selector=None):
        pipelines = [
            {"name": "Guion", "pipeline": "script"},
            {"name": "Imagen", "pipeline": "image"},
            {"name": "Video", "pipeline": "video"},
            {"name": "Studio", "pipeline": "studio"},
        ]
        self._write("\nAI VISUAL COMPOSER\n", writer)
        for index, pipeline in enumerate(pipelines, start=1):
            self._write(f"{index}. {pipeline['name']}", writer)

        while True:
            selected = self._select(pipelines, selector)
            if selected.get("available", True):
                return selected["pipeline"]
            self._write("\nNo disponible.", writer)

    def select_script_destination(self, writer=None, selector=None):
        destinations = [
            {"name": "Imagen", "pipeline": "image"},
            {"name": "Video", "pipeline": "video"},
            {"name": "Diseño", "pipeline": "design"},
        ]
        self._write("\nDESTINO\n", writer)
        for index, destination in enumerate(destinations, start=1):
            self._write(f"{index}. {destination['name']}", writer)

        while True:
            selected = self._select(destinations, selector)
            if selected.get("available", True):
                return selected["pipeline"]
            self._write("\nNo disponible.", writer)

    def select_design_target(self, writer=None, selector=None):
        targets = [
            {"name": "Imagen", "pipeline": "image"},
            {"name": "Video", "pipeline": "video"},
        ]

        while True:
            self._write("\nDISEÑO\n", writer)
            for index, target in enumerate(targets, start=1):
                self._write(f"{index}. {target['name']}", writer)

            selected = self._select(targets, selector)
            if selected.get("available", True):
                return selected["pipeline"]
            self._write("\nNo disponible.", writer)

    def select_pipeline_mode(
        self,
        include_full_without_subtitles=False,
        writer=None,
        selector=None,
    ):
        modes = [
            {"name": "Proyecto completo", "mode": "full"},
            {"name": "Solo audio", "mode": "audio"},
            {"name": "Audio + subtítulos", "mode": "subtitles"},
            {
                "name": "Audio + subtítulos + storyboard",
                "mode": "storyboard",
            },
        ]
        if include_full_without_subtitles:
            modes.append({
                "name": "Proyecto completo sin subtítulos",
                "mode": "full_without_subtitles",
            })

        self._write("\nMODO\n", writer)
        for index, mode in enumerate(modes, start=1):
            self._write(f"{index}. {mode['name']}", writer)
        return self._select(modes, selector)["mode"]

    def select_studio_input_mode(self, writer=None, selector=None):
        modes = (
            StudioInputMode.VIDEO.value,
            StudioInputMode.SRT_VIDEO.value,
            StudioInputMode.INTRO_OUTRO.value,
            StudioInputMode.MONTAJE_VIDEOS.value,
            StudioInputMode.VIDEO_AUDIO_SRT.value,
            StudioInputMode.EXPORTAR_SRT.value,
        )
        self._write("\nENTRADA\n", writer)
        self._write("1. SOLO VIDEO", writer)
        self._write("2. SRT + VIDEO", writer)
        self._write("3. INTRO / OUTRO", writer)
        self._write("4. MONTAJE VÍDEOS", writer)
        self._write("5. VIDEO + AUDIO | SRT", writer)
        self._write("6. EXPORTAR SRT ➜  VIDEO", writer)
        return self._select(modes, selector)

    def select_studio_subtitle_export_mode(self, writer=None, selector=None):
        modes = (
            StudioSubtitleExportMode.TRANSCRIBIR,
            StudioSubtitleExportMode.CONVERTIR,
        )
        self._write("\nMODO\n", writer)
        self._write("1. TRANSCRIBIR", writer)
        self._write("2. CONVERTIR", writer)
        return self._select(modes, selector)

    def select_studio_montage_transitions(self, writer=None, selector=None):
        self._write("\nTRANSICIONES\n", writer)
        self._write("1. Sí", writer)
        self._write("2. No", writer)
        return self._select((True, False), selector)
