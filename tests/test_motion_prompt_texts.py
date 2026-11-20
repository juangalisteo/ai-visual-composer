"""The motion texts of the WAN clips come from prompts/video/.

The byte-for-byte equality with the texts that lived in Python is in
``test_prompt_snapshots.py`` (``wan_motion__`` cases).
"""

import json
import shutil
from pathlib import Path

import pytest

from app.domain import StoryboardScene
from app.modules.video_component import (
    MinimalVisualContext,
    MotionIntentBuilder,
    VideoPromptTranslator,
)
from app.modules.video_component.motion_intent_builder import (
    MOTION_TEXTS,
    STORYBOARD_FIELD_TEMPLATE,
    MotionPromptTexts,
)
from app.shared.operational_error import OperationalError
from app.shared.prompt_library import PromptLibrary


REAL_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


def _context():
    return MinimalVisualContext(
        source_path=Path("test_source.png"),
        width=1080,
        height=1920,
        aspect_ratio="9:16",
        orientation="portrait",
        image_format="PNG",
        stability_constraints=("test_stability",),
    )


def _document():
    return {
        "levels": {
            level: {
                "camera_motion": f"test {level} camera",
                "motion_intensity": f"test {level} intensity",
                "stability": f"test {level} stability",
                "temporal_rhythm": f"test {level} rhythm",
            }
            for level in ("subtle", "normal", "intense")
        },
        "intense_action_cues": ["test_fast"],
        "static_action_cues": ["test_still"],
        "static_visual_constraint_cues": ["test_frozen"],
        "preservation_constraints": ["test_keep"],
        "storyboard_preservation_constraints": ["test_keep_scene"],
        "avoidance_constraints": ["test_avoid"],
        "storyboard_avoidance_constraints": ["test_avoid_scene"],
    }


def _library(tmp_path, document=None, template="field {campo} = {valor}"):
    root = tmp_path / "test_prompts"
    (root / "video").mkdir(parents=True)
    if document is not None:
        (root / MOTION_TEXTS).write_text(
            json.dumps(document),
            encoding="utf-8",
        )
    if template is not None:
        (root / STORYBOARD_FIELD_TEMPLATE).write_text(
            template,
            encoding="utf-8",
        )
    return PromptLibrary(root)


def _scene(**fields):
    return StoryboardScene(scene_number=1, text="Texto.", **fields)


def _config_error(action):
    with pytest.raises(OperationalError) as context:
        action()
    assert context.value.context.family == "CONFIG"
    return context.value.context


def test_every_motion_text_comes_from_the_prompt_files(tmp_path):
    builder = MotionIntentBuilder(prompts=_library(tmp_path, _document()))

    motion = builder.build(
        _context(),
        storyboard_scene=_scene(
            visible_subject="test subject",
            visible_action="a test_fast move",
            key_objects=("test object", "other"),
        ),
    )

    assert motion.motion_level == "intense"
    assert motion.camera_motion == "test intense camera"
    assert motion.motion_intensity == "test intense intensity"
    assert motion.stability == "test intense stability"
    assert motion.temporal_rhythm == "test intense rhythm"
    assert motion.preservation_constraints == (
        "test_stability",
        "test_keep",
        "test_keep_scene",
        "field visible_subject = test subject",
        "field visible_action = a test_fast move",
        "field key_objects = test object; other",
    )
    assert motion.avoidance_constraints == ("test_avoid", "test_avoid_scene")


@pytest.mark.parametrize(
    ("fields", "level"),
    [
        ({"visible_action": "TEST_STILL and test_fast"}, "subtle"),
        (
            {
                "visible_action": "test_fast",
                "visual_constraints": ("Test_Frozen frame",),
            },
            "subtle",
        ),
        ({"filmable_interpretation": "test_fast water"}, "intense"),
        ({"visible_action": "walks"}, "normal"),
        ({"filmable_interpretation": "a valley"}, "subtle"),
    ],
)
def test_the_declared_keywords_choose_the_level(tmp_path, fields, level):
    builder = MotionIntentBuilder(prompts=_library(tmp_path, _document()))

    motion = builder.build(_context(), storyboard_scene=_scene(**fields))

    assert motion.motion_level == level
    assert motion.camera_motion == f"test {level} camera"


def test_without_storyboard_scene_only_the_fixed_constraints_go(tmp_path):
    builder = MotionIntentBuilder(prompts=_library(tmp_path, _document()))

    motion = builder.build(_context())

    assert motion.motion_level == "subtle"
    assert motion.preservation_constraints == ("test_stability", "test_keep")
    assert motion.avoidance_constraints == ("test_avoid",)


def test_texts_are_read_once(tmp_path):
    library = _library(tmp_path, _document())
    builder = MotionIntentBuilder(prompts=library)
    builder.build(_context())
    (library.root / MOTION_TEXTS).unlink()

    assert builder.build(_context()).camera_motion == "test subtle camera"


def test_injected_texts_are_used_as_they_are(tmp_path):
    texts = MotionPromptTexts.load(_library(tmp_path, _document()))

    motion = MotionIntentBuilder(
        texts=texts,
        prompts=_library(tmp_path / "other", template=None),
    ).build(_context())

    assert motion.camera_motion == "test subtle camera"


def test_missing_motion_file_is_a_config_error_with_its_path(tmp_path):
    builder = MotionIntentBuilder(prompts=_library(tmp_path))

    context = _config_error(lambda: builder.build(_context()))

    assert "video/motion.json" in context.user_message
    assert "Falta el archivo de prompt" in context.user_message


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        (lambda document: document.pop("levels"), "«levels.subtle.camera_motion»"),
        (lambda document: document["levels"].pop("intense"), "«levels.intense.camera_motion»"),
        (
            lambda document: document["levels"]["normal"].pop("stability"),
            "«levels.normal.stability»",
        ),
        (
            lambda document: document["levels"]["subtle"].update(temporal_rhythm=" "),
            "«levels.subtle.temporal_rhythm»",
        ),
        (
            lambda document: document["levels"].update(normal="test"),
            "«levels.normal.camera_motion»",
        ),
        (lambda document: document.pop("intense_action_cues"), "«intense_action_cues»"),
        (lambda document: document.update(static_action_cues=[]), "«static_action_cues»"),
        (
            lambda document: document.update(static_visual_constraint_cues=[""]),
            "«static_visual_constraint_cues»",
        ),
        (lambda document: document.pop("preservation_constraints"), "«preservation_constraints»"),
        (
            lambda document: document.pop("storyboard_preservation_constraints"),
            "«storyboard_preservation_constraints»",
        ),
        (lambda document: document.pop("avoidance_constraints"), "«avoidance_constraints»"),
        (
            lambda document: document.pop("storyboard_avoidance_constraints"),
            "«storyboard_avoidance_constraints»",
        ),
    ],
)
def test_missing_text_is_a_config_error_naming_it(tmp_path, change, fragment):
    document = _document()
    change(document)
    builder = MotionIntentBuilder(prompts=_library(tmp_path, document))

    context = _config_error(lambda: builder.build(_context()))

    assert "video/motion.json" in context.user_message
    assert fragment in context.user_message


@pytest.mark.parametrize(
    ("template", "fragment"),
    [
        (None, "Falta el archivo de prompt"),
        ("field {valor}", "le falta el marcador {campo}"),
        ("field {campo}", "le falta el marcador {valor}"),
        ("field {campo} {valor} {otro}", "marcador desconocido: {otro}"),
    ],
)
def test_storyboard_field_template_needs_both_markers(
    tmp_path,
    template,
    fragment,
):
    builder = MotionIntentBuilder(
        prompts=_library(tmp_path, _document(), template=template)
    )

    context = _config_error(
        lambda: builder.build(
            _context(),
            storyboard_scene=_scene(visible_subject="test subject"),
        )
    )

    assert "video/motion_storyboard_field.txt" in context.user_message
    assert fragment in context.user_message


def test_real_prompt_files_load_and_reach_wan(tmp_path):
    root = tmp_path / "prompts"
    shutil.copytree(REAL_PROMPTS, root)
    builder = MotionIntentBuilder(prompts=PromptLibrary(root))

    plan = VideoPromptTranslator(prompts=PromptLibrary(root)).translate(
        builder.build(
            _context(),
            storyboard_scene=_scene(
                visible_subject="An inventor",
                visible_action="se zambulle en el agua",
            ),
        )
    )

    assert "controlled short tracking move" in plan.prompt
    assert "preserve_storyboard_visible_subject: An inventor" in plan.prompt
    assert "no action beyond StoryboardScene.visible_action" in plan.negative_prompt
    texts = builder.texts
    assert set(texts.levels) == {"subtle", "normal", "intense"}
    assert "se zambulle" in texts.intense_action_cues
