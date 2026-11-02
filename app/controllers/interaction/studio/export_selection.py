"""Selección de fuentes para la exportación de subtítulos STUDIO."""

from app.modules.studio import (
    SRT_INPUT_ACTION,
    StudioInputMode,
    StudioSubtitleExportInputError,
    StudioSubtitleExportMode,
    to_studio_operational_error,
)


class StudioExportSelection:
    def __init__(self, input_service, resource_selection):
        self._input_service = input_service
        self._resource_selection = resource_selection

    def select_plan(self, export_mode, writer=None, selector=None):
        """Report a missing or invalid source file as an input error."""
        try:
            return self._select_plan(export_mode, writer, selector)
        except StudioSubtitleExportInputError as error:
            raise to_studio_operational_error(
                error,
                mode=StudioInputMode.EXPORTAR_SRT.value,
                recommended_action=(
                    "Pon en esa carpeta el vídeo .mp4 o el audio .mp3 que "
                    "quieres transcribir y vuelve a intentarlo."
                    if export_mode is StudioSubtitleExportMode.TRANSCRIBIR
                    else SRT_INPUT_ACTION
                ),
            ) from error

    def _select_plan(self, export_mode, writer, selector):
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
