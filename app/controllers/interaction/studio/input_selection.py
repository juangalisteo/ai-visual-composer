"""Preparación de entradas VIDEO y SRT + VIDEO de STUDIO."""

from app.modules.studio import StudioInputMode


class StudioInputSelection:
    def __init__(self, preparation_service, resource_selection):
        self._preparation_service = preparation_service
        self._resource_selection = resource_selection

    def select_files(self, profile, input_mode, writer=None, selector=None):
        candidates = self._preparation_service.discover(profile, input_mode)
        if candidates.mode is StudioInputMode.VIDEO:
            video_path = self._resource_selection.select_studio_input_candidate(
                "VIDEO",
                candidates.videos,
                direct=len(candidates.videos) == 1,
                writer=writer,
                selector=selector,
            )
            return self._preparation_service.prepare(
                profile,
                candidates.mode,
                video_path=video_path,
            )

        direct = (
            len(candidates.videos) == 1
            and len(candidates.subtitles) == 1
        )
        video_path = self._resource_selection.select_studio_input_candidate(
            "VIDEO",
            candidates.videos,
            direct=direct,
            writer=writer,
            selector=selector,
        )
        subtitle_path = self._resource_selection.select_studio_input_candidate(
            "SRT",
            candidates.subtitles,
            direct=direct,
            writer=writer,
            selector=selector,
        )
        return self._preparation_service.prepare(
            profile,
            candidates.mode,
            video_path=video_path,
            subtitle_path=subtitle_path,
        )
