import requests
from pathlib import Path


class OllamaProvider:

    def __init__(self, model):
        self.url = "http://localhost:11434/api/generate"
        self.model = model

    def generate(self, prompt):

        Path("logs").mkdir(exist_ok=True)
        Path("logs/prompt_debug.txt").write_text(prompt, encoding="utf-8")

        response = requests.post(
            self.url,
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
        )

        response.raise_for_status()

        result = response.json()["response"]

        Path("logs/response_debug.txt").write_text(result, encoding="utf-8")

        return result
