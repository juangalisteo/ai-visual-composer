"""Project-owned handling of lossless WAN frame capture.

For ``lossless_ffv1``, this module obtains frames from the semantic
``SaveImage`` capture, validates and copies its PNG batch, then materializes
an internal RGB FFV1/Matroska input that the existing final FFmpeg graph can
consume. The effective lossless route does not depend on ``SaveVideo``;
``savevideo_h264`` remains a separate rollback capability.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from app.modules.video.ffmpeg.runner import Runner
from app.modules.video_component.contracts import (
    WanArtifactRetention,
    WanLosslessCapturePlan,
    WanLosslessFrameSequence,
)


class LosslessWanFrameOutputError(RuntimeError):
    pass


class LosslessWanFrameOutput:
    """Downloads, validates, materializes and cleans one owned frame batch."""

    def __init__(self, runner=None):
        self.runner = runner or Runner()

    def capture(self, *, history_item, plan, prompt_id, destination_root, download):
        plan = _require_plan(plan)
        output_items = self._capture_output_items(history_item, plan)
        destination_root = Path(destination_root)
        artifact_root = destination_root / ".wan_lossless" / plan.job_id
        frames_root = artifact_root / "frames"
        frames_root.mkdir(parents=True, exist_ok=False)

        ordered_paths = []
        try:
            for index, output_item in enumerate(output_items, start=1):
                target = frames_root / f"frame_{index:06d}.png"
                download(output_item, target)
                self._validate_png(target, plan)
                ordered_paths.append(target)
        except Exception:
            # Partial local data is diagnostic evidence; the caller owns the
            # retention decision and deliberately preserves it on failure.
            raise

        return WanLosslessFrameSequence(
            plan=plan,
            prompt_id=prompt_id,
            ordered_frame_paths=tuple(ordered_paths),
            artifact_root=artifact_root,
            fingerprint=_sequence_sha256(ordered_paths),
        )

    def materialize_ffv1(self, sequence, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frames_root = self._owned_frames_root(sequence)
        command = [
            "ffmpeg",
            "-y",
            "-framerate",
            _number_text(sequence.plan.fps),
            "-start_number",
            "1",
            "-i",
            str(frames_root / "frame_%06d.png"),
            "-frames:v",
            str(sequence.plan.expected_frame_count),
            "-c:v",
            "ffv1",
            "-pix_fmt",
            "rgb24",
            str(output_path),
        ]
        try:
            self.runner.run(command)
        except Exception as error:
            raise LosslessWanFrameOutputError(
                "No se pudieron materializar los frames lossless WAN como FFV1."
            ) from error
        if not output_path.exists() or output_path.stat().st_size <= 0:
            raise LosslessWanFrameOutputError(
                "La materialización FFV1 WAN no produjo un clip válido."
            )
        return output_path

    def cleanup_after_success(self, sequence):
        retention = sequence.plan.retention
        if retention is WanArtifactRetention.PRESERVE_ALWAYS:
            return
        artifact_root = self._owned_artifact_root(sequence)
        try:
            shutil.rmtree(artifact_root)
        except OSError as error:
            raise LosslessWanFrameOutputError(
                "No se pudieron limpiar los artefactos lossless WAN poseidos."
            ) from error

    def _capture_output_items(self, history_item, plan):
        try:
            node_output = history_item["outputs"][plan.capture_node_id]
            items = list(node_output["images"])
        except (KeyError, TypeError) as error:
            raise LosslessWanFrameOutputError(
                "ComfyUI no devolvió los PNG lossless esperados para el job WAN."
            ) from error
        if len(items) != plan.expected_frame_count:
            raise LosslessWanFrameOutputError(
                "La captura lossless WAN tiene un número de frames inesperado."
            )
        locations = []
        for item in items:
            if not isinstance(item, dict):
                raise LosslessWanFrameOutputError("Un output PNG WAN es inválido.")
            filename = str(item.get("filename", ""))
            if not filename.lower().endswith(".png"):
                raise LosslessWanFrameOutputError("La captura lossless WAN requiere PNG.")
            locations.append((filename, str(item.get("subfolder", "")), str(item.get("type", "output"))))
        if len(locations) != len(set(locations)):
            raise LosslessWanFrameOutputError("La captura lossless WAN contiene frames duplicados.")
        indexed = []
        for item, location in zip(items, locations):
            match = re.search(r"_(\d+)_\.png$", location[0], flags=re.IGNORECASE)
            if match is None:
                raise LosslessWanFrameOutputError(
                    "El nombre de frame lossless WAN no permite validar su secuencia."
                )
            indexed.append((int(match.group(1)), item))
        indexed.sort(key=lambda pair: pair[0])
        indices = [index for index, _ in indexed]
        expected = list(range(indices[0], indices[0] + plan.expected_frame_count))
        if indices != expected:
            raise LosslessWanFrameOutputError(
                "La captura lossless WAN contiene frames fuera de secuencia."
            )
        return [item for _, item in indexed]

    @staticmethod
    def _validate_png(path, plan):
        header = Path(path).read_bytes()[:33]
        if len(header) < 33 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
            raise LosslessWanFrameOutputError("Un frame lossless WAN no es PNG válido.")
        width = int.from_bytes(header[16:20], "big")
        height = int.from_bytes(header[20:24], "big")
        bit_depth = header[24]
        if (width, height, bit_depth) != (plan.width, plan.height, plan.bit_depth):
            raise LosslessWanFrameOutputError(
                "Un frame lossless WAN no coincide con el contrato de dimensiones."
            )

    @staticmethod
    def _owned_artifact_root(sequence):
        root = Path(sequence.artifact_root).resolve()
        if root.name != sequence.plan.job_id or root.parent.name != ".wan_lossless":
            raise LosslessWanFrameOutputError("La limpieza lossless WAN no posee ese artefacto.")
        return root

    def _owned_frames_root(self, sequence):
        root = self._owned_artifact_root(sequence)
        frames_root = root / "frames"
        expected_paths = tuple(
            (frames_root / f"frame_{index:06d}.png").resolve()
            for index in range(1, sequence.plan.expected_frame_count + 1)
        )
        if tuple(path.resolve() for path in sequence.ordered_frame_paths) != expected_paths:
            raise LosslessWanFrameOutputError("Los frames lossless WAN no pertenecen al job.")
        return frames_root


def _require_plan(plan):
    if not isinstance(plan, WanLosslessCapturePlan):
        raise TypeError("lossless capture requires WanLosslessCapturePlan.")
    return plan


def _sequence_sha256(paths):
    digest = hashlib.sha256()
    for path in paths:
        digest.update(Path(path).read_bytes())
    return digest.hexdigest()


def _number_text(value):
    return format(float(value), "g")
