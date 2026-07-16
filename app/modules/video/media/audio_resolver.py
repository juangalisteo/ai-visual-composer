from pathlib import Path


class AudioResolver:

    def resolve(
        self,
        project,
        audio_path=None
    ):
        if audio_path is not None:

            resolved_path = Path(
                audio_path
            )

            if not resolved_path.exists():
                raise FileNotFoundError(
                    f"No existe el audio: "
                    f"{resolved_path}"
                )

            return resolved_path

        final_audio = (
            project.final_audio_path()
        )

        if final_audio.exists():
            return final_audio

        voice_audio = (
            project.audio_path()
        )

        if voice_audio.exists():
            return voice_audio

        raise FileNotFoundError(
            "No existe audio_final.mp3 ni voz.mp3 "
            "para generar el vídeo."
        )