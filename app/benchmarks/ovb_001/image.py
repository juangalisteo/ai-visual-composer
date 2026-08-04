import base64
import hashlib
import json
from pathlib import Path

from app.backend_adapters.models import ComfyUIPayload
from app.benchmarks.ovb_001.models import (
    BenchmarkExecutionConfig,
    BenchmarkScene,
    GeneratedBenchmarkImage,
)
from app.benchmarks.ovb_001.serialization import canonical_data, write_json
from app.modules.images.image_builder import ImageBuilder


class RealBackendBenchmarkImageGenerator:
    def __init__(
        self,
        image_builder: ImageBuilder | None = None,
    ) -> None:
        self.image_builder = image_builder or ImageBuilder()

    def generate(
        self,
        scene: BenchmarkScene,
        payload: ComfyUIPayload,
        config: BenchmarkExecutionConfig,
        output_dir: Path,
    ) -> GeneratedBenchmarkImage:
        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        image_path = Path(
            self.image_builder._generate_image(
                prompt=payload.prompt,
                scene_number=scene.scene.scene_number,
                output_dir=output_dir,
                width=config.width,
                height=config.height,
            )
        )
        metadata = {
            "benchmark_id": config.benchmark_id,
            "benchmark_version": config.benchmark_version,
            "scene_id": scene.identifier,
            "workflow": config.workflow_id,
            "backend": config.backend_id,
            "model": config.model_id,
            "scheduler": config.scheduler,
            "seed": str(
                config.seed
            ),
            "seed_policy": "recorded; applied only if supported by configured backend workflow",
            "resolution": f"{config.width}x{config.height}",
            "sampler": config.sampler,
            "cfg": str(
                config.cfg
            ),
            "steps": str(
                config.steps
            ),
            "prompt": payload.prompt,
            "negative_prompt": config.negative_prompt,
            "payload_fingerprint": payload.fingerprint,
            "generator_id": "real-backend-image-generator",
            "generation_time": "backend_measured_externally",
        }
        write_json(
            output_dir / "generation_metadata.json",
            metadata,
        )
        return GeneratedBenchmarkImage(
            path=image_path.as_posix(),
            fingerprint=_image_fingerprint(
                image_path,
                metadata,
            ),
            metadata=metadata,
        )


class DeterministicBenchmarkImageGenerator:
    """Creates deterministic image artifacts for benchmark infrastructure tests."""

    _PNG_BYTES = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )

    def generate(
        self,
        scene: BenchmarkScene,
        payload: ComfyUIPayload,
        config: BenchmarkExecutionConfig,
        output_dir: Path,
    ) -> GeneratedBenchmarkImage:
        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        image_path = output_dir / "generated_image.png"
        image_path.write_bytes(
            self._PNG_BYTES
        )
        metadata = {
            "benchmark_id": config.benchmark_id,
            "benchmark_version": config.benchmark_version,
            "scene_id": scene.identifier,
            "workflow": config.workflow_id,
            "backend": config.backend_id,
            "model": config.model_id,
            "scheduler": config.scheduler,
            "seed": str(
                config.seed
            ),
            "resolution": f"{config.width}x{config.height}",
            "sampler": config.sampler,
            "cfg": str(
                config.cfg
            ),
            "steps": str(
                config.steps
            ),
            "prompt": payload.prompt,
            "negative_prompt": config.negative_prompt,
            "payload_fingerprint": payload.fingerprint,
            "generator_id": config.generator_id,
            "generation_time": "deterministic",
        }
        metadata_path = output_dir / "generation_metadata.json"
        write_json(
            metadata_path,
            metadata,
        )
        image_fingerprint = hashlib.sha256(
            json.dumps(
                canonical_data(
                    metadata
                ),
                sort_keys=True,
                separators=(
                    ",",
                    ":",
                ),
                ensure_ascii=False,
            ).encode(
                "utf-8"
            )
            + self._PNG_BYTES
        ).hexdigest()
        return GeneratedBenchmarkImage(
            path=image_path.as_posix(),
            fingerprint=image_fingerprint,
            metadata=metadata,
        )


def _image_fingerprint(
    image_path: Path,
    metadata: dict[str, str],
) -> str:
    return hashlib.sha256(
        json.dumps(
            canonical_data(
                metadata
            ),
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=False,
        ).encode(
            "utf-8"
        )
        + image_path.read_bytes()
    ).hexdigest()
