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

        json_start = cleaned_response.find("[")

        if json_start < 0:
            raise ValueError(
                "Ollama no devolvió una lista JSON válida."
            )

        try:
            decoder = json.JSONDecoder()
            parsed_response, consumed = decoder.raw_decode(
                cleaned_response[json_start:]
            )

        except json.JSONDecodeError as error:
            raise ValueError(
                "No se pudo interpretar el JSON "
                "devuelto por Ollama."
            ) from error

        trailing = cleaned_response[json_start + consumed:].strip()
        if trailing:
            raise ValueError(
                "Ollama devolvió datos adicionales después del JSON del storyboard."
            )

        if not isinstance(
            parsed_response,
            list
        ):
            raise ValueError(
                "La respuesta del storyboard "
                "debe ser una lista JSON."
            )

        return parsed_response
