"""Selección de entradas y plan VIDEO + AUDIO + SRT de STUDIO."""

from dataclasses import replace

from app.modules.studio import (
    SRT_INPUT_ACTION,
    StudioInputMode,
    StudioVideoAudioSrtInputError,
    to_studio_operational_error,
)


_MODE = StudioInputMode.VIDEO_AUDIO_SRT
_MEDIA_INPUT_ACTION = (
    f"Pon en esa carpeta el vídeo .mp4 y el audio que pide {_MODE.label} y "
    "vuelve a intentarlo."
)


def _input_error(error, recommended_action):
    return to_studio_operational_error(
        error,
        mode=_MODE.value,
        recommended_action=recommended_action,
    )


class StudioVideoAudioSrtSelection:
    def __init__(
        self,
        input_service,
        resource_selection,
        media_probe,
        music_selector,
    ):
        self._input_service = input_service
        self._resource_selection = resource_selection
        self._media_probe = media_probe
        self._music_selector = music_selector

    def select_inputs(self, writer=None, selector=None):
        try:
            candidates = self._input_service.discover(False)
        except StudioVideoAudioSrtInputError as error:
            raise _input_error(error, _MEDIA_INPUT_ACTION) from error
        return (
            self._resource_selection.select_studio_input_candidate(
                "VIDEO",
                candidates.videos,
                direct=len(candidates.videos) == 1,
                writer=writer,
                selector=selector,
            ),
            self._resource_selection.select_studio_input_candidate(
                "AUDIO",
                candidates.audios,
                direct=len(candidates.audios) == 1,
                writer=writer,
                selector=selector,
            ),
        )

    def select_subtitle(self, writer=None, selector=None):
        try:
            candidates = self._input_service.discover(True)
        except StudioVideoAudioSrtInputError as error:
            raise _input_error(error, SRT_INPUT_ACTION) from error
        return self._resource_selection.select_studio_input_candidate(
            "SRT",
            candidates.subtitles,
            direct=len(candidates.subtitles) == 1,
            writer=writer,
            selector=selector,
        )

    def select_plan(
        self,
        subtitles,
        video_path=None,
        audio_path=None,
        subtitle_path=None,
        select_inputs=None,
        select_subtitle=None,
    ):
        if video_path is None or audio_path is None:
            video_path, audio_path = select_inputs()
        if subtitles and subtitle_path is None:
            subtitle_path = select_subtitle()
        try:
            return self._input_service.create_plan(
                subtitles,
                video_path=video_path,
                audio_path=audio_path,
                subtitle_path=subtitle_path,
            )
        except StudioVideoAudioSrtInputError as error:
            raise _input_error(error, _MEDIA_INPUT_ACTION) from error

    def select_audio_tail(self, plan, writer=None, selector=None):
        video_duration = self._media_probe.inspect(plan.video_path).duration
        audio_duration = self._media_probe.get_duration(plan.audio_path)
        if audio_duration >= video_duration:
            return replace(
                plan,
                video_duration=video_duration,
                audio_duration=audio_duration,
            )

        (writer or (lambda message: None))(
            "\nAUDIO MÁS CORTO QUE EL VÍDEO\n"
        )
        (writer or (lambda message: None))("1. SIN MÚSICA")
        (writer or (lambda message: None))("2. CON MÚSICA")
        mode = selector(("silence", "music"))
        music_path = (
            self._music_selector.select("random")
            if mode == "music"
            else None
        )
        return replace(
            plan,
            audio_tail_mode=mode,
            music_path=music_path,
            video_duration=video_duration,
            audio_duration=audio_duration,
        )
