"""The stability constraints of the source image come from prompts/video/.

The byte-for-byte equality with the texts that lived in Python is in
``test_prompt_snapshots.py`` (``wan_source__`` cases).
"""

import json
import shutil
import struct
from pathlib import Path

import pytest

from app.modules.video_component import (
    MotionIntentBuilder,
    SourceImageAnalyzer,
    VideoComponentBuilder,
)
from app.modules.video_component.motion_intent_builder import MOTION_TEXTS
from app.modules.video_component.source_image_analysis import (
    SOURCE_STABILITY_CONSTRAINTS,
    load_source_stability_constraints,
)
from app.shared.operational_error import OperationalError
from app.shared.prompt_library import PromptLibrary


REAL_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


def _png(path, width=1080, height=1920):
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
        + b"\x08\x02\x00\x00\x00\x00\x00\x00\x00"
    )
    return path


def _library(tmp_path, document=None):
    root = tmp_path / "test_prompts"
    (root / "video").mkdir(parents=True)
    if document is not None:
        (root / MOTION_TEXTS).write_text(
            json.dumps(document),
            encoding="utf-8",
        )
    return PromptLibrary(root)


def _config_error(action):
    with pytest.raises(OperationalError) as context:
        action()
    assert context.value.context.family == "CONFIG"
    return context.value.context


def test_the_constraints_come_from_the_motion_file(tmp_path):
    library = _library(
        tmp_path,
        {SOURCE_STABILITY_CONSTRAINTS: ["test_keep_a", "test_keep_b"]},
    )

    context = SourceImageAnalyzer(prompts=library).analyze(
        _png(tmp_path / "test_source.png")
    )

    assert context.stability_constraints == ("test_keep_a", "test_keep_b")
    assert (context.width, context.height) == (1080, 1920)


def test_the_file_is_read_once(tmp_path):
    library = _library(
        tmp_path,
        {SOURCE_STABILITY_CONSTRAINTS: ["test_keep"]},
    )
    analyzer = SourceImageAnalyzer(prompts=library)
    source = _png(tmp_path / "test_source.png")
    analyzer.analyze(source)
    (library.root / MOTION_TEXTS).unlink()

    assert analyzer.analyze(source).stability_constraints == ("test_keep",)


def test_injected_constraints_are_used_as_they_are(tmp_path):
    analyzer = SourceImageAnalyzer(
        stability_constraints=["test_injected"],
        prompts=_library(tmp_path),
    )

    context = analyzer.analyze(_png(tmp_path / "test_source.png"))

    assert context.stability_constraints == ("test_injected",)


def test_missing_motion_file_is_a_config_error_with_its_path(tmp_path):
    analyzer = SourceImageAnalyzer(prompts=_library(tmp_path))

    context = _config_error(
        lambda: analyzer.analyze(_png(tmp_path / "test_source.png"))
    )

    assert "video/motion.json" in context.user_message
    assert "Falta el archivo de prompt" in context.user_message


@pytest.mark.parametrize(
    "document",
    [
        {},
        {SOURCE_STABILITY_CONSTRAINTS: []},
        {SOURCE_STABILITY_CONSTRAINTS: ["test_keep", " "]},
        {SOURCE_STABILITY_CONSTRAINTS: "test_keep"},
    ],
)
def test_missing_or_invalid_list_is_a_config_error_naming_it(
    tmp_path,
    document,
):
    analyzer = SourceImageAnalyzer(prompts=_library(tmp_path, document))

    context = _config_error(
        lambda: analyzer.analyze(_png(tmp_path / "test_source.png"))
    )

    assert "video/motion.json" in context.user_message
    assert "«source_stability_constraints»" in context.user_message


def test_a_missing_image_is_reported_before_the_prompt_file(tmp_path):
    analyzer = SourceImageAnalyzer(prompts=_library(tmp_path))

    with pytest.raises(FileNotFoundError):
        analyzer.analyze(tmp_path / "test_missing.png")


def test_the_motion_texts_do_not_need_the_source_list(tmp_path):
    # MotionIntentBuilder reads its own keys of motion.json; the source list
    # is only read by SourceImageAnalyzer.
    root = tmp_path / "prompts"
    shutil.copytree(REAL_PROMPTS, root)
    document = json.loads((root / MOTION_TEXTS).read_text(encoding="utf-8"))
    document.pop(SOURCE_STABILITY_CONSTRAINTS)
    (root / MOTION_TEXTS).write_text(json.dumps(document), encoding="utf-8")

    texts = MotionIntentBuilder(prompts=PromptLibrary(root)).texts

    assert "preserve_source_composition" not in texts.preservation_constraints


def test_real_prompt_files_reach_wan_first(tmp_path):
    root = tmp_path / "prompts"
    shutil.copytree(REAL_PROMPTS, root)
    library = PromptLibrary(root)

    preparation = VideoComponentBuilder(
        source_image_analyzer=SourceImageAnalyzer(prompts=library),
        motion_intent_builder=MotionIntentBuilder(prompts=library),
    ).prepare(source_path=_png(tmp_path / "test_source.png"))

    assert load_source_stability_constraints(library) == (
        "preserve_source_composition",
        "preserve_source_geometry",
        "avoid_identity_or_subject_changes",
    )
    assert preparation.motion_intent.preservation_constraints[:3] == (
        "preserve_source_composition",
        "preserve_source_geometry",
        "avoid_identity_or_subject_changes",
    )
    assert (
        "Preservation constraints: preserve_source_composition, "
        "preserve_source_geometry, avoid_identity_or_subject_changes, "
        "preserve_original_lighting"
    ) in preparation.prompt_plan.prompt
