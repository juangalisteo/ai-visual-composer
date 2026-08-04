import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from app.evidence.image_evidence_policy import (
    ARTIFACT_FILENAMES,
    ImageEvidencePathPolicy,
)


SCHEMA_VERSION = "1.0.0"
INDEX_VERSION = "image-evidence-index-v1"


class EvidenceArtifactStatus(Enum):
    EXPECTED = "expected"
    AVAILABLE = "available"
    MISSING = "missing"


@dataclass(frozen=True)
class EvidenceArtifactReference:
    artifact_id: str
    filename: str
    relative_path: str
    status: EvidenceArtifactStatus = EvidenceArtifactStatus.EXPECTED
    fingerprint: str = ""

    def __post_init__(self) -> None:
        _require_text(
            self.artifact_id,
            "artifact_id",
        )
        _require_text(
            self.filename,
            "filename",
        )
        _require_relative_path(
            self.relative_path,
            "relative_path",
        )
        _require_enum(
            self.status,
            EvidenceArtifactStatus,
            "status",
        )


@dataclass(frozen=True)
class ImageEvidenceIndex:
    scene_number: int
    scene_directory: str
    artifacts: tuple[EvidenceArtifactReference, ...]
    schema_version: str = SCHEMA_VERSION
    version: str = INDEX_VERSION
    fingerprint: str = field(
        default="",
        init=False,
    )

    def __post_init__(self) -> None:
        _validate_scene_number(
            self.scene_number
        )
        _require_relative_path(
            self.scene_directory,
            "scene_directory",
        )
        _require_sequence_of(
            self.artifacts,
            EvidenceArtifactReference,
            "artifacts",
        )
        _require_text(
            self.schema_version,
            "schema_version",
        )
        _require_text(
            self.version,
            "version",
        )
        object.__setattr__(
            self,
            "fingerprint",
            deterministic_fingerprint(
                "ImageEvidenceIndex",
                {
                    "scene_number": self.scene_number,
                    "scene_directory": self.scene_directory,
                    "artifacts": self.artifacts,
                    "schema_version": self.schema_version,
                    "version": self.version,
                },
            ),
        )

    def to_dict(
        self
    ) -> dict[str, Any]:
        return _canonical_mapping(
            self
        )


def build_image_evidence_index(
    scene_number: int,
    policy: ImageEvidencePathPolicy | None = None,
    artifact_ids: tuple[str, ...] | None = None,
) -> ImageEvidenceIndex:
    policy = policy or ImageEvidencePathPolicy()
    artifact_ids = (
        artifact_ids
        if artifact_ids is not None
        else tuple(
            sorted(
                ARTIFACT_FILENAMES
            )
        )
    )
    _validate_artifact_ids(
        artifact_ids
    )
    artifacts = tuple(
        EvidenceArtifactReference(
            artifact_id=artifact_id,
            filename=policy.artifact_filename(
                artifact_id
            ),
            relative_path=_path_text(
                policy.artifact_relative_path(
                    scene_number,
                    artifact_id,
                )
            ),
        )
        for artifact_id in artifact_ids
    )
    return ImageEvidenceIndex(
        scene_number=scene_number,
        scene_directory=_path_text(
            policy.scene_directory_relative(
                scene_number
            )
        ),
        artifacts=artifacts,
    )


def deterministic_fingerprint(
    label: str,
    value: Any,
) -> str:
    canonical = {
        label: _canonical_mapping(
            value
        )
    }
    return hashlib.sha256(
        json.dumps(
            canonical,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _validate_artifact_ids(
    artifact_ids: tuple[str, ...]
) -> None:
    if not isinstance(
        artifact_ids,
        tuple,
    ):
        raise ValueError(
            "artifact_ids must be a tuple."
        )
    for artifact_id in artifact_ids:
        if artifact_id not in ARTIFACT_FILENAMES:
            raise ValueError(
                f"Unknown image evidence artifact: {artifact_id}"
            )


def _validate_scene_number(
    scene_number: int
) -> None:
    if not isinstance(
        scene_number,
        int,
    ) or scene_number <= 0:
        raise ValueError(
            "scene_number must be a positive integer."
        )


def _require_text(
    value: str,
    field_name: str,
) -> None:
    if not isinstance(
        value,
        str,
    ) or not value.strip():
        raise ValueError(
            f"{field_name} must be a non-empty string."
        )


def _require_relative_path(
    value: str,
    field_name: str,
) -> None:
    _require_text(
        value,
        field_name,
    )
    if Path(
        value
    ).is_absolute():
        raise ValueError(
            f"{field_name} must be a relative path."
        )


def _require_enum(
    value: Any,
    enum_type: type[Enum],
    field_name: str,
) -> None:
    if not isinstance(
        value,
        enum_type,
    ):
        raise ValueError(
            f"{field_name} must be a {enum_type.__name__} value."
        )


def _require_sequence_of(
    values: tuple[Any, ...],
    expected_type: type,
    field_name: str,
) -> None:
    if not isinstance(
        values,
        tuple,
    ):
        raise ValueError(
            f"{field_name} must be a tuple."
        )
    for value in values:
        if not isinstance(
            value,
            expected_type,
        ):
            raise ValueError(
                f"{field_name} must contain only "
                f"{expected_type.__name__} values."
            )


def _canonical_mapping(
    value: Any
) -> Any:
    if isinstance(
        value,
        Enum,
    ):
        return value.value
    if is_dataclass(
        value
    ):
        return {
            key: _canonical_mapping(
                item
            )
            for key, item in asdict(
                value
            ).items()
        }
    if isinstance(
        value,
        dict,
    ):
        return {
            key: _canonical_mapping(
                item
            )
            for key, item in sorted(
                value.items()
            )
        }
    if isinstance(
        value,
        (
            tuple,
            list,
        ),
    ):
        return [
            _canonical_mapping(
                item
            )
            for item in value
        ]
    return value


def _path_text(
    path: Path
) -> str:
    return path.as_posix()
