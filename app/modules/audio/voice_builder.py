from pathlib import Path
import asyncio
import time

import edge_tts

from app.managers.project_manager import ProjectManager
from app.shared.config_manager import ConfigManager
from app.shared.progress_logger import ProgressLogger


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
            volume=self.volume
        )

        await communicate.save(
            str(output_path)
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

        asyncio.run(
            self._generate_audio(
                text=text,
                output_path=output_path
            )
        )

        if not output_path.exists():
            raise FileNotFoundError(
                "La generación de voz terminó, "
                "pero no se encontró el archivo: "
                f"{output_path}"
            )

        if output_path.stat().st_size <= 0:
            raise RuntimeError(
                "El archivo de voz generado "
                "está vacío."
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