import re
import unittest

from app.core.prompt_engine import PromptEngine


FORMAT_SENTENCES = {
    "vertical": (
        "Genera un contenido adaptado para vídeo vertical.",
        "Mantén un ritmo constante.",
        "Cada frase debe aportar valor.",
        "El cierre debe ser una afirmación clara, firme, coherente y memorable.",
    ),
    "horizontal": (
        "Genera un contenido adaptado para vídeo horizontal.",
        "Prioriza la comprensión sobre la velocidad.",
        "El desarrollo puede ser pausado.",
        "El objetivo es construir una explicación completa del tema.",
    ),
}


# Cabecera que precede a FORMATO: la sección que se unió en R1 iba entre ambas.
HEADER_BEFORE_FORMAT = {"script": "TAREA", "storyboard": "TAREA VISUAL"}
HEADER = re.compile(r"^([A-ZÁÉÍÓÚÑ0-9 /]+):\s*$", re.MULTILINE)


def build_prompts(profile_format):
    profile = {
        "tone": "modo_conciencia",
        "format": profile_format,
        "duration": 10,
    }
    engine = PromptEngine()
    return {
        "script": engine.build_script_request("conciencia", profile).prompt,
        "storyboard": engine.build_storyboard_prompt(
            scenes=[{"scene": 1, "text": "Una puerta se abre."}],
            profile=profile,
        ),
    }


class PromptEngineFormatSectionTest(unittest.TestCase):

    def test_prompts_have_one_format_section_with_the_joined_text(self):
        for profile_format, sentences in FORMAT_SENTENCES.items():
            for kind, prompt in build_prompts(profile_format).items():
                with self.subTest(format=profile_format, prompt=kind):
                    self.assertEqual(1, prompt.count("\nFORMATO:\n"))
                    section = prompt.split("\nFORMATO:\n", 1)[1]
                    positions = [section.index(text) for text in sentences]
                    self.assertEqual(sorted(positions), positions)
                    headers = HEADER.findall(prompt)
                    self.assertEqual(
                        HEADER_BEFORE_FORMAT[kind],
                        headers[headers.index("FORMATO") - 1],
                    )
                    self.assertNotIn("destinado a", prompt)

    def test_profile_without_format_fails_as_before(self):
        profile = {"tone": "modo_conciencia", "duration": 10}
        engine = PromptEngine()

        with self.assertRaises(KeyError):
            engine.build_script_request("conciencia", profile)
        with self.assertRaises(KeyError):
            engine.build_storyboard_prompt(
                scenes=[{"scene": 1, "text": "Una puerta se abre."}],
                profile=profile,
            )


if __name__ == "__main__":
    unittest.main()
