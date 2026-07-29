from app.providers.ollama_provider import OllamaProvider


class StoryboardAIBuilder:

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
        response = self.provider.generate(
            prompt
        ).strip()

        if not response:
            raise ValueError(
                "Ollama devolvió una respuesta vacía "
                "para el storyboard."
            )

        return response