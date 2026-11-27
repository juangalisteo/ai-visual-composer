import json
import tempfile
import unittest
from pathlib import Path

from app.core.prompt_engine import PromptEngine
from app.core.script_length import DurationMargin, SpeechPacing
from app.modules.images.prompt_system import ImagePromptSystem, ImagePromptTexts
from app.modules.script.script_builder import ScriptBuilder
from app.modules.video_component import MotionIntent, VideoPromptTranslator
from app.shared.operational_error import OperationalError
from app.shared.prompt_library import (
    PromptLibrary,
    require_prompt_text,
    require_prompt_texts,
)


REAL_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


class PromptLibraryTest(unittest.TestCase):

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name) / "test_prompts"
        self.root.mkdir()
        self.library = PromptLibrary(self.root)

    def tearDown(self):
        self._temp.cleanup()

    def _write(self, relative_path, content):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8"))
        return path

    def assertConfigError(self, context, *fragments):
        error = context.exception
        self.assertIsInstance(error, OperationalError)
        self.assertEqual("CONFIG", error.context.family)
        for fragment in fragments:
            self.assertIn(fragment, error.context.user_message)
        return error

    def test_text_is_stripped_and_read_as_utf8(self):
        self._write("test_family/test_text.txt", "\n  Línea con tilde.\r\nOtra.\n\n")

        self.assertEqual(
            "Línea con tilde.\nOtra.",
            self.library.text("test_family/test_text.txt"),
        )

    def test_missing_file_is_a_config_error_with_the_relative_path(self):
        library = PromptLibrary()

        with self.assertRaises(OperationalError) as context:
            library.text("test_family/missing.txt")

        error = self.assertConfigError(
            context,
            "Falta el archivo de prompt",
            "«prompts/test_family/missing.txt»",
        )
        self.assertEqual(
            "prompts/test_family/missing.txt",
            error.context.resource,
        )

    def test_empty_file_is_a_config_error(self):
        self._write("test_family/empty.txt", " \n\n")

        with self.assertRaises(OperationalError) as context:
            self.library.text("test_family/empty.txt")

        self.assertConfigError(context, "está vacío", "empty.txt")

    def test_render_fills_every_marker_once_and_does_not_reread_values(self):
        self._write(
            "templates/test_template.txt",
            "A: {primero}\nB: {segundo} y otra vez {primero}.\n{\n  \"json\": 1\n}",
        )

        rendered = self.library.render(
            "templates/test_template.txt",
            primero="{segundo}",
            segundo=7,
        )

        self.assertEqual(
            'A: {segundo}\nB: 7 y otra vez {segundo}.\n{\n  "json": 1\n}',
            rendered,
        )

    def test_missing_marker_is_a_config_error(self):
        self._write("templates/test_template.txt", "Solo {primero}.")

        with self.assertRaises(OperationalError) as context:
            self.library.render(
                "templates/test_template.txt",
                primero="x",
                segundo="y",
            )

        error = self.assertConfigError(
            context,
            "le falta el marcador {segundo}",
            "test_template.txt",
        )
        self.assertIn("{segundo}", error.context.recommended_action)

    def test_unknown_marker_is_a_config_error(self):
        self._write("templates/test_template.txt", "{primero} y {otro}.")

        with self.assertRaises(OperationalError) as context:
            self.library.render("templates/test_template.txt", primero="x")

        error = self.assertConfigError(
            context,
            "marcador desconocido: {otro}",
        )
        self.assertIn("{primero}", error.context.recommended_action)

    def test_tone_file_prefers_the_tone_and_falls_back_to_default(self):
        self._write("test_family/default.txt", "común")
        self._write("test_family/test_tone.txt", "propio")

        self.assertEqual(
            "test_family/test_tone.txt",
            self.library.tone_file("test_family", "test_tone"),
        )
        self.assertEqual(
            "test_family/default.txt",
            self.library.tone_file("test_family", "other_tone"),
        )
        self.assertEqual(
            "test_family/default.txt",
            self.library.tone_file("test_family", None),
        )
        self.assertEqual(
            "test_family/default.json",
            self.library.tone_file("test_family", "test_tone", suffix=".json"),
        )

    def test_mapping_reads_a_json_object(self):
        self._write("test_family/data.json", '{"clave": "valor"}')

        self.assertEqual(
            {"clave": "valor"},
            self.library.mapping("test_family/data.json"),
        )

    def test_invalid_json_and_non_objects_are_config_errors(self):
        self._write("test_family/broken.json", '{"clave": ')
        self._write("test_family/list.json", '["valor"]')

        with self.assertRaises(OperationalError) as context:
            self.library.mapping("test_family/broken.json")
        self.assertConfigError(context, "no es un JSON válido", "broken.json")

        with self.assertRaises(OperationalError) as context:
            self.library.mapping("test_family/list.json")
        self.assertConfigError(context, "debe ser un objeto JSON")

    def test_required_texts_name_the_missing_key(self):
        document = {"texto": " ", "lista": ["uno", ""], "bien": ["uno"]}

        with self.assertRaises(OperationalError) as context:
            require_prompt_text(document, "texto", self.library, "test.json")
        self.assertConfigError(context, "no declara el texto «texto»")

        with self.assertRaises(OperationalError) as context:
            require_prompt_texts(document, "lista", self.library, "test.json")
        self.assertConfigError(context, "no declara la lista de textos «lista»")

        self.assertEqual(
            ("uno",),
            require_prompt_texts(document, "bien", self.library, "test.json"),
        )

    def test_display_keeps_the_relative_root(self):
        self.assertEqual(
            "prompts/templates/script.txt",
            PromptLibrary().display("templates/script.txt"),
        )


class PromptFilesInUseTest(unittest.TestCase):
    """Each stage reads its texts from the prompts/ folder it is given."""

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name) / "prompts"
        self._copy_real_prompts()
        self.library = PromptLibrary(self.root)

    def tearDown(self):
        self._temp.cleanup()

    def _copy_real_prompts(self):
        for source in REAL_PROMPTS.rglob("*"):
            if source.is_file():
                target = self.root / source.relative_to(REAL_PROMPTS)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())

    def _write(self, relative_path, content):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8"))

    def test_storyboard_uses_the_criteria_of_its_tone(self):
        self._write("tones/test_tone.txt", "Tono de prueba.")
        self._write("criteria/storyboard/test_tone.txt", "- Criterio de prueba.")
        engine = PromptEngine(self.library)
        scenes = [{"scene": 1, "text": "Una puerta se abre."}]

        own = engine.build_storyboard_prompt(
            scenes=scenes,
            profile={"tone": "test_tone", "format": "vertical"},
        )
        shared = engine.build_storyboard_prompt(
            scenes=scenes,
            profile={"tone": "modo_conciencia", "format": "vertical"},
        )

        self.assertIn("CRITERIOS DE DISEÑO:\n\n- Criterio de prueba.\n", own)
        self.assertNotIn("- Criterio de prueba.", shared)
        self.assertIn(
            (self.root / "criteria/storyboard/default.txt")
            .read_text(encoding="utf-8")
            .strip(),
            shared,
        )

    def test_storyboard_without_shared_criteria_is_a_config_error(self):
        (self.root / "criteria/storyboard/default.txt").unlink()

        with self.assertRaises(OperationalError) as context:
            PromptEngine(self.library).build_storyboard_prompt(
                scenes=[{"scene": 1, "text": "Una puerta se abre."}],
                profile={"tone": "modo_conciencia", "format": "vertical"},
            )

        self.assertEqual("CONFIG", context.exception.context.family)
        self.assertIn(
            "criteria/storyboard/default.txt",
            context.exception.context.user_message,
        )

    def test_script_template_without_a_marker_is_a_config_error(self):
        template = (self.root / "templates/script.txt").read_text(encoding="utf-8")
        self._write(
            "templates/script.txt",
            template.replace("{palabras_max}", "70"),
        )

        with self.assertRaises(OperationalError) as context:
            PromptEngine(self.library).build_script_request(
                "Tema de prueba",
                {"tone": "modo_conciencia", "format": "vertical", "duration": 30},
                SpeechPacing(letters_per_second=14.0, words_per_second=2.6),
                DurationMargin(below=0.10, above=None),
            )

        self.assertIn(
            "le falta el marcador {palabras_max}",
            context.exception.context.user_message,
        )

    def test_script_retry_reads_its_template(self):
        self._write("templates/script_retry.txt", "ARREGLO: {motivo}.")

        class FakeProvider:
            def __init__(self):
                self.prompts = []

            def generate(self, prompt, **_):
                self.prompts.append(prompt)
                return "" if len(self.prompts) == 1 else "Guion corregido."

        provider = FakeProvider()
        builder = ScriptBuilder(
            {"model": "test_model"},
            provider=provider,
            prompts=self.library,
        )

        self.assertEqual(
            "Guion corregido.",
            builder.generate_result("Prompt de prueba.").script,
        )
        self.assertEqual(
            "Prompt de prueba.\n\nARREGLO: empty_script.",
            provider.prompts[1],
        )

    def test_wan_reads_its_prompt_and_negative(self):
        self._write("video/wan.txt", "Mueve {movimiento_camara} ({intensidad}, {ritmo}, {estabilidad}); {conservar}")
        self._write("video/wan_negative.txt", "Evita: {evitar}")
        intent = MotionIntent(
            source="test_source",
            camera_motion="test_motion",
            motion_intensity="subtle",
            stability="high",
            temporal_rhythm="slow",
            preservation_constraints=("keep_a",),
            avoidance_constraints=("no_b", "no_c"),
        )

        plan = VideoPromptTranslator(self.library).translate(intent)

        self.assertEqual("Mueve test_motion (subtle, slow, high); keep_a", plan.prompt)
        self.assertEqual("Evita: no_b, no_c", plan.negative_prompt)

    def test_image_identity_follows_the_tone_and_rules_are_shared(self):
        self._write(
            "image/identity/test_tone.json",
            json.dumps({"base_visual": "test base", "cinematic": "test light"}),
        )

        own = ImagePromptTexts.load(self.library, "test_tone")
        shared = ImagePromptTexts.load(self.library, "other_tone")

        self.assertEqual("test base", own.base_visual_identity)
        self.assertEqual("test light", own.cinematic_operational_identity)
        self.assertNotEqual("test base", shared.base_visual_identity)
        self.assertEqual(
            own.cinematic_operational_restrictions,
            shared.cinematic_operational_restrictions,
        )
        prompt = ImagePromptSystem(
            tone="test_tone",
            prompts=self.library,
        ).compose_cinematic_backend_prompt("A quiet valley")
        self.assertTrue(prompt.startswith("A quiet valley, test base, test light, "))

    def test_image_rules_without_a_text_are_a_config_error(self):
        rules = json.loads(
            (self.root / "image/rules.json").read_text(encoding="utf-8")
        )
        del rules["no_text"]
        self._write("image/rules.json", json.dumps(rules))

        with self.assertRaises(OperationalError) as context:
            ImagePromptTexts.load(self.library, None)

        self.assertIn("«no_text»", context.exception.context.user_message)
        self.assertIn("image/rules.json", context.exception.context.user_message)

    def test_image_direction_without_cues_is_a_config_error(self):
        rules = json.loads(
            (self.root / "image/rules.json").read_text(encoding="utf-8")
        )
        rules["non_human_directions"] = [{"category": "test_family", "text": "x"}]
        self._write("image/rules.json", json.dumps(rules))

        with self.assertRaises(OperationalError) as context:
            ImagePromptTexts.load(self.library, None)

        self.assertIn("«cues»", context.exception.context.user_message)


if __name__ == "__main__":
    unittest.main()
