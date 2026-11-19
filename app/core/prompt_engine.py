from pathlib import Path

from app.core.script_length import (
    ScriptLengthBudget,
    ScriptRequest,
    SpeechPacing,
)


class PromptEngine:

    def __init__(self):
        self.prompts_path = Path("prompts")

    def read_prompt_file(
        self,
        category: str,
        name: str
    ) -> str:
        file_path = (
            self.prompts_path
            / category
            / f"{name}.txt"
        )

        if not file_path.exists():
            raise FileNotFoundError(
                f"No existe el archivo de prompt: "
                f"{file_path}"
            )

        content = file_path.read_text(
            encoding="utf-8"
        ).strip()

        if not content:
            raise ValueError(
                f"El archivo de prompt está vacío: "
                f"{file_path}"
            )

        return content

    def build_script_request(
        self,
        topic: str,
        profile: dict,
        pacing: SpeechPacing,
    ) -> ScriptRequest:
        """Prompt of a topic script and its length budget, as data.

        ``pacing`` is the reading rate declared by the selected voice.
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

        prompt = f"""
TEMA:
{topic}

DURACIÓN:
- Duración objetivo: {duration} segundos.
- Extensión: {length.target_words} palabras como máximo; es un límite estricto.
- Ese límite es el presupuesto temporal que se usará para voz, subtítulos, storyboard e imágenes.
- Prioriza claridad, coherencia, desarrollo natural y completitud dentro de ese presupuesto.

IDENTIDAD Y TONO:
{tone_text}

TAREA:
{task_text}

FORMATO:
{format_text}

IDIOMA:
{language_text}

RESTRICCIONES:
{restrictions_text}

SALIDA OBLIGATORIA:
- Devuelve únicamente el guion final.
- No expliques el proceso.
- No añadas comentarios.
- No añadas encabezados técnicos.
- No escribas "Answer", "Response", "Output" ni "Final answer".
- No escribas "Word count" ni recuentos de palabras.
- No añadas un título.
- No uses Markdown.
- No uses bloques de código.
- No uses formato JSON.
- No uses XML.
""".strip()

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
            (
                f"ESCENA {scene['scene']}:\n"
                f"{scene['text']}"
            )
            for scene in normalized_scenes
        )

        json_example = self._build_json_example()

        prompt = f"""
OBJETIVO:
Crear el storyboard visual completo de un único vídeo.

NÚMERO EXACTO DE ESCENAS:
{scene_count}

TEXTOS DE LAS ESCENAS:
{scenes_text}

IDENTIDAD Y TONO:
{tone_text}

TAREA VISUAL:
{task_text}

FORMATO:
{format_text}

CRITERIOS DE DISEÑO:

- Analiza todas las escenas antes de generar la respuesta.
- Diseña el conjunto como una secuencia visual coherente.
- Cada escena debe representar fielmente su texto.
- Cada escena debe tener una identidad visual clara.
- Mantén una estética cinematográfica y profesional.
- Las escenas deben sentirse parte del mismo vídeo.
- Evita repetir protagonistas, escenarios, acciones y composiciones.
- Evita que todas las escenas sean una persona centrada rodeada de partículas.
- Alterna cuando tenga sentido entre:
  figura humana,
  arquitectura,
  naturaleza,
  espacios simbólicos,
  entornos cósmicos,
  objetos conceptuales
  y composiciones abstractas comprensibles.
- Estructura cada escena como Visual Truth 2.0.
- Incluye en cada escena:
  sujeto o elemento principal,
  acción o estado,
  entorno,
  composición,
  iluminación,
  atmósfera
  y elemento simbólico distintivo.
- Prioriza imágenes claras, impactantes y fáciles de generar.
- Evita descripciones genéricas o vagas.
- Evita escenas excesivamente recargadas.
- No incluyas ningún texto dentro de la imagen.
- No incluyas letras, palabras ni tipografía.
- No incluyas carteles, rótulos ni señales.
- No incluyas pantallas con texto.
- No incluyas libros abiertos con texto legible.
- No incluyas texto escrito a mano.
- No incluyas logotipos.
- No incluyas marcas de agua.
- No incluyas subtítulos.
- Evita cualquier objeto que pueda inducir al modelo a generar texto visible.
- No menciones cámaras, lentes, resolución ni parámetros técnicos.
- `filmable_interpretation` debe describir la imagen filmable final.
- No escribas párrafos largos.
- No expliques las decisiones visuales.

SALIDA OBLIGATORIA:

- Devuelve exclusivamente un JSON válido.
- La respuesta debe comenzar con [ y terminar con ].
- No uses bloques de código Markdown.
- No escribas texto antes ni después del JSON.
- La respuesta completa debe ser una única lista JSON.
- Devuelve exactamente {scene_count} objetos.
- Numera los objetos consecutivamente con "scene" desde 1 hasta {scene_count}.
- No omitas escenas.
- No añadas escenas nuevas.
- Cada objeto debe contener exactamente:
  "scene",
  "visible_subject",
  "visible_action",
  "visible_environment",
  "time_context",
  "key_objects",
  "spatial_relationships",
  "continuity_links",
  "abstract_source",
  "filmable_interpretation",
  "visual_constraints",
  y
  "visual_truth_status".

FORMATO EXACTO:

{json_example}
""".strip()

        return prompt

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

    def _build_json_example(
        self
    ) -> str:
        return (
            "[\n"
            "    {\n"
            '        "scene": 1,\n'
            '        "visible_subject": '
            '"Sujeto o elemento visible principal",\n'
            '        "visible_action": '
            '"Accion, estado o cambio visible",\n'
            '        "visible_environment": '
            '"Entorno fisico observable",\n'
            '        "time_context": '
            '"Momento temporal observable",\n'
            '        "key_objects": [\n'
            '            "Objeto visual clave"\n'
            "        ],\n"
            '        "spatial_relationships": [\n'
            '            "Relacion espacial observable"\n'
            "        ],\n"
            '        "continuity_links": [\n'
            '            "Elemento de continuidad con otras escenas"\n'
            "        ],\n"
            '        "abstract_source": '
            '"Idea abstracta de origen si existe",\n'
            '        "filmable_interpretation": '
            '"Descripcion filmable concreta de la escena",\n'
            '        "visual_constraints": [\n'
            '            "Sin texto legible"\n'
            "        ],\n"
            '        "visual_truth_status": "structured"\n'
            "    }\n"
            "]"
        )
