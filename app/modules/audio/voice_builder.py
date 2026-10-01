from pathlib import Path
import asyncio
import time

import edge_tts

from app.managers.project_manager import ProjectManager
from app.modules.subtitles.policies.timing import edge_word_boundaries_path
from app.shared.config_manager import ConfigManager
from app.shared.progress_logger import ProgressLogger
from app.shared.operational_error import OperationalError, create_operational_error


class VoiceBuilder:

    def __init__(
        self
    ):
        config = (
            ConfigManager()
            .get_voice_config()
        )

        self.voice = config["voice"]
        self.rate = config["rate"]
        self.volume = config["volume"]

    async def _generate_audio(
        self,
        text,
        output_path
    ):
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume,
            boundary="WordBoundary"
        )

        await communicate.save(
            str(output_path),
            str(
                edge_word_boundaries_path(
                    output_path
                )
            )
        )

    def build(
        self,
        text,
        output_path=None
    ):
        ProgressLogger.start(
            "GENERANDO VOCES"
        )

        start = time.perf_counter()

        if not str(text).strip():
            raise ValueError(
                "No se puede generar voz "
                "a partir de un texto vacío."
            )

        if output_path is None:
            project = ProjectManager()
            output_path = project.audio_path()

        output_path = Path(
            output_path
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        try:
            asyncio.run(
                self._generate_audio(
                    text=text,
                    output_path=output_path
                )
            )
        except OperationalError:
            raise
        except Exception as error:
            raise create_operational_error(
                family="AUDIO",
                user_message="No se pudo generar la voz con Edge TTS.",
                recommended_action="Comprueba la voz configurada y la disponibilidad del servicio.",
                operation="Generar voz con Edge TTS",
                resource=str(output_path),
                technical_metadata={
                    "voice": self.voice,
                    "phase": "voice_generation",
                },
            ) from error

        if not output_path.exists():
            error = FileNotFoundError(
                "La generación de voz terminó, "
                "pero no se encontró el archivo: "
                f"{output_path}"
            )
            raise create_operational_error(
                family="VALIDATION",
                user_message="La generación de voz terminó sin crear el archivo esperado.",
                recommended_action="Revisa el servicio de voz y el directorio de salida.",
                operation="Validar salida de voz",
                resource=str(output_path),
                technical_metadata={"voice": self.voice, "phase": "voice_output"},
            ) from error

        if output_path.stat().st_size <= 0:
            error = RuntimeError(
                "El archivo de voz generado "
                "está vacío."
            )
            raise create_operational_error(
                family="VALIDATION",
                user_message="La generación de voz creó un archivo vacío.",
                recommended_action="Revisa el servicio de voz y vuelve a intentarlo.",
                operation="Validar salida de voz",
                resource=str(output_path),
                technical_metadata={"voice": self.voice, "phase": "voice_output"},
            ) from error

        elapsed = (
            time.perf_counter()
            - start
        )

        ProgressLogger.finish(
            "Finalizado",
            elapsed
        )

        return output_path
