"""Snapshots of the assembled prompts: the exact text sent to Ollama, Flux and WAN.

Each case assembles one prompt with the code and the files of ``prompts/``
and compares it with ``tests/fixtures/prompt_snapshots/<case>.txt``.

The snapshots of I4 (PARTE B) were written by the code of ``main`` 4c8238d,
when these texts still lived in Python: moving them to ``prompts/`` had to
leave every prompt byte for byte the same. A prompt changed on purpose
changes its snapshot; rewrite them with
``AIVC_UPDATE_PROMPT_SNAPSHOTS=1 python -m pytest tests/test_prompt_snapshots.py``
and review the diff.

``assemble_prompt_snapshots`` only uses calls that already existed before I4,
so the same function also wrote the snapshots from the old code.
"""

import os
import shutil
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = REPOSITORY_ROOT / "tests" / "fixtures" / "prompt_snapshots"
UPDATE_ENVIRONMENT = "AIVC_UPDATE_PROMPT_SNAPSHOTS"

TONES = ("modo_conciencia", "test_tone")
FORMATS = ("vertical", "horizontal")
TEST_TONE_TEXT = (
    "Tono de prueba: sereno, directo y sin adornos.\n\n"
    "Cada frase aporta una sola idea."
)

SCRIPT_TOPIC = "La memoria del agua"
SCRIPT_TEXT = (
    "El agua recuerda la forma de cada cauce que recorre. "
    "Cada gota guarda el camino de la anterior. "
    "Así aprende el río a volver siempre al mar."
)

STORYBOARD_SCENES = (
    "La neuroplasticidad es la capacidad del cerebro para reorganizarse. "
    "Permite nuevas conexiones neuronales.",
    "Este fenómeno demuestra que el cerebro no es estático.",
    "Su comprensión revoluciona la forma en que entendemos el potencial humano.",
    "El cerebro no tiene límites fijos; su capacidad de transformación "
    "es uno de los mayores logros de la naturaleza.",
)

IMAGE_SCENES = (
    {
        "scene": 1,
        "text": "Una persona camina hacia la luz.",
        "visible_subject": "Persona caminando a través de un puente de luz",
        "visible_action": "La persona avanza, dejando un rastro de luz",
        "visible_environment": "Un paisaje abstracto con cielo nocturno",
        "time_context": "En un momento de transición",
        "key_objects": ["Persona", "Puente de luz"],
        "spatial_relationships": ["La persona está en el centro del puente"],
        "continuity_links": ["La luz conecta con la escena anterior"],
        "abstract_source": "Adaptación y aprendizaje",
        "filmable_interpretation": (
            "Una figura humana camina por un puente de luz sobre un paisaje "
            "abstracto, con el suelo formado por patrones dinámicos"
        ),
        "visual_constraints": ["Sin texto legible"],
        "visual_truth_status": "structured",
    },
    {
        "scene": 2,
        "text": "El cerebro se reorganiza.",
        "visible_subject": "Cerebro humano en sección transversal",
        "visible_action": "Conexiones neuronales brillando y formándose",
        "visible_environment": "Entorno estéril de laboratorio con luces frías",
        "time_context": "En tiempo real",
        "key_objects": ["Cerebro humano", "Neuronas luminosas"],
        "spatial_relationships": [
            "Las neuronas se extienden desde el centro del cerebro hacia sus bordes",
        ],
        "continuity_links": [],
        "abstract_source": "Neuroplasticidad",
        "filmable_interpretation": (
            "A cross-section of a human brain with glowing neurons forming "
            "new connections"
        ),
        "visual_constraints": ["Sin texto legible"],
        "visual_truth_status": "structured",
    },
    {
        "scene": 3,
        "text": "Una catedral en ruinas.",
        "visible_subject": "Ancient cathedral ruins",
        "visible_action": "Morning fog drifts between the columns",
        "visible_environment": "Stone interior with broken vaults",
        "time_context": "Dawn",
        "key_objects": ["columns", "fog"],
        "spatial_relationships": ["Columns frame the central nave"],
        "continuity_links": ["Same cold palette as the previous scene"],
        "abstract_source": "",
        "filmable_interpretation": (
            "Fog drifting through the nave of ancient cathedral ruins at dawn"
        ),
        "visual_constraints": [],
        "visual_truth_status": "structured",
    },
    {
        "scene": 4,
        "text": "El tiempo se agota.",
        "visible_subject": "An hourglass on a wooden table",
        "visible_action": "Sand falls slowly",
        "visible_environment": "Dark study lit by a single candle",
        "time_context": "Night",
        "key_objects": ["hourglass", "candle"],
        "spatial_relationships": [],
        "continuity_links": [],
        "abstract_source": "El paso del tiempo",
        "filmable_interpretation": "Sand falling through an hourglass by candlelight",
        "visual_constraints": ["No text"],
        "visual_truth_status": "structured",
    },
    {
        "scene": 5,
        "text": "La energía lo atraviesa todo.",
        "visible_subject": "Electric plasma arcs",
        "visible_action": "Arcs pulse between two metal spheres",
        "visible_environment": "Dark laboratory",
        "time_context": "",
        "key_objects": ["metal spheres"],
        "spatial_relationships": ["The arcs connect both spheres"],
        "continuity_links": [],
        "abstract_source": "",
        "filmable_interpretation": "Electric plasma arcs pulsing between two metal spheres",
        "visual_constraints": [],
        "visual_truth_status": "structured",
    },
    {
        "scene": 6,
        "text": "El orden del universo.",
        "visible_subject": "A golden mandala of light",
        "visible_action": "The mandala rotates slowly",
        "visible_environment": "Deep space",
        "time_context": "",
        "key_objects": ["mandala"],
        "spatial_relationships": [],
        "continuity_links": [],
        "abstract_source": "Orden cósmico",
        "filmable_interpretation": "A golden mandala of light rotating in deep space",
        "visual_constraints": [],
        "visual_truth_status": "structured",
    },
    {
        "scene": 7,
        "text": "Un valle en calma.",
        "visible_subject": "Quiet valley",
        "visible_action": "Dawn light spreads slowly",
        "visible_environment": "Mountain landscape",
        "time_context": "Dawn",
        "key_objects": [],
        "spatial_relationships": [],
        "continuity_links": [],
        "abstract_source": "",
        "filmable_interpretation": "A quiet dawn over a mountain valley",
        "visual_constraints": [],
        "visual_truth_status": "structured",
    },
    {
        "scene": 8,
        "text": "Un inventor anciano estudia de noche.",
        "visible_subject": "An elderly inventor",
        "visible_action": "He studies an open book",
        "visible_environment": "A dim workshop",
        "time_context": "Night",
        "key_objects": ["open book", "oil lamp"],
        "spatial_relationships": ["The lamp lights the book"],
        "continuity_links": [],
        "abstract_source": "Curiosidad",
        "filmable_interpretation": (
            "An elderly inventor reads an open book by an oil lamp in a dim "
            "workshop at night, with cinematic light and deep shadows."
        ),
        "visual_constraints": [],
        "visual_truth_status": "structured",
    },
)

WAN_INTENTS = (
    (
        "subtle",
        {
            "source": "minimal_source_image_context",
            "camera_motion": "slow subtle cinematic camera drift",
            "motion_intensity": "subtle",
            "stability": "high",
            "temporal_rhythm": "slow and steady",
            "motion_level": "subtle",
            "preservation_constraints": (
                "preserve_source_composition",
                "preserve_original_lighting",
            ),
            "avoidance_constraints": (
                "no abrupt motion",
                "no invented action",
            ),
        },
    ),
    (
        "dynamic",
        {
            "source": "minimal_source_image_context",
            "camera_motion": "steady forward dolly",
            "motion_intensity": "moderate",
            "stability": "medium",
            "temporal_rhythm": "flowing",
            "motion_level": "normal",
            "preservation_constraints": ("preserve_subject_identity",),
            "avoidance_constraints": ("no new subjects", " "),
        },
    ),
    (
        "unconstrained",
        {
            "source": "minimal_source_image_context",
            "camera_motion": "static camera",
            "motion_intensity": "minimal",
            "stability": "high",
            "temporal_rhythm": "still",
            "motion_level": "subtle",
            "preservation_constraints": (),
            "avoidance_constraints": (),
        },
    ),
)


@contextmanager
def _working_directory(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


@contextmanager
def snapshot_project(code_root=REPOSITORY_ROOT):
    """A temporary project root: the real prompts/ and formats plus a test tone."""
    code_root = Path(code_root)
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        shutil.copytree(code_root / "prompts", root / "prompts")
        (root / "config").mkdir()
        shutil.copy2(
            code_root / "config" / "formats.json",
            root / "config" / "formats.json",
        )
        (root / "prompts" / "tones" / "test_tone.txt").write_bytes(
            TEST_TONE_TEXT.encode("utf-8")
        )
        with _working_directory(root):
            yield root


def _script_pacing():
    from app.core.script_length import SpeechPacing

    return SpeechPacing(letters_per_second=14.2, words_per_second=2.6)


def _script_prompts():
    from app.core.prompt_engine import PromptEngine

    snapshots = {}
    for tone in TONES:
        for profile_format in FORMATS:
            for duration in (30, 60):
                request = PromptEngine().build_script_request(
                    SCRIPT_TOPIC,
                    {
                        "tone": tone,
                        "format": profile_format,
                        "duration": duration,
                    },
                    _script_pacing(),
                )
                snapshots[
                    f"script__{tone}__{profile_format}__{duration}s"
                ] = request.prompt
    return snapshots


def _script_retry_prompts():
    from app.core.prompt_engine import PromptEngine
    from app.modules.script import script_builder
    from app.modules.script.models import (
        ScriptValidationIssue,
        ScriptValidationReport,
    )

    request = PromptEngine().build_script_request(
        SCRIPT_TOPIC,
        {"tone": "modo_conciencia", "format": "vertical", "duration": 30},
        _script_pacing(),
    )

    def report(reason):
        return ScriptValidationReport(
            valid=False,
            issues=(
                ScriptValidationIssue(
                    reason=reason,
                    field="script",
                    value="",
                ),
            ),
        )

    long_script = " ".join((SCRIPT_TEXT,) * 4)
    return {
        "script_retry__first_attempt": script_builder._attempt_prompt(
            request.prompt, 1, None, request.length, ""
        ),
        "script_retry__format_with_length": script_builder._attempt_prompt(
            request.prompt,
            2,
            report("markdown_detected"),
            request.length,
            "",
        ),
        "script_retry__format_without_length": script_builder._attempt_prompt(
            request.prompt, 2, None, None, ""
        ),
        "script_retry__too_long": script_builder._attempt_prompt(
            request.prompt,
            2,
            report("script_too_long_for_duration"),
            request.length,
            long_script,
        ),
        "script_retry__too_short": script_builder._attempt_prompt(
            request.prompt,
            2,
            report("script_too_short_for_duration"),
            request.length,
            SCRIPT_TEXT,
        ),
        "script_adjust__measured_long": script_builder._length_correction_prompt(
            request.prompt,
            length=request.length,
            previous_script=long_script,
            measured_seconds=41.27,
        ),
        "script_adjust__measured_short": script_builder._length_correction_prompt(
            request.prompt,
            length=request.length,
            previous_script=SCRIPT_TEXT,
            measured_seconds=9.5,
        ),
    }


def _storyboard_prompts():
    from app.core.prompt_engine import PromptEngine

    snapshots = {}
    for tone in TONES:
        for profile_format in FORMATS:
            for count in (1, len(STORYBOARD_SCENES)):
                scenes = [
                    {"scene": index, "text": text}
                    for index, text in enumerate(
                        STORYBOARD_SCENES[:count],
                        start=1,
                    )
                ]
                snapshots[
                    f"storyboard__{tone}__{profile_format}__{count}_scenes"
                ] = PromptEngine().build_storyboard_prompt(
                    scenes=scenes,
                    profile={"tone": tone, "format": profile_format},
                )
    return snapshots


def _image_prompts():
    from app.domain.adapters import StoryboardSceneAdapter
    from app.modules.images.image_builder import ImageBuilder

    snapshots = {}
    for profile_format in FORMATS:
        profile = {
            "tone": "modo_conciencia",
            "format": profile_format,
            "video_style": {"width": 1080, "height": 1920},
        }
        builder = ImageBuilder(backend=object(), profile=profile)
        for scene in IMAGE_SCENES:
            storyboard_scene = StoryboardSceneAdapter.from_visual_truth(
                scene=dict(scene),
                default_scene_number=scene["scene"],
            )
            metadata = builder._build_cinematic_runtime_metadata(
                storyboard_scene=storyboard_scene,
                profile=profile,
            )
            snapshots[
                f"image__{profile_format}__scene_{scene['scene']}"
            ] = metadata["operational_prompt"]
    return snapshots


def _wan_prompts():
    from app.modules.video_component import (
        MotionIntent,
        VideoPromptTranslator,
    )

    snapshots = {}
    for name, values in WAN_INTENTS:
        plan = VideoPromptTranslator().translate(MotionIntent(**values))
        snapshots[f"wan__{name}__prompt"] = plan.prompt
        snapshots[f"wan__{name}__negative"] = plan.negative_prompt
    return snapshots


def assemble_prompt_snapshots(code_root=REPOSITORY_ROOT):
    """Every prompt case, assembled inside a temporary project root."""
    with snapshot_project(code_root):
        snapshots = {}
        for assemble in (
            _script_prompts,
            _script_retry_prompts,
            _storyboard_prompts,
            _image_prompts,
            _wan_prompts,
        ):
            snapshots.update(assemble())
        return snapshots


def write_prompt_snapshots(snapshots, directory=SNAPSHOT_DIR):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for stale in directory.glob("*.txt"):
        stale.unlink()
    for name, text in snapshots.items():
        (directory / f"{name}.txt").write_bytes(text.encode("utf-8"))


class PromptSnapshotTest(unittest.TestCase):

    def test_assembled_prompts_match_their_snapshots(self):
        snapshots = assemble_prompt_snapshots()
        if os.environ.get(UPDATE_ENVIRONMENT) == "1":
            write_prompt_snapshots(snapshots)

        expected_names = sorted(
            path.stem for path in SNAPSHOT_DIR.glob("*.txt")
        )
        self.assertEqual(expected_names, sorted(snapshots))
        for name, text in snapshots.items():
            with self.subTest(case=name):
                expected = (SNAPSHOT_DIR / f"{name}.txt").read_text(
                    encoding="utf-8"
                )
                self.assertEqual(expected, text)

    def test_cases_cover_every_stage_tone_and_format(self):
        names = assemble_prompt_snapshots().keys()
        for stage in (
            "script__",
            "script_retry__",
            "script_adjust__",
            "storyboard__",
            "image__",
            "wan__",
        ):
            with self.subTest(stage=stage):
                self.assertTrue(
                    any(name.startswith(stage) for name in names)
                )
        for tone in TONES:
            self.assertTrue(any(f"__{tone}__" in name for name in names))
        for profile_format in FORMATS:
            self.assertTrue(
                any(f"__{profile_format}__" in name for name in names)
            )


if __name__ == "__main__":
    unittest.main()
