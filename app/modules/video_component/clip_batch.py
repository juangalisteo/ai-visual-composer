"""I2V clips for one storyboard: generation, atomic manifest and public video."""

import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from app.domain.adapters import StoryboardSceneAdapter
from app.managers.project_manager import ProjectManager
from app.modules.video_component.builder import VideoComponentBuilder
from app.modules.video_component.profile_parameters import (
    build_video_backend_overrides,
    load_video_component_parameters,
    video_progress_interval_seconds,
)
from app.shared.progress_heartbeat import ProgressHeartbeat, format_elapsed
from app.shared.progress_logger import ProgressLogger


@dataclass(frozen=True)
class I2VArtifactLease:
    """Private ownership of lossless clips from one published I2V manifest."""

    manifest_path: Path
    owned_lossless_paths: tuple[Path, ...]

    @classmethod
    def from_manifest(cls, manifest_path):
        manifest_path = Path(manifest_path)
        if not manifest_path.is_file():
            return cls(manifest_path, ())

        try:
            entries = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls(manifest_path, ())

        if not isinstance(entries, list):
            return cls(manifest_path, ())

        manifest_directory = manifest_path.parent.resolve()
        owned_paths = []
        seen_paths = set()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("kept") is False:
                continue
            output_clip = entry.get("output_clip")
            if not output_clip:
                continue
            candidate = Path(output_clip)
            if candidate.suffix.lower() != ".mkv":
                continue
            if candidate.parent.resolve() != manifest_directory:
                continue
            if not candidate.is_file():
                continue
            resolved_candidate = candidate.resolve()
            if resolved_candidate in seen_paths:
                continue
            seen_paths.add(resolved_candidate)
            owned_paths.append(candidate)

        return cls(manifest_path, tuple(owned_paths))

    def cleanup_after_successful_public_render(self, output_path):
        output_path = Path(output_path)
        if (
            output_path.suffix.lower() != ".mp4"
            or not output_path.is_file()
        ):
            return ()

        manifest_directory = self.manifest_path.parent.resolve()
        failures = []
        removed = []
        for owned_path in self.owned_lossless_paths:
            if (
                owned_path.suffix.lower() != ".mkv"
                or owned_path.parent.resolve() != manifest_directory
            ):
                continue
            try:
                owned_path.unlink(missing_ok=True)
            except OSError as error:
                failures.append((owned_path, error))
                ProgressLogger.info(
                    "No se pudo limpiar el FFV1 WAN poseido tras el render: "
                    f"{owned_path} ({error})"
                )
                continue
            removed.append(owned_path)

        if removed:
            self._mark_removed_clips(removed)
        return tuple(failures)

    def _mark_removed_clips(self, removed_paths):
        """Keep every clip in the manifest; a deleted one says ``"kept": false``.

        The manifest stays the record of what WAN generated (prompts, seed,
        frames…), but it no longer points to a ``.mkv`` as if it existed
        (PRUEBA-GS, fallo 17). If it cannot be rewritten, the final video is
        fine: it only warns.
        """
        removed = {Path(path).resolve() for path in removed_paths}
        try:
            entries = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            for entry in entries:
                output_clip = entry.get("output_clip") if isinstance(entry, dict) else None
                if output_clip and Path(output_clip).resolve() in removed:
                    entry["kept"] = False
            _write_json_atomically(self.manifest_path, entries)
        except (OSError, ValueError, TypeError, AttributeError) as error:
            ProgressLogger.warning(
                f"No se pudo marcar en «{self.manifest_path}» los clips "
                f"borrados tras el render ({error}). El vídeo final está bien."
            )


def generate_video_clips(
    storyboard_path,
    images_manifest_path,
    project=None,
    video_builder=None,
    profile_key=None
):
    project = (
        project
        or ProjectManager()
    )

    video_profile = load_video_component_parameters(
        profile_key
    )

    video_builder = (
        video_builder
        or VideoComponentBuilder()
    )

    storyboard_path = Path(
        storyboard_path
    )
    images_manifest_path = Path(
        images_manifest_path
    )

    scenes = _load_storyboard_scenes(
        storyboard_path
    )
    image_entries = _load_image_manifest_entries(
        images_manifest_path
    )

    scenes_by_number = {
        int(
            scene.get(
                "scene"
            )
        ): scene
        for scene in scenes
    }

    output_dir = (
        project.base_path
        / "video_clips"
    )
    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    clip_entries = []
    clip_count = len(
        image_entries
    )
    progress_interval = video_progress_interval_seconds(
        video_profile
    )

    ProgressLogger.start(
        "GENERANDO CLIPS DE VÍDEO (WAN)"
    )

    for clip_index, entry in enumerate(
        image_entries,
        start=1
    ):
        scene_number = _required_manifest_scene_number(
            entry
        )
        scene = scenes_by_number.get(
            scene_number
        )
        if scene is None:
            raise ValueError(
                "No existe una escena de storyboard "
                f"para la imagen {scene_number}."
            )

        source_image = Path(
            entry.get(
                "image",
                ""
            )
        )
        if not source_image.exists():
            raise FileNotFoundError(
                "No existe la imagen base para Video: "
                f"{source_image}"
            )

        storyboard_scene = (
            StoryboardSceneAdapter.from_visual_truth(
                scene=scene,
                default_scene_number=scene_number
            )
        )
        scene_identity = scene_clip_identity(scene_number)
        clip_label = f"Clip {clip_index}/{clip_count}"

        with ProgressHeartbeat(
            clip_label,
            progress_interval,
        ) as heartbeat:
            result = video_builder.generate_clip(
                source_path=source_image,
                output_dir=output_dir,
                output_name=f"{scene_identity}.mp4",
                storyboard_scene=storyboard_scene,
                **build_video_backend_overrides(
                    video_profile
                )
            )

        ProgressLogger.info(
            f"{clip_label} listo · "
            f"{format_elapsed(heartbeat.elapsed())}"
        )

        clip_entries.append(
            _build_video_clip_manifest_entry(
                result=result,
                storyboard_scene=storyboard_scene,
                image_entry=entry
            )
        )

    return _publish_video_clips_manifest_atomically(
        output_dir=output_dir,
        clip_entries=clip_entries,
    )


def _publish_video_clips_manifest_atomically(
    *,
    output_dir,
    clip_entries,
):
    manifest_path = (
        Path(output_dir)
        / "video_clips_manifest.json"
    )
    _write_json_atomically(manifest_path, clip_entries)
    return manifest_path


def _write_json_atomically(path, data):
    path = Path(path)
    temporary_path = path.with_name(
        f".{path.name}.{secrets.token_hex(16)}.tmp"
    )

    try:
        temporary_path.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=4,
            ),
            encoding="utf-8",
        )
        os.replace(
            temporary_path,
            path,
        )
    except Exception:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def build_public_video(
    *,
    video_builder,
    video_clips_manifest_path,
):
    lease = I2VArtifactLease.from_manifest(
        video_clips_manifest_path
    )
    output_path = video_builder.build(
        video_clips_manifest_path=video_clips_manifest_path
    )
    lease.cleanup_after_successful_public_render(output_path)
    return output_path


def _load_storyboard_scenes(
    storyboard_path
):
    data = json.loads(
        Path(
            storyboard_path
        ).read_text(
            encoding="utf-8"
        )
    )
    if not isinstance(
        data,
        list
    ):
        raise ValueError(
            "El storyboard de Video debe ser una lista de escenas."
        )
    return data


def _load_image_manifest_entries(
    images_manifest_path
):
    data = json.loads(
        Path(
            images_manifest_path
        ).read_text(
            encoding="utf-8"
        )
    )
    if not isinstance(
        data,
        list
    ):
        raise ValueError(
            "El manifiesto de imágenes debe ser una lista."
        )
    return data


def _required_manifest_scene_number(
    entry
):
    if not isinstance(
        entry,
        dict
    ):
        raise ValueError(
            "Cada entrada del manifiesto de imágenes "
            "debe ser un diccionario."
        )

    try:
        return int(
            entry[
                "scene"
            ]
        )
    except (
        KeyError,
        TypeError,
        ValueError
    ) as error:
        raise ValueError(
            "Cada imagen base de Video debe declarar scene."
        ) from error


def _build_video_clip_manifest_entry(
    result,
    storyboard_scene,
    image_entry
):
    return {
        "scene": storyboard_scene.scene_number,
        "source_image": str(
            result.source_image
        ),
        "image_manifest_entry": image_entry,
        "output_clip": str(
            result.output_clip
        ),
        # False once the final video is rendered and the clip is deleted.
        "kept": True,
        "positive_prompt": result.positive_prompt,
        "negative_prompt": result.negative_prompt,
        "motion_summary": result.motion_summary,
        "camera_motion": result.camera_motion,
        "motion_intensity": result.motion_intensity,
        "stability": result.stability,
        "temporal_rhythm": result.temporal_rhythm,
        "motion_level": result.motion_level,
        "preservation_constraints": list(
            result.preservation_constraints
        ),
        "avoidance_constraints": list(
            result.avoidance_constraints
        ),
        "source_trace": list(
            result.source_trace
        ),
        "profile": result.profile_name,
        "backend": result.backend,
        "model": result.model,
        "workflow": result.workflow,
        "prompt_id": result.prompt_id,
        "seed": result.seed,
        "frames": result.frames,
        "fps": result.fps,
        "generation_width": result.generation_width,
        "generation_height": result.generation_height,
        "steps": result.steps,
        "cfg": result.cfg,
        "sampler": result.sampler,
        "scheduler": result.scheduler,
        "duration_seconds": result.duration_seconds,
        "fingerprint": result.fingerprint,
    }


def scene_clip_identity(
    scene_number
):
    return f"scene_{int(scene_number):03d}"
