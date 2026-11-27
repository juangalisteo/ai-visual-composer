from app.core.script_length import (
    DurationMargin,
    ScriptLengthBudget,
    ScriptRequest,
    SpeechPacing,
)
from app.shared.prompt_library import PromptLibrary


# Templates of prompts/ that assemble each request.
SCRIPT_TEMPLATE = "templates/script.txt"
STORYBOARD_TEMPLATE = "templates/storyboard.txt"
STORYBOARD_SCENE_TEMPLATE = "templates/storyboard_scene.txt"
STORYBOARD_EXAMPLE = "templates/storyboard_example.json"
# Design criteria of the storyboard: one file per tone or the shared default.
STORYBOARD_CRITERIA = "criteria/storyboard"


class PromptEngine:

    def __init__(self, library=None):
        self.library = library or PromptLibrary()

    def read_prompt_file(
        self,
        category: str,
        name: str
    ) -> str:
        return self.library.text(
            f"{category}/{name}.txt"
        )

    def build_script_request(
        self,
        topic: str,
        profile: dict,
        pacing: SpeechPacing,
        margin: DurationMargin,
    ) -> ScriptRequest:
        """Prompt of a topic script and its length budget, as data.

        ``pacing`` is the reading rate declared by the selected voice and
        ``margin`` the accepted deviation declared in ``config/ai.json``.
        """
        topic = str(topic).strip()

        if not topic:
            raise ValueError(
                "El tema del guion está vacío."
            )

        tone = profile["tone"]
        format_type = profile["format"]
        duration = int(profile["duration"])

        length = ScriptLengthBudget.for_duration(
            duration,
            pacing,
            margin,
        )

        tone_text = self.read_prompt_file(
            "tones",
            tone
        )

        task_text = self.read_prompt_file(
            "tasks",
            "script"
        )

        format_text = self.read_prompt_file(
            "formats",
            format_type
        )

        language_text = self.read_prompt_file(
            "rules",
            "language"
        )

        restrictions_text = self.read_prompt_file(
            "rules",
            "restrictions"
        )

        prompt = self.library.render(
            SCRIPT_TEMPLATE,
            tema=topic,
            duracion=duration,
            palabras=length.target_words,
            tono=tone_text,
            tarea=task_text,
            formato=format_text,
            idioma=language_text,
            restricciones=restrictions_text,
        ).strip()

        return ScriptRequest(
            prompt=prompt,
            length=length,
        )

    def build_storyboard_prompt(
        self,
        scenes: list[dict],
        profile: dict
    ) -> str:
        if not scenes:
            raise ValueError(
                "No hay escenas para construir "
                "el prompt del storyboard."
            )

        tone = profile["tone"]
        format_type = profile["format"]

        tone_text = self.read_prompt_file(
            "tones",
            tone
        )

        task_text = self.read_prompt_file(
            "tasks",
            "storyboard"
        )

        format_text = self.read_prompt_file(
            "formats",
            format_type
        )

        normalized_scenes = (
            self._normalize_storyboard_scenes(
                scenes
            )
        )

        scene_count = len(
            normalized_scenes
        )

        scenes_text = "\n\n".join(
            self.library.render(
                STORYBOARD_SCENE_TEMPLATE,
                numero=scene["scene"],
                texto=scene["text"],
            )
            for scene in normalized_scenes
        )

        return self.library.render(
            STORYBOARD_TEMPLATE,
            numero_escenas=scene_count,
            escenas=scenes_text,
            tono=tone_text,
            tarea=task_text,
            formato=format_text,
            criterios=self.library.text(
                self.library.tone_file(
                    STORYBOARD_CRITERIA,
                    tone,
                )
            ),
            ejemplo_json=self.library.text(
                STORYBOARD_EXAMPLE
            ),
        ).strip()

    def _normalize_storyboard_scenes(
        self,
        scenes: list[dict]
    ) -> list[dict]:
        normalized = []

        for index, scene in enumerate(
            scenes,
            start=1
        ):
            if not isinstance(scene, dict):
                raise ValueError(
                    "Cada escena debe ser "
                    "un diccionario."
                )

            scene_number = scene.get(
                "scene",
                index
            )

            scene_text = str(
                scene.get(
                    "text",
                    ""
                )
            ).strip()

            if not scene_text:
                raise ValueError(
                    f"La escena {scene_number} "
                    f"no contiene texto."
                )

            try:
                scene_number = int(
                    scene_number
                )
            except (
                TypeError,
                ValueError
            ) as error:
                raise ValueError(
                    "El número de escena "
                    "no es válido."
                ) from error

            normalized.append({
                "scene": scene_number,
                "text": scene_text
            })

        expected_numbers = list(
            range(
                1,
                len(normalized) + 1
            )
        )

        received_numbers = [
            scene["scene"]
            for scene in normalized
        ]

        if received_numbers != expected_numbers:
            raise ValueError(
                "Las escenas deben estar numeradas "
                "consecutivamente desde 1."
            )

        return normalized
