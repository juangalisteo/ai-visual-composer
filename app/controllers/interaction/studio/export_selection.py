"""Selección de fuentes para la exportación de subtítulos STUDIO."""

from app.modules.studio import StudioSubtitleExportMode


class StudioExportSelection:
    def __init__(self, input_service, resource_selection):
        self._input_service = input_service
        self._resource_selection = resource_selection

    def select_plan(self, export_mode, writer=None, selector=None):
        candidates = self._input_service.discover(export_mode)
        label = (
            "MEDIA"
            if candidates.mode is StudioSubtitleExportMode.TRANSCRIBIR
            else "SRT"
        )
        source_path = self._resource_selection.select_studio_input_candidate(
            label,
            candidates.sources,
            direct=len(candidates.sources) == 1,
            writer=writer,
            selector=selector,
        )
        return self._input_service.prepare(
            candidates.mode,
            source_path=source_path,
        )
