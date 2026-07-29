import time

from app.providers.ollama_provider import OllamaProvider
from app.shared.progress_logger import ProgressLogger


class ScriptBuilder:

    def __init__(
        self,
        ai_config
    ):
        self.provider = OllamaProvider(
            ai_config["model"]
        )

    def build(
        self,
        prompt
    ):
        ProgressLogger.start(
            "GENERANDO GUION"
        )

        start = time.perf_counter()

        script = self.provider.generate(
            prompt
        )

        elapsed = (
            time.perf_counter()
            - start
        )

        if not script:
            raise ValueError(
                "La IA devolvió un guion vacío."
            )

        ProgressLogger.finish(
            "Finalizado",
            elapsed
        )

        return script