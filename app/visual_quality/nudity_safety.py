from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.visual_quality.factory import create_validation_failure
from app.visual_quality.models import GeneratedAsset, ValidationContext


NUDITY_FAILURE_TYPE = "nudity_detected"


@dataclass(frozen=True)
class NuditySafetyConfig:
    model_path: Path = Path("models/visual_safety/nudenet-320n.onnx")
    model_id: str = "nudenet-320n"
    model_version: str = "nudenet==3.4.2"
    explicit_threshold: float = 0.65
    buttocks_threshold: float = 0.80


class NuditySafetyCheck:
    """Pixel-only local NudeNet safety check for generated images."""

    name = NUDITY_FAILURE_TYPE
    check_category = "safety"

    _explicit_classes = frozenset(
        {
            "FEMALE_GENITALIA_EXPOSED",
            "MALE_GENITALIA_EXPOSED",
            "ANUS_EXPOSED",
            "FEMALE_BREAST_EXPOSED",
        }
    )
    _buttocks_class = "BUTTOCKS_EXPOSED"

    def __init__(
        self,
        config: NuditySafetyConfig | None = None,
        detector=None,
    ) -> None:
        self.config = config or NuditySafetyConfig()
        self._detector = detector

    def check(
        self,
        asset: GeneratedAsset,
        context: ValidationContext,
    ) -> tuple:
        del context
        try:
            detections = self._detect(asset)
        except Exception as error:
            from app.visual_quality.image_validator import ValidationCheckError

            raise ValidationCheckError(
                self.name,
                "NuditySafetyCheck could not load or execute the local model: "
                f"{type(error).__name__}: {error}",
            ) from error

        relevant = tuple(
            detection
            for detection in detections
            if self._is_nudity_detection(detection)
        )
        if not relevant:
            return ()

        strongest = max(
            relevant,
            key=lambda detection: float(detection["score"]),
        )
        return (
            create_validation_failure(
                failure_type=NUDITY_FAILURE_TYPE,
                severity="high",
                confidence=float(strongest["score"]),
                evidence=self._evidence(relevant),
                technical_message=(
                    "NuditySafetyCheck rejected the generated image from "
                    "local pixel detections."
                ),
                retry_relevant=True,
                region=tuple(strongest["box"]),
            ),
        )

    def _detect(
        self,
        asset: GeneratedAsset,
    ) -> tuple[dict, ...]:
        image_path = Path(
            asset.local_artifact_path or asset.path
        )
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        detector = self._detector or self._load_detector()
        return tuple(detector.detect(str(image_path)))

    def _load_detector(self):
        model_path = self.config.model_path
        if not model_path.is_file():
            raise FileNotFoundError(model_path)
        from nudenet import NudeDetector

        self._detector = NudeDetector(model_path=str(model_path))
        return self._detector

    def _is_nudity_detection(
        self,
        detection: dict,
    ) -> bool:
        label = str(detection.get("class", ""))
        score = float(detection.get("score", 0.0))
        if label in self._explicit_classes:
            return score >= self.config.explicit_threshold
        return (
            label == self._buttocks_class
            and score >= self.config.buttocks_threshold
        )

    def _evidence(
        self,
        detections: tuple[dict, ...],
    ) -> str:
        payload = {
            "model_id": self.config.model_id,
            "model_version": self.config.model_version,
            "model_sha256": _sha256(self.config.model_path),
            "explicit_threshold": self.config.explicit_threshold,
            "buttocks_threshold": self.config.buttocks_threshold,
            "detections": [
                {
                    "class": str(detection["class"]),
                    "score": round(float(detection["score"]), 6),
                    "box": [int(value) for value in detection["box"]],
                }
                for detection in detections
            ],
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as model_file:
        for block in iter(lambda: model_file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
