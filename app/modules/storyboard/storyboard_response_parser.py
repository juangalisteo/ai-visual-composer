import json
import re


class StoryboardResponseParser:

    def parse(
        self,
        raw_response
    ):
        if not raw_response:
            raise ValueError(
                "Ollama devolvió una respuesta vacía."
            )

        cleaned_response = str(
            raw_response
        ).strip()

        cleaned_response = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned_response,
            flags=re.IGNORECASE
        )

        cleaned_response = re.sub(
            r"\s*```$",
            "",
            cleaned_response
        )

        json_match = re.search(
            r"\[[\s\S]*\]",
            cleaned_response
        )

        if not json_match:
            raise ValueError(
                "Ollama no devolvió una lista JSON válida."
            )

        json_text = (
            json_match.group(0)
        )

        try:
            parsed_response = json.loads(
                json_text
            )

        except json.JSONDecodeError as error:
            raise ValueError(
                "No se pudo interpretar el JSON "
                "devuelto por Ollama."
            ) from error

        if not isinstance(
            parsed_response,
            list
        ):
            raise ValueError(
                "La respuesta del storyboard "
                "debe ser una lista JSON."
            )

        return parsed_response