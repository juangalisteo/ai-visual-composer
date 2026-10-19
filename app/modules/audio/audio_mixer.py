from pathlib import Path
import shutil
import subprocess
import time

from app.managers.project_manager import ProjectManager
from app.shared.media_probe import MediaProbe
from app.shared.progress_logger import ProgressLogger
from app.shared.operational_error import create_operational_error, summarize_technical_text


class AudioMixer:

    def __init__(
        self,
        music_volume=0.25,
        fade_in=1.0,
        fade_out=2.0
    ):
        self.music_volume = float(
            music_volume
        )

        self.fade_in = float(
            fade_in
        )

        self.fade_out = float(
            fade_out
        )

    def build(
        self,
        voice_path=None,
        music_path=None,
        output_path=None,
        project=None,
    ):
        ProgressLogger.start(
            "GENERANDO AUDIO"
        )

        start = time.perf_counter()

        if voice_path is None or output_path is None:
            project = project or ProjectManager()

        if voice_path is None:
            voice_path = project.audio_path()

        if output_path is None:
            output_path = (
                project.audio_dir()
                / "audio_final.mp3"
            )

        voice_path = Path(
            voice_path
        )

        output_path = Path(
            output_path
        )

        if not voice_path.exists():
            raise FileNotFoundError(
                f"No existe el audio de voz: "
                f"{voice_path}"
            )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if music_path is None:
            shutil.copy2(
                voice_path,
                output_path
            )

            self._validate_output(
                output_path
            )

            elapsed = (
                time.perf_counter()
                - start
            )

            ProgressLogger.finish(
                "Finalizado",
                elapsed
            )

            return output_path

        music_path = Path(
            music_path
        )

        if not music_path.exists():
            raise FileNotFoundError(
                f"No existe la pista musical: "
                f"{music_path}"
            )

        voice_duration = (
            MediaProbe.get_duration(
                voice_path
            )
        )

        fade_out_start = max(
            voice_duration
            - self.fade_out,
            0
        )

        filter_complex = (
            f"[1:a]"
            f"volume={self.music_volume},"
            f"afade=t=in:"
            f"st=0:"
            f"d={self.fade_in},"
            f"afade=t=out:"
            f"st={fade_out_start}:"
            f"d={self.fade_out},"
            f"atrim=duration={voice_duration},"
            f"asetpts=N/SR/TB"
            f"[music];"
            f"[0:a]"
            f"asetpts=N/SR/TB"
            f"[voice];"
            f"[voice][music]"
            f"amix=inputs=2:"
            f"duration=first:"
            f"dropout_transition=0"
            f"[audio]"
        )

        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(voice_path),
            "-stream_loop",
            "-1",
            "-i",
            str(music_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[audio]",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "192k",
            str(output_path)
        ]

        try:
            self._run_command(command)
        except RuntimeError as error:
            metadata = {
                "command": tuple(map(str, command)),
                "phase": "audio_mix",
                "voice_input": str(voice_path),
                "music_input": str(music_path),
            }
            returncode = getattr(error, "returncode", None)
            if returncode is not None:
                metadata["returncode"] = returncode
            stderr = summarize_technical_text(getattr(error, "stderr", None))
            if stderr:
                metadata["stderr_summary"] = stderr
            raise create_operational_error(
                family="AUDIO",
                user_message="FFmpeg no pudo mezclar la voz y la musica.",
                recommended_action="Comprueba los archivos de audio y el diagnostico del proceso.",
                operation="Mezclar voz y musica",
                resource=str(output_path),
                technical_metadata=metadata,
            ) from error

        self._validate_output(
            output_path
        )

        elapsed = (
            time.perf_counter()
            - start
        )

        ProgressLogger.finish(
            "Finalizado",
            elapsed
        )

        return output_path

    def _run_command(
        self,
        command
    ):
        result = subprocess.run(
            command,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            error = RuntimeError("Error al mezclar voz y música.")
            error.stderr = result.stderr
            error.returncode = result.returncode
            raise error

    def _validate_output(
        self,
        output_path
    ):
        if not output_path.exists():
            error = FileNotFoundError(
                "La generación de audio terminó, "
                "pero no se encontró el archivo: "
                f"{output_path}"
            )
            raise create_operational_error(
                family="VALIDATION",
                user_message="La mezcla terminó sin crear el audio esperado.",
                recommended_action="Revisa el resultado de FFmpeg y el directorio de salida.",
                operation="Validar mezcla de audio",
                resource=str(output_path),
            ) from error

        if output_path.stat().st_size <= 0:
            error = RuntimeError(
                "El archivo de audio generado "
                "está vacío."
            )
            raise create_operational_error(
                family="VALIDATION",
                user_message="La mezcla generó un archivo de audio vacío.",
                recommended_action="Revisa el resultado de FFmpeg y vuelve a intentarlo.",
                operation="Validar mezcla de audio",
                resource=str(output_path),
            ) from error
