"""The program deletes from ComfyUI only the files it left there (I5b, P7).

Each image and each WAN clip leaves its files in a folder of its own job
inside the ComfyUI folders of ``config/comfyui.json``. Once copied into the
project, that job folder goes (and the empty folders above it the job
created); nothing else in ComfyUI is touched. ``cleanup_after_copy`` false
keeps everything; a failed deletion is a warning and the run goes on.
"""

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from app.modules.images.backends import ComfyUIBackend
from app.modules.images.backends.comfyui_backend import IMAGE_JOB_FOLDER
from app.modules.video_component import (
    BackendVideoPrompt,
    ComfyUIVideoBackend,
    ComfyUIVideoWorkflow,
    WanIntermediateOutput,
)
from app.modules.video_component.contracts import (
    ComfyUIInputRetention,
    StagedComfyInput,
    WanLosslessCapturePlan,
)
from app.modules.video_component.models import ComfyUIVideoBackendError
from app.modules.video_component.lossless_frame_output import (
    LosslessWanFrameOutput,
)
from app.shared import comfyui_files
from app.shared.comfyui_files import (
    ComfyUIJobFolder,
    ComfyUISettings,
    load_comfyui_settings,
)
from app.shared.operational_error import OperationalError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FLUX_WORKFLOW = REPOSITORY_ROOT / "config" / "comfyui_flux_workflow_api.json"


def _settings(root, cleanup=True):
    return ComfyUISettings(
        input_directory=root / "comfy" / "input",
        output_directory=root / "comfy" / "output",
        cleanup_after_copy=cleanup,
    )


def _png(width=2, height=1):
    return (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes((8, 2, 0, 0, 0))
        + b"\x00\x00\x00\x00"
    )


def _foreign_files(settings):
    """Files and folders of ComfyUI this program did not create."""
    output = settings.output_directory
    foreign = (
        output / "ComfyUI_00001_.png",
        output / IMAGE_JOB_FOLDER / "test_other_job" / "scene_001_00001_.png",
        output / "aivc_wan_lossless" / "test_other_job" / "frame_00001_.png",
        settings.input_directory / "wan_i2v" / "test_other_job" / "source.png",
        settings.input_directory / "example.png",
    )
    for path in foreign:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test-foreign")
    (output / "test_empty_folder").mkdir(parents=True, exist_ok=True)
    return foreign + (output / "test_empty_folder",)


def _tree(directory):
    return sorted(
        path.relative_to(directory).as_posix()
        for path in Path(directory).rglob("*")
    )


def _warnings(capsys):
    return [
        line
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("ADVERTENCIA:")
    ]


# --- config/comfyui.json -------------------------------------------------


def test_project_settings_clean_by_default():
    settings = load_comfyui_settings(REPOSITORY_ROOT / "config" / "comfyui.json")

    assert settings == ComfyUISettings(
        input_directory=Path("ComfyUI/ComfyUI/input"),
        output_directory=Path("ComfyUI/ComfyUI/output"),
        cleanup_after_copy=True,
    )


def _config_error(path):
    with pytest.raises(OperationalError) as caught:
        load_comfyui_settings(path)
    assert caught.value.context.family == "CONFIG"
    assert path.as_posix() in caught.value.context.user_message
    return caught.value.context


def _valid_document():
    return {
        "input_directory": "test_comfy/input",
        "output_directory": "test_comfy/output",
        "cleanup_after_copy": False,
    }


def test_settings_are_read_as_declared(tmp_path):
    path = tmp_path / "comfyui.json"
    document = _valid_document()
    document["input_directory"] = "  test_comfy/input  "
    path.write_text(json.dumps(document), encoding="utf-8")

    assert load_comfyui_settings(path) == ComfyUISettings(
        input_directory=Path("test_comfy/input"),
        output_directory=Path("test_comfy/output"),
        cleanup_after_copy=False,
    )


def test_missing_settings_file_is_a_config_error(tmp_path):
    context = _config_error(tmp_path / "comfyui.json")

    assert "Falta el archivo de configuración de ComfyUI" in context.user_message


@pytest.mark.parametrize(
    ("content", "fragment"),
    [
        ("{broken", "no es un JSON válido (línea 1)"),
        ("[]", "debe ser un objeto JSON"),
    ],
)
def test_unreadable_settings_are_a_config_error(tmp_path, content, fragment):
    path = tmp_path / "comfyui.json"
    path.write_text(content, encoding="utf-8")

    assert fragment in _config_error(path).user_message


@pytest.mark.parametrize(
    ("key", "value", "fragment"),
    [
        ("input_directory", None, "no declara «input_directory»"),
        ("output_directory", None, "no declara «output_directory»"),
        ("cleanup_after_copy", None, "no declara «cleanup_after_copy»"),
        ("input_directory", " ", "«input_directory» debe ser un texto no vacío"),
        ("output_directory", 3, "«output_directory» debe ser un texto no vacío"),
        ("cleanup_after_copy", "true", "«cleanup_after_copy» debe ser true o false"),
        ("cleanup_after_copy", 1, "«cleanup_after_copy» debe ser true o false"),
    ],
)
def test_each_key_is_required_and_checked(tmp_path, key, value, fragment):
    document = _valid_document()
    if value is None:
        document.pop(key)
    else:
        document[key] = value
    path = tmp_path / "comfyui.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    context = _config_error(path)

    assert fragment in context.user_message
    assert context.technical_metadata["key"] == key


# --- ComfyUIJobFolder -------------------------------------------------------


@pytest.mark.parametrize(
    "relative_path",
    ["", "/test_job", "../test_job", "test_folder/../../test_job"],
)
def test_a_job_folder_stays_inside_the_comfyui_folder(tmp_path, relative_path):
    with pytest.raises(ValueError):
        ComfyUIJobFolder.before_creating(tmp_path, relative_path)


def test_the_job_remembers_the_closest_existing_folder(tmp_path):
    (tmp_path / "test_shared").mkdir()

    created = ComfyUIJobFolder.before_creating(tmp_path, "test_new/test_job")
    shared = ComfyUIJobFolder.before_creating(tmp_path, "test_shared/test_job")
    missing_root = ComfyUIJobFolder.before_creating(
        tmp_path / "test_missing",
        "test_new/test_job",
    )

    assert created.existing == tmp_path
    assert shared.existing == tmp_path / "test_shared"
    assert missing_root.existing == tmp_path / "test_missing"


def test_removing_a_job_deletes_only_what_the_job_created(tmp_path):
    root = tmp_path / "comfy"
    (root / "test_kept").mkdir(parents=True)
    (root / "test_kept" / "other.png").write_bytes(b"other")
    created = ComfyUIJobFolder.before_creating(root, "test_new/test_sub/test_job")
    shared = ComfyUIJobFolder.before_creating(root, "test_kept/test_job")
    for job in (created, shared):
        job.path.mkdir(parents=True)
        (job.path / "file.png").write_bytes(b"job")

    created.remove()
    shared.remove()

    assert _tree(root) == ["test_kept", "test_kept/other.png"]


def test_a_folder_that_is_not_empty_is_never_deleted(tmp_path, capsys):
    root = tmp_path / "comfy"
    job = ComfyUIJobFolder.before_creating(root, "test_new/test_job")
    job.path.mkdir(parents=True)
    (root / "test_new" / "test_other_job").mkdir()

    job.remove()

    assert _tree(root) == ["test_new", "test_new/test_other_job"]
    assert _warnings(capsys) == []


def test_a_folder_that_existed_before_the_job_stays_even_if_empty(tmp_path):
    root = tmp_path / "comfy"
    (root / "test_shared").mkdir(parents=True)
    job = ComfyUIJobFolder.before_creating(root, "test_shared/test_job")
    job.path.mkdir()

    job.remove()

    assert root.is_dir()
    assert _tree(root) == ["test_shared"]


def test_a_failed_deletion_warns_in_spanish_and_goes_on(
    tmp_path,
    monkeypatch,
    capsys,
):
    job = ComfyUIJobFolder.before_creating(tmp_path, "test_new/test_job")
    job.path.mkdir(parents=True)

    def failing_rmtree(path):
        raise PermissionError(13, "Acceso denegado")

    monkeypatch.setattr(comfyui_files.shutil, "rmtree", failing_rmtree)
    job.remove()

    assert job.path.is_dir()
    assert _warnings(capsys) == [
        "ADVERTENCIA: No se pudo borrar de ComfyUI "
        f"«{job.path.as_posix()}» (Acceso denegado). "
        "La ejecución sigue; puede borrarlo a mano."
    ]


def test_a_failed_parent_deletion_warns_and_goes_on(
    tmp_path,
    monkeypatch,
    capsys,
):
    job = ComfyUIJobFolder.before_creating(tmp_path, "test_new/test_job")
    job.path.mkdir(parents=True)

    def failing_rmdir(self):
        raise PermissionError(13, "Acceso denegado")

    monkeypatch.setattr(Path, "rmdir", failing_rmdir)
    job.remove()

    assert not job.path.exists()
    assert (tmp_path / "test_new").is_dir()
    assert len(_warnings(capsys)) == 1


# --- Images (Flux) ----------------------------------------------------------


class _FakeComfyUIImages(ComfyUIBackend):
    """ComfyUI that saves each image where the workflow says, like SaveImage."""

    def __init__(self, settings, **kwargs):
        super().__init__(
            workflow_path=FLUX_WORKFLOW,
            comfyui_settings=settings,
            **kwargs,
        )
        self.workflows = []
        self.saved = []
        self.present_at_download = []

    def _save_node(self, workflow):
        (node,) = [
            node
            for node in workflow.values()
            if node.get("class_type") == "SaveImage"
        ]
        return node

    def queue_prompt(self, workflow, client_id):
        self.workflows.append(deepcopy(workflow))
        prefix = Path(self._save_node(workflow)["inputs"]["filename_prefix"])
        saved = (
            self.comfyui_settings.output_directory
            / prefix.parent
            / f"{prefix.name}_00001_.png"
        )
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(_png())
        self.saved.append(saved)
        return "test-prompt"

    def wait_for_image(self, prompt_id):
        saved = self.saved[-1]
        subfolder = saved.parent.relative_to(
            self.comfyui_settings.output_directory
        ).as_posix()
        return {
            "filename": saved.name,
            "subfolder": "" if subfolder == "." else subfolder,
            "type": "output",
        }

    def download_image(self, image_info, scene_number, output_dir):
        self.present_at_download.append(self.saved[-1].exists())
        image_path = Path(output_dir) / f"scene_{scene_number:03d}.png"
        image_path.write_bytes(self.saved[-1].read_bytes())
        return image_path


def _generate_images(backend, project, scenes=(1, 2)):
    project.mkdir(parents=True, exist_ok=True)
    return [
        backend.generate(
            prompt="test prompt",
            scene_number=scene,
            output_dir=project,
            width=64,
            height=64,
            seed=7,
        )
        for scene in scenes
    ]


def test_each_image_is_copied_and_then_its_comfyui_job_deleted(tmp_path):
    settings = _settings(tmp_path)
    foreign = _foreign_files(settings)
    before = _tree(settings.output_directory)
    backend = _FakeComfyUIImages(settings)

    images = _generate_images(backend, tmp_path / "project")

    assert [image.read_bytes() for image in images] == [_png(), _png()]
    assert backend.present_at_download == [True, True]
    assert all(not saved.exists() for saved in backend.saved)
    assert _tree(settings.output_directory) == before
    assert all(path.exists() for path in foreign)


def test_each_image_job_saves_in_a_folder_of_its_own(tmp_path):
    settings = _settings(tmp_path)
    backend = _FakeComfyUIImages(settings)

    _generate_images(backend, tmp_path / "project")

    prefixes = [
        backend._save_node(workflow)["inputs"]["filename_prefix"]
        for workflow in backend.workflows
    ]
    first, second = (Path(prefix) for prefix in prefixes)
    assert first.parts[0] == second.parts[0] == IMAGE_JOB_FOLDER
    assert first.parent != second.parent
    assert len(first.parent.name) == 32
    assert (first.name, second.name) == ("scene_001", "scene_002")


def test_the_image_job_folder_goes_when_the_job_created_it(tmp_path):
    settings = _settings(tmp_path)
    settings.output_directory.mkdir(parents=True)
    backend = _FakeComfyUIImages(settings)

    _generate_images(backend, tmp_path / "project")

    assert settings.output_directory.is_dir()
    assert _tree(settings.output_directory) == []


def test_without_cleanup_the_image_workflow_and_comfyui_are_untouched(tmp_path):
    settings = _settings(tmp_path, cleanup=False)
    settings.output_directory.mkdir(parents=True)
    backend = _FakeComfyUIImages(settings)
    expected = json.loads(FLUX_WORKFLOW.read_text(encoding="utf-8"))
    expected = backend.inject_seed(
        backend.inject_dimensions(
            backend.inject_prompt(expected, "test prompt"),
            64,
            64,
        ),
        7,
    )

    _generate_images(backend, tmp_path / "project", scenes=(1,))

    assert backend.workflows == [expected]
    assert backend.saved[0].exists()
    assert backend.saved[0].parent == settings.output_directory


def test_a_failed_image_download_keeps_the_comfyui_file(tmp_path):
    settings = _settings(tmp_path)

    class FailingDownload(_FakeComfyUIImages):
        def download_image(self, image_info, scene_number, output_dir):
            raise RuntimeError("test download failure")

    backend = FailingDownload(settings)

    with pytest.raises(RuntimeError, match="test download failure"):
        _generate_images(backend, tmp_path / "project", scenes=(1,))

    assert backend.saved[0].exists()


def test_a_failed_image_deletion_warns_and_keeps_the_image(
    tmp_path,
    monkeypatch,
    capsys,
):
    settings = _settings(tmp_path)
    backend = _FakeComfyUIImages(settings)

    def failing_rmtree(path):
        raise PermissionError(13, "Acceso denegado")

    monkeypatch.setattr(comfyui_files.shutil, "rmtree", failing_rmtree)
    (image,) = _generate_images(backend, tmp_path / "project", scenes=(1,))

    assert image.read_bytes() == _png()
    assert backend.saved[0].exists()
    (warning,) = _warnings(capsys)
    assert "No se pudo borrar de ComfyUI" in warning


@pytest.mark.parametrize("count", [0, 2])
def test_the_workflow_needs_exactly_one_save_node(count):
    workflow = {
        str(index): {"class_type": "SaveImage", "inputs": {}}
        for index in range(count)
    }

    with pytest.raises(ValueError, match="un solo nodo SaveImage"):
        ComfyUIBackend().inject_output_prefix(workflow, "test_prefix")


def test_the_real_flux_workflow_takes_the_job_prefix():
    workflow = json.loads(FLUX_WORKFLOW.read_text(encoding="utf-8"))

    ComfyUIBackend().inject_output_prefix(workflow, "test_folder/scene_001")

    saves = [
        node["inputs"]["filename_prefix"]
        for node in workflow.values()
        if node.get("class_type") == "SaveImage"
    ]
    assert saves == ["test_folder/scene_001"]


# --- WAN clips --------------------------------------------------------------


def _h264_workflow(source):
    return ComfyUIVideoWorkflow(
        workflow={
            "load": {
                "class_type": "LoadImage",
                "inputs": {"image": "test-source.png"},
            },
        },
        backend_prompt=BackendVideoPrompt(
            source_image=source,
            positive_prompt="test positive",
            negative_prompt="test negative",
            motion_summary="test motion",
            intermediate_output=WanIntermediateOutput.SAVEVIDEO_H264,
        ),
        source_image_name="test-source.png",
        output_prefix="test/clip_001",
    )


class _FakeComfyUIClip(ComfyUIVideoBackend):
    def queue_prompt(self, workflow, client_id):
        self.staged = (
            self.comfyui_input_dir / workflow["load"]["inputs"]["image"]
        )
        self.staged_at_queue = self.staged.exists()
        return "test-prompt"

    def wait_for_video(self, prompt_id):
        return {"filename": "clip.mp4", "subfolder": "", "type": "output"}

    def download_video(self, video_info, output_dir, output_name):
        output_path = Path(output_dir) / output_name
        output_path.write_bytes(b"test-video")
        return output_path


def _clip(tmp_path, settings, backend_class=_FakeComfyUIClip, **kwargs):
    source = tmp_path / "project" / "scene_001.png"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(_png())
    backend = backend_class(comfyui_settings=settings, **kwargs)
    result = backend.generate(_h264_workflow(source), tmp_path / "project" / "clips")
    return backend, source, result


def test_the_comfyui_folders_come_from_the_settings(tmp_path):
    settings = _settings(tmp_path)
    backend = ComfyUIVideoBackend(comfyui_settings=settings)

    assert backend.comfyui_input_dir == settings.input_directory
    assert backend.comfyui_output_dir == settings.output_directory
    assert backend.staging_retention is ComfyUIInputRetention.CLEANUP_ON_SUCCESS
    assert (
        ComfyUIVideoBackend(
            comfyui_settings=_settings(tmp_path, cleanup=False)
        ).staging_retention
        is ComfyUIInputRetention.PRESERVE_ALWAYS
    )


def test_the_staged_source_copy_and_its_job_folder_go_after_the_clip(tmp_path):
    settings = _settings(tmp_path)
    foreign = _foreign_files(settings)
    before = _tree(settings.input_directory)

    backend, source, result = _clip(tmp_path, settings)

    assert backend.staged_at_queue
    assert not backend.staged.parent.exists()
    assert _tree(settings.input_directory) == before
    assert source.exists()
    assert result.output_clip.read_bytes() == b"test-video"
    assert all(path.exists() for path in foreign)


def test_the_staging_folder_goes_when_the_clip_created_it(tmp_path):
    settings = _settings(tmp_path)
    settings.input_directory.mkdir(parents=True)

    _clip(tmp_path, settings)

    assert _tree(settings.input_directory) == []


def test_the_cleanup_never_deletes_the_source_image(tmp_path):
    settings = _settings(tmp_path)
    job = settings.input_directory / "wan_i2v" / "test_job"
    job.mkdir(parents=True)
    source = job / "source.png"
    source.write_bytes(_png())
    staged = StagedComfyInput(
        job_id="test_job",
        source_path=source,
        relative_input_name="wan_i2v/test_job/staged.png",
        staged_path=job / "staged.png",
        existing_folder=settings.input_directory,
    )

    with pytest.raises(ComfyUIVideoBackendError, match="imagen fuente original"):
        ComfyUIVideoBackend(
            comfyui_settings=settings,
        )._cleanup_after_success(staged)

    assert source.exists()


def test_without_cleanup_the_staged_copy_stays(tmp_path):
    settings = _settings(tmp_path, cleanup=False)

    backend, _, _ = _clip(tmp_path, settings)

    assert backend.staged.exists()


def test_a_failed_staging_deletion_warns_and_keeps_the_clip(
    tmp_path,
    monkeypatch,
    capsys,
):
    settings = _settings(tmp_path)

    def failing_rmtree(path):
        raise PermissionError(13, "Acceso denegado")

    monkeypatch.setattr(comfyui_files.shutil, "rmtree", failing_rmtree)
    backend, _, result = _clip(tmp_path, settings)

    assert result.output_clip.exists()
    assert backend.staged.exists()
    (warning,) = _warnings(capsys)
    assert "No se pudo borrar de ComfyUI" in warning


class _Runner:
    def run(self, command):
        Path(command[-1]).write_bytes(b"test-ffv1")


def _lossless_workflow(source, job_id="test_job"):
    plan = WanLosslessCapturePlan(
        job_id=job_id,
        capture_node_id="capture",
        output_prefix=f"aivc_wan_lossless/{job_id}/frame",
        expected_frame_count=2,
        width=2,
        height=1,
        fps=12,
        bit_depth=8,
    )
    return plan, ComfyUIVideoWorkflow(
        workflow={
            "load": {"class_type": "LoadImage", "inputs": {"image": "x.png"}},
            "capture": {"class_type": "SaveImage", "inputs": {}},
        },
        backend_prompt=BackendVideoPrompt(
            source_image=source,
            positive_prompt="test positive",
            negative_prompt="",
            motion_summary="test motion",
            frames=2,
            fps=12,
            generation_width=2,
            generation_height=1,
            intermediate_output=WanIntermediateOutput.LOSSLESS_FFV1,
        ),
        source_image_name="x.png",
        output_prefix="clip",
        lossless_capture=plan,
    )


class _FakeComfyUILossless(ComfyUIVideoBackend):
    """ComfyUI that saves the frames of the capture node, like SaveImage."""

    def queue_prompt(self, workflow, client_id):
        frames = self.comfyui_output_dir / "aivc_wan_lossless" / "test_job"
        frames.mkdir(parents=True, exist_ok=True)
        for index in (1, 2):
            (frames / f"frame_{index:05d}_.png").write_bytes(_png())
        self.frames = frames
        return "test-prompt"

    def _history(self, prompt_id):
        return {
            prompt_id: {
                "outputs": {
                    "capture": {
                        "images": [
                            {
                                "filename": f"frame_{index:05d}_.png",
                                "subfolder": "aivc_wan_lossless/test_job",
                                "type": "output",
                            }
                            for index in (1, 2)
                        ],
                    },
                },
            },
        }

    def download_output_file(self, output_info, output_path):
        self.frames_at_download = self.frames.is_dir()
        Path(output_path).write_bytes(_png())
        return Path(output_path)


def _lossless_clip(tmp_path, settings):
    source = tmp_path / "project" / "scene_001.png"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(_png())
    backend = _FakeComfyUILossless(
        comfyui_settings=settings,
        lossless_frame_output=LosslessWanFrameOutput(runner=_Runner()),
    )
    _, workflow = _lossless_workflow(source)
    result = backend.generate(workflow, tmp_path / "project" / "clips", "scene_001.mp4")
    return backend, result


def test_the_wan_frames_go_from_comfyui_after_the_clip(tmp_path):
    settings = _settings(tmp_path)
    foreign = _foreign_files(settings)
    before_output = _tree(settings.output_directory)
    before_input = _tree(settings.input_directory)

    backend, result = _lossless_clip(tmp_path, settings)

    assert backend.frames_at_download
    assert result.output_clip.read_bytes() == b"test-ffv1"
    assert _tree(settings.output_directory) == before_output
    assert _tree(settings.input_directory) == before_input
    assert all(path.exists() for path in foreign)


def test_nothing_of_the_clip_stays_in_comfyui(tmp_path):
    settings = _settings(tmp_path)
    settings.input_directory.mkdir(parents=True)
    settings.output_directory.mkdir(parents=True)

    _lossless_clip(tmp_path, settings)

    assert _tree(settings.input_directory) == []
    assert _tree(settings.output_directory) == []


def test_without_cleanup_the_wan_frames_stay_in_comfyui(tmp_path):
    settings = _settings(tmp_path, cleanup=False)

    backend, result = _lossless_clip(tmp_path, settings)

    assert result.output_clip.exists()
    assert sorted(path.name for path in backend.frames.iterdir()) == [
        "frame_00001_.png",
        "frame_00002_.png",
    ]


def test_a_failed_frames_deletion_warns_and_keeps_the_clip(
    tmp_path,
    monkeypatch,
    capsys,
):
    settings = _settings(tmp_path)
    real_rmtree = shutil.rmtree

    def failing_rmtree(path, *args, **kwargs):
        if "aivc_wan_lossless" in Path(path).as_posix():
            raise PermissionError(13, "Acceso denegado")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(comfyui_files.shutil, "rmtree", failing_rmtree)
    backend, result = _lossless_clip(tmp_path, settings)

    assert result.output_clip.exists()
    assert backend.frames.is_dir()
    (warning,) = _warnings(capsys)
    assert "aivc_wan_lossless/test_job" in warning
