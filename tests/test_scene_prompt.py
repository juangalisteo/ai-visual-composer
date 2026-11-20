import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.domain import StoryboardScene
from app.modules.images.image_builder import ImageBuilder
from app.modules.images.prompt_system import ImagePromptSystem
from app.prompt_translation import (
    PromptBudgetExceededError,
    PromptBudgetPolicy,
    PromptTranslator,
    ScenePromptTemplate,
    compose_scene_prompt,
)
from app.shared.operational_error import OperationalError
from app.shared.prompt_library import (
    PromptLibrary,
    require_prompt_replacements,
)


TEXT_FREE = (
    ("open books", "closed books with plain covers"),
    ("open book", "closed book with a plain cover"),
    ("newspaper", "folded blank sheet of paper"),
    ("monitor", "dark glossy screen"),
)


def _template(text="{filmable_interpretation}, {visual_constraints}"):
    return ScenePromptTemplate(template=text, text_free_objects=TEXT_FREE)


class ComposeScenePromptTest(unittest.TestCase):

    def test_keeps_the_whole_sentence_with_its_commas(self):
        sentence = (
            "An old inventor, alone in a dark workshop, holds a glowing "
            "bulb; warm light, deep shadows, dust in the air"
        )

        composition = compose_scene_prompt(
            _template(),
            {
                "filmable_interpretation": sentence + ".",
                "visual_constraints": ("vertical 9:16",),
            },
        )

        self.assertEqual(sentence + ", vertical 9:16", composition.prompt)

    def test_a_value_already_said_by_another_is_dropped(self):
        composition = compose_scene_prompt(
            _template(
                "{visible_subject}, {filmable_interpretation}, {key_objects}"
            ),
            {
                "visible_subject": "An old inventor",
                "filmable_interpretation": "An old inventor holds glowing bulbs",
                "key_objects": ("glowing bulb", "workbench"),
            },
        )

        self.assertEqual(
            "An old inventor holds glowing bulbs, workbench",
            composition.prompt,
        )
        self.assertEqual(
            (
                ("visible_subject", "An old inventor"),
                ("key_objects", "glowing bulb"),
            ),
            composition.repeated,
        )

    def test_equal_values_keep_the_first(self):
        composition = compose_scene_prompt(
            _template("{visible_environment}. {time_context}"),
            {"visible_environment": "Night", "time_context": "night"},
        )

        self.assertEqual("Night.", composition.prompt)

    def test_objects_with_letters_are_replaced_with_their_article(self):
        composition = compose_scene_prompt(
            _template("{filmable_interpretation}"),
            {
                "filmable_interpretation": (
                    "An open book and a newspaper lie under a monitor; "
                    "Open books everywhere"
                ),
            },
        )

        self.assertEqual(
            "A closed book with a plain cover and a folded blank sheet of "
            "paper lie under a dark glossy screen; Closed books with plain "
            "covers everywhere",
            composition.prompt,
        )
        self.assertEqual(
            (
                ("Open books", "Closed books with plain covers"),
                ("An open book", "A closed book with a plain cover"),
                ("a newspaper", "a folded blank sheet of paper"),
                ("a monitor", "a dark glossy screen"),
            ),
            composition.replaced_objects,
        )

    def test_the_article_follows_the_replacement(self):
        composition = compose_scene_prompt(
            ScenePromptTemplate(
                template="{filmable_interpretation}",
                text_free_objects=(
                    ("poster", "empty frame"),
                    ("open book", "closed book"),
                ),
            ),
            {"filmable_interpretation": "A poster above an open book"},
        )

        self.assertEqual(
            "An empty frame above a closed book",
            composition.prompt,
        )

    def test_only_whole_words_are_replaced(self):
        composition = compose_scene_prompt(
            _template("{filmable_interpretation}"),
            {"filmable_interpretation": "Monitoring newspapers of the openbook era"},
        )

        self.assertEqual(
            "Monitoring newspapers of the openbook era",
            composition.prompt,
        )
        self.assertEqual((), composition.replaced_objects)

    def test_empty_values_leave_no_separators(self):
        composition = compose_scene_prompt(
            _template("{visual_constraints}, {filmable_interpretation}, {key_objects}"),
            {
                "filmable_interpretation": "A quiet valley at dawn",
                "visual_constraints": (),
                "key_objects": ("", "  "),
            },
        )

        self.assertEqual("A quiet valley at dawn", composition.prompt)

    def test_an_empty_value_in_the_middle_leaves_one_separator(self):
        composition = compose_scene_prompt(
            _template("{filmable_interpretation}, {visual_constraints}, {key_objects}"),
            {
                "filmable_interpretation": "A quiet valley at dawn",
                "visual_constraints": (),
                "key_objects": ("stone bridge",),
            },
        )

        self.assertEqual(
            "A quiet valley at dawn, stone bridge",
            composition.prompt,
        )

    def test_template_needs_known_fields(self):
        with self.assertRaises(ValueError):
            ScenePromptTemplate(template="{abstract_source}")
        with self.assertRaises(ValueError):
            ScenePromptTemplate(template="Sin campos")
        with self.assertRaises(ValueError):
            ScenePromptTemplate(template=" ")
        self.assertEqual(
            ("filmable_interpretation", "visual_constraints"),
            _template(
                "{filmable_interpretation}, {visual_constraints} {filmable_interpretation}"
            ).fields,
        )


class PromptTranslatorSceneTemplateTest(unittest.TestCase):

    def _brief(self, **values):
        from app.domain import EffectiveVisualBrief

        defaults = {
            "visible_subject": "An old inventor",
            "filmable_interpretation": (
                "An old inventor, alone at night, holds a glowing bulb "
                "above a cluttered workbench while warm light spills over "
                "his tools, his hands and the dusty shelves behind him, where "
                "old copper coils and glass jars catch the last reflections"
            ),
            "visual_constraints": ("vertical 9:16",),
            "fingerprint": "test-brief",
        }
        defaults.update(values)
        return EffectiveVisualBrief(**defaults)

    def test_prompt_is_the_template_without_cuts(self):
        translator = PromptTranslator(scene_template=_template())

        prompt = translator.translate(self._brief())

        self.assertEqual(
            self._brief().filmable_interpretation + ", vertical 9:16",
            prompt.compiled_prompt,
        )
        self.assertGreater(len(prompt.compiled_prompt.split()), 36)
        self.assertEqual(
            (
                "EffectiveVisualBrief.filmable_interpretation",
                "EffectiveVisualBrief.visual_constraints",
            ),
            tuple(instruction.source_field for instruction in prompt.instructions),
        )
        self.assertEqual(
            {"scene_template"},
            {item.transformation for item in prompt.trace.items},
        )
        self.assertEqual(("scene_template",), prompt.metrics.compactation_stages)
        self.assertTrue(prompt.fingerprint)
        stage = translator.last_observation.stages[0]
        self.assertEqual("scene_template", stage.stage_id)
        self.assertEqual(prompt.compiled_prompt, stage.prompt)

    def test_prompt_over_the_hard_limit_is_an_error_not_a_cut(self):
        translator = PromptTranslator(
            budget_policy=PromptBudgetPolicy(hard_prompt_tokens=10),
            scene_template=_template(),
        )

        with self.assertRaises(PromptBudgetExceededError):
            translator.translate(self._brief())

    def test_without_template_the_fragment_compiler_is_unchanged(self):
        brief = self._brief()

        self.assertEqual(
            PromptTranslator().translate(brief).compiled_prompt,
            PromptTranslator(scene_template=None).translate(brief).compiled_prompt,
        )
        self.assertNotEqual(
            PromptTranslator().translate(brief).compiled_prompt,
            PromptTranslator(scene_template=_template()).translate(brief).compiled_prompt,
        )


class IdentityWithoutRepetitionTest(unittest.TestCase):

    def test_identity_parts_said_by_the_scene_are_not_repeated(self):
        composition = ImagePromptSystem().compose_cinematic_backend_prompt_with_parts(
            "A quiet valley at dawn, cinematic lights and sharp details"
        )
        identity = dict(composition.parts)["identity.cinematic"]

        self.assertEqual(
            "coherent production design, balanced composition, atmospheric depth",
            identity,
        )
        self.assertIn("No text, logos, watermarks, or readable writing", composition.prompt)

    def test_identity_fully_said_by_the_scene_is_dropped(self):
        composition = ImagePromptSystem().compose_cinematic_backend_prompt_with_parts(
            "Professional photorealism, grounded documentary aesthetic: a valley"
        )

        self.assertNotIn(
            "identity.base_visual",
            [rule.id for rule in composition.rules],
        )
        self.assertIn("identity.cinematic", dict(composition.parts))

    def test_rules_other_than_identity_are_kept_whole(self):
        composition = ImagePromptSystem().compose_cinematic_backend_prompt_with_parts(
            "A valley with no text, logos"
        )

        self.assertIn(
            "No text, logos, watermarks, or readable writing",
            dict(composition.parts).values(),
        )

    def test_english_people_get_the_human_rules(self):
        rules = ImagePromptSystem().operational_rules_for_prompt(
            "An elderly inventor reads by an oil lamp"
        )

        self.assertIn("casting.human.anatomy", [rule.id for rule in rules])


class ImageBuilderSceneAndSeedTest(unittest.TestCase):

    def _scene(self, number):
        return {
            "scene": number,
            "text": "Texto de la escena.",
            "visible_subject": "A quiet valley",
            "visible_action": "Fog drifts slowly",
            "visible_environment": "Mountain landscape",
            "filmable_interpretation": (
                f"Fog drifts over quiet valley number {number}, "
                "with an open book on a rock"
            ),
            "visual_constraints": [],
            "visual_truth_status": "structured",
        }

    def _build(self, profile, scene_count=3):
        seeds = []
        prompts = []

        def generate(prompt, scene_number, output_dir, width, height, seed=None):
            seeds.append(seed)
            prompts.append(prompt)
            path = Path(output_dir) / f"scene_{scene_number:03d}.png"
            path.write_bytes(b"png")
            return path

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            storyboard = root / "storyboard.json"
            storyboard.write_text(
                json.dumps([self._scene(n) for n in range(1, scene_count + 1)]),
                encoding="utf-8",
            )
            workflow = root / "workflow.json"
            workflow.write_text("{}", encoding="utf-8")

            class Flow:
                def evaluate(self, **kwargs):
                    from types import SimpleNamespace

                    return SimpleNamespace(
                        status="approved",
                        generated_asset=SimpleNamespace(attempt_number=1),
                    )

            class Project:
                def images_manifest_path(self):
                    return root / "images_manifest.json"

            builder = ImageBuilder(
                workflow_path=workflow,
                backend=object(),
                image_quality_flow=Flow(),
                profile=profile,
                project=Project(),
            )
            with patch.object(ImageBuilder, "_generate_image", side_effect=generate):
                builder.build(storyboard_path=storyboard, output_dir=root / "images")
        return seeds, prompts

    def _profile(self, **images):
        profile = {
            "profile_id": "test_profile",
            "tone": "modo_conciencia",
            "format": "vertical",
            "video_style": {"width": 360, "height": 640},
        }
        if images:
            profile["images"] = images
        return profile

    def test_first_attempt_seed_is_profile_seed_plus_scene(self):
        first, prompts = self._build(self._profile(seed=500))
        again, _ = self._build(self._profile(seed=500))

        self.assertEqual([501, 502, 503], first)
        self.assertEqual(first, again)
        self.assertEqual([1], self._build(self._profile(seed=0), scene_count=1)[0])

    def test_default_prompt_uses_the_scene_template_of_prompts(self):
        _, prompts = self._build(self._profile(seed=1), scene_count=1)

        self.assertTrue(
            prompts[0].startswith(
                "Fog drifts over quiet valley number 1, with a closed "
                "leather-bound book with a plain cover on a rock, vertical 9:16, "
                "professional photorealism"
            ),
            prompts[0],
        )
        self.assertNotIn("open book", prompts[0])

    def test_profile_without_a_valid_seed_is_a_config_error(self):
        for images in ({}, {"seed": "7"}, {"seed": True}, {"seed": -1}, None):
            with self.subTest(images=images):
                profile = self._profile()
                if images is not None:
                    profile["images"] = images
                with self.assertRaises(OperationalError) as context:
                    self._build(profile, scene_count=1)
                error = context.exception.context
                self.assertEqual("CONFIG", error.family)
                self.assertIn("«test_profile»", error.user_message)
                self.assertIn("images.seed", error.user_message)

    def test_official_profiles_with_images_declare_the_image_seed(self):
        profiles = [
            (path, json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(Path("config/profiles").glob("*/*/perfil_*.json"))
        ]
        with_images = [
            (path, profile)
            for path, profile in profiles
            if profile.get("builders", {}).get("images")
        ]
        self.assertEqual(6, len(with_images))
        for path, profile in with_images:
            with self.subTest(path=path.as_posix()):
                seed = profile["images"]["seed"]
                self.assertIsInstance(seed, int)
                self.assertGreaterEqual(seed, 0)


class ScenePromptFilesTest(unittest.TestCase):

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name) / "prompts"
        self.root.mkdir()
        self.library = PromptLibrary(self.root)

    def tearDown(self):
        self._temp.cleanup()

    def _write(self, relative_path, content):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_template_with_an_unknown_or_no_marker_is_a_config_error(self):
        self._write("image/unknown.txt", "{filmable_interpretation} {texto}")
        self._write("image/none.txt", "Sin marcadores")
        allowed = ("filmable_interpretation",)

        with self.assertRaises(OperationalError) as context:
            self.library.template("image/unknown.txt", allowed)
        self.assertIn("marcador desconocido: {texto}", context.exception.context.user_message)

        with self.assertRaises(OperationalError) as context:
            self.library.template("image/none.txt", allowed)
        self.assertIn("no tiene ningún marcador", context.exception.context.user_message)

        self._write("image/scene.txt", "{filmable_interpretation}.")
        self.assertEqual(
            "{filmable_interpretation}.",
            self.library.template("image/scene.txt", allowed),
        )

    def test_replacements_need_a_text_for_each_object(self):
        self.assertEqual(
            (("open book", "closed book"),),
            require_prompt_replacements(
                {" open book ": " closed book "}, self.library, "x.json"
            ),
        )
        for document in ({"open book": ""}, {"open book": 3}, {" ": "x"}):
            with self.subTest(document=document):
                with self.assertRaises(OperationalError) as context:
                    require_prompt_replacements(document, self.library, "x.json")
                self.assertEqual("CONFIG", context.exception.context.family)

    def test_real_scene_files_load(self):
        template = ImageBuilder()._scene_prompt_template()

        self.assertEqual(
            ("filmable_interpretation", "visual_constraints"),
            template.fields,
        )
        self.assertIn(
            ("open book", "closed leather-bound book with a plain cover"),
            template.text_free_objects,
        )


class StoryboardSceneStillComposesTest(unittest.TestCase):

    def test_runtime_metadata_reports_the_scene_template(self):
        builder = ImageBuilder(
            backend=object(),
            profile={"tone": "modo_conciencia", "format": "vertical"},
        )

        metadata = builder._build_cinematic_runtime_metadata(
            storyboard_scene=StoryboardScene(
                scene_number=1,
                text="Texto.",
                visible_subject="A quiet valley",
                visible_action="Fog drifts",
                visible_environment="Mountains",
                filmable_interpretation="A quiet valley under drifting fog",
                visual_truth_status="structured",
            ),
            profile=builder.profile,
        )

        self.assertEqual(
            "A quiet valley under drifting fog, vertical 9:16",
            metadata["backend_payload_prompt"],
        )
        self.assertEqual(
            ("scene_template",),
            metadata["prompt_translation_metrics"]["compactation_stages"],
        )


if __name__ == "__main__":
    unittest.main()
