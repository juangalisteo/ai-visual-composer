import requests
from pathlib import Path


class OllamaRequestError(RuntimeError):
    """A visible, actionable failure while contacting local Ollama."""


class OllamaProvider:

    def __init__(self, model):
        self.url = "http://localhost:11434/api/generate"
        self.model = model

    def generate(self, prompt):

        Path("logs").mkdir(exist_ok=True)
        Path("logs/prompt_debug.txt").write_text(prompt, encoding="utf-8")

        try:
            response = requests.post(
                self.url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
            )
            response.raise_for_status()
        except requests.Timeout as error:
            raise OllamaRequestError(
                "La comunicación con Ollama agotó su espera de red. "
                "Comprueba que el servicio y el modelo estén disponibles."
            ) from error
        except requests.RequestException as error:
            raise OllamaRequestError(
                f"No se pudo conectar con Ollama: {error}"
            ) from error

        try:
            result = response.json()["response"]
        except (ValueError, KeyError, TypeError) as error:
            raise OllamaRequestError(
                "Ollama devolvió una respuesta HTTP sin el campo 'response'."
            ) from error

        if not isinstance(result, str):
            raise OllamaRequestError(
                "Ollama devolvió un campo 'response' no textual."
            )

        Path("logs/response_debug.txt").write_text(result, encoding="utf-8")

        return result
