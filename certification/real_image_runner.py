from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from app.managers.project_manager import ProjectManager
from app.modules.images.image_builder import ImageBuilder
from certification.image_component import ImageCertificationObservation
from certification.models import CertificationScenario


@dataclass(frozen=True)
class RealImageRunnerConfig:
    campaign_id: str = "rc0_quick"
    base_output_dir: Path = Path("output") / "certification"
    profile_path: Path = Path(
        "config/profiles/youtube/modo_conciencia.json"
    )
    workflow_path: Path = Path(
        "config/comfyui_flux_workflow_api.json"
    )
    comfyui_url: str = "http://127.0.0.1:8188"
    image_validation_enabled: bool = True
    keep_rejected_heavy_artifacts: bool = False


class RealImageComponentRunner:
    def __init__(
        self,
        config: RealImageRunnerConfig | None = None
    ) -> None:
        self.config = config or RealImageRunnerConfig()

    def __call__(
        self,
        scenario: CertificationScenario
    ) -> ImageCertificationObservation:
        start = time.perf_counter()
        scenario_dir = (
            self.config.base_output_dir
            / self.config.campaign_id
            / scenario.scenario_id
        )
        scenario_dir.mkdir(
            parents=True,
            exist_ok=True
        )
        project_name = (
            f"{self.config.campaign_id}_{scenario.scenario_id}"
        )
        previous_profile = os.environ.get(
            "MC_PROFILE_PATH"
        )
        previous_project = os.environ.get(
            "MC_PROJECT_NAME"
        )

        try:
            profile_path = self._write_campaign_profile(
                scenario_dir
            )
            os.environ[
                "MC_PROFILE_PATH"
            ] = str(
                profile_path
            )
            os.environ[
                "MC_PROJECT_NAME"
            ] = project_name

            project = ProjectManager()
            project.setup()
            self._write_storyboard(
                project.storyboard_path(),
                scenario
            )

            manifest_path = ImageBuilder(
                comfyui_url=self.config.comfyui_url,
                workflow_path=self.config.workflow_path
            ).build(
                storyboard_path=project.storyboard_path(),
                output_dir=project.images_dir(),
            )

            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )
            approved_asset = Path(
                manifest[0][
                    "image"
                ]
            )
            metadata = self._metadata(
                scenario=scenario,
                manifest_path=manifest_path,
                approved_asset=approved_asset,
                scenario_dir=scenario_dir,
            )
            self._write_observation_file(
                scenario_dir=scenario_dir,
                metadata=metadata,
                status="PASS",
                errors=(),
            )
            self._apply_retention(
                project.images_dir()
            )
            return ImageCertificationObservation(
                approved=True,
                attempts=1,
                retry_count=0,
                manual_review=False,
                stopped=False,
                execution_time=round(
                    time.perf_counter()
                    - start,
                    4
                ),
                details="real image generated",
                metadata=metadata,
            )
        except Exception as error:
            metadata = (
                (
                    "scenario_id",
                    scenario.scenario_id,
                ),
                (
                    "category",
                    _category(
                        scenario
                    ),
                ),
                (
                    "scenario_dir",
                    _stable_path(
                        scenario_dir
                    ),
                ),
            )
            self._write_observation_file(
                scenario_dir=scenario_dir,
                metadata=metadata,
                status="FAIL",
                errors=(
                    str(
                        error
                    ),
                ),
            )
            return ImageCertificationObservation(
                status="FAIL",
                attempts=0,
                approved=False,
                retry_count=0,
                manual_review=False,
                stopped=True,
                execution_time=round(
                    time.perf_counter()
                    - start,
                    4
                ),
                details="real image generation failed",
                errors=(
                    str(
                        error
                    ),
                ),
                metadata=metadata,
            )
        finally:
            _restore_env(
                "MC_PROFILE_PATH",
                previous_profile
            )
            _restore_env(
                "MC_PROJECT_NAME",
                previous_project
            )

    def _write_campaign_profile(
        self,
        scenario_dir: Path
    ) -> Path:
        profile = json.loads(
            self.config.profile_path.read_text(
                encoding="utf-8"
            )
        )
        profile[
            "image_validation"
        ] = {
            "enabled": self.config.image_validation_enabled
        }
        profile.setdefault(
            "visual_director",
            {}
        )[
            "enabled"
        ] = True
        profile_path = (
            scenario_dir
            / "profile.rc0.json"
        )
        profile_path.write_text(
            json.dumps(
                profile,
                ensure_ascii=False,
                indent=4
            ),
            encoding="utf-8"
        )
        return profile_path

    def _write_storyboard(
        self,
        storyboard_path: Path,
        scenario: CertificationScenario
    ) -> None:
        storyboard_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )
        storyboard_path.write_text(
            json.dumps(
                [
                    {
                        "scene": 1,
                        "text": _scene_text(
                            scenario
                        ),
                        **_visual_truth(
                            scenario
                        ),
                        "duration": 10,
                    }
                ],
                ensure_ascii=False,
                indent=4
            ),
            encoding="utf-8"
        )

    def _metadata(
        self,
        *,
        scenario: CertificationScenario,
        manifest_path: Path,
        approved_asset: Path,
        scenario_dir: Path
    ) -> tuple[tuple[str, str], ...]:
        asset_size = (
            approved_asset.stat().st_size
            if approved_asset.exists()
            else 0
        )
        return (
            (
                "scenario_id",
                scenario.scenario_id,
            ),
            (
                "category",
                _category(
                    scenario
                ),
            ),
            (
                "approved_asset",
                _stable_path(
                    approved_asset
                ),
            ),
            (
                "manifest_path",
                _stable_path(
                    manifest_path
                ),
            ),
            (
                "history_id",
                f"history-{scenario.scenario_id}",
            ),
            (
                "seed",
                "unavailable",
            ),
            (
                "asset_size",
                str(
                    asset_size
                ),
            ),
            (
                "asset_fingerprint",
                _file_fingerprint(
                    approved_asset
                ),
            ),
            (
                "scenario_dir",
                _stable_path(
                    scenario_dir
                ),
            ),
        )

    def _write_observation_file(
        self,
        *,
        scenario_dir: Path,
        metadata: tuple[tuple[str, str], ...],
        status: str,
        errors: tuple[str, ...],
    ) -> None:
        observation_path = (
            scenario_dir
            / "observation.json"
        )
        observation_path.write_text(
            json.dumps(
                {
                    "status": status,
                    "metadata": dict(
                        metadata
                    ),
                    "errors": list(
                        errors
                    ),
                },
                ensure_ascii=False,
                indent=4,
                sort_keys=True,
            ),
            encoding="utf-8"
        )

    def _apply_retention(
        self,
        images_dir: Path
    ) -> None:
        attempts_dir = (
            images_dir
            / "_quality_attempts"
        )
        if (
            attempts_dir.exists()
            and not self.config.keep_rejected_heavy_artifacts
        ):
            shutil.rmtree(
                attempts_dir
            )


def _scene_text(
    scenario: CertificationScenario
) -> str:
    return (
        "Certification scenario "
        f"{scenario.name}: {scenario.objective}"
    )


def _visual_truth(
    scenario: CertificationScenario
) -> dict[str, object]:
    category = _category(
        scenario
    )
    scenes = {
        "portrait": (
            "thoughtful adult person",
            "holds a calm frontal presence",
            "quiet professional studio",
            "controlled indoor session",
            ("neutral backdrop", "soft practical chair"),
            ("the subject stays separated from the background",),
            ("stable identity", "consistent modest wardrobe"),
            "identity stability certification",
            "A cinematic portrait of a thoughtful person in a quiet studio.",
            ("no readable text", "modest wardrobe", "realistic anatomy"),
        ),
        "context": (
            "empty hospital corridor",
            "waits in calm documentary silence",
            "clean hospital interior",
            "daytime clinical atmosphere",
            ("hospital doors", "soft overhead lights"),
            ("the corridor extends into the background",),
            ("same clinical environment",),
            "contextual environment certification",
            "A calm hospital corridor prepared for a documentary scene.",
            ("no readable text", "no logos", "no patient exposure"),
        ),
        "fantasy": (
            "ancient archive chamber",
            "glows with quiet atmospheric mystery",
            "fantasy stone archive",
            "timeless interior",
            ("stone shelves", "sealed artifacts"),
            ("artifacts rest deep within the chamber",),
            ("consistent fantasy archive",),
            "fantasy environment certification",
            "An ancient fantasy archive illuminated by soft atmospheric light.",
            ("no readable text", "no modern objects"),
        ),
        "nature": (
            "forest path",
            "leads through layered morning trees",
            "natural woodland",
            "early morning",
            ("trees", "mist", "path"),
            ("the path recedes between layered trees",),
            ("same natural morning atmosphere",),
            "nature certification",
            "A forest path with layered trees and natural morning atmosphere.",
            ("no readable text", "no artificial structures"),
        ),
        "animals": (
            "animal in natural habitat",
            "rests calmly without theatrical posing",
            "wild natural environment",
            "soft daylight",
            ("natural ground", "background vegetation"),
            ("the animal remains grounded in its habitat",),
            ("respectful documentary framing",),
            "animal safety certification",
            "A respectful documentary image of an animal in its natural habitat.",
            ("no human clothing", "no unnatural anatomy", "no readable text"),
        ),
        "anatomy": (
            "human hands",
            "hold a simple object carefully",
            "practical tabletop setting",
            "neutral indoor light",
            ("simple object", "table surface"),
            ("the object sits between both hands",),
            ("same hands", "same object"),
            "anatomy certification",
            "A close practical scene focused on hands holding a simple object.",
            ("realistic hands", "correct finger count", "no readable text"),
        ),
        "wardrobe": (
            "cinematic character",
            "stands in coherent modest clothing",
            "neutral interior",
            "controlled portrait moment",
            ("coat", "plain shirt"),
            ("wardrobe fits naturally on the character",),
            ("consistent wardrobe",),
            "wardrobe certification",
            "A cinematic character wearing coherent modest clothing.",
            ("modest clothing", "no nudity", "no logos", "no readable text"),
        ),
        "identity": (
            "same cinematic character",
            "maintains stable identity and expression",
            "quiet portrait environment",
            "soft interior light",
            ("recognizable face", "consistent hairstyle"),
            ("the character remains centered in a stable portrait setup",),
            ("same age", "same face", "same hairstyle"),
            "identity continuity certification",
            "A consistent cinematic character portrait with stable identity.",
            ("no identity drift", "no age change", "no readable text"),
        ),
        "continuity": (
            "coherent place",
            "preserves the same visual mood",
            "continuous cinematic environment",
            "matching scene atmosphere",
            ("recurring environment detail",),
            ("foreground and background preserve spatial logic",),
            ("same place", "same mood", "same atmosphere"),
            "continuity certification",
            "A scene that should preserve a coherent place and visual mood.",
            ("no abrupt environment change", "no readable text"),
        ),
        "retry": (
            "technically demanding subject",
            "tests retry behavior under controlled conditions",
            "neutral certification environment",
            "controlled light",
            ("primary test object", "background structure"),
            ("the object remains readable without text",),
            ("retry attempt consistency",),
            "retry behavior certification",
            "A technically demanding image used to observe retry behavior.",
            ("no readable text", "stable subject", "realistic anatomy"),
        ),
        "rollback": (
            "baseline cinematic scene",
            "holds a simple stable composition",
            "neutral cinematic environment",
            "balanced lighting",
            ("main subject", "simple background"),
            ("subject and background remain clearly separated",),
            ("rollback baseline consistency",),
            "rollback readiness certification",
            "A baseline cinematic scene used to verify rollback readiness.",
            ("no readable text", "no logos"),
        ),
        "history": (
            "traceable certification scene",
            "preserves asset history behavior",
            "controlled archive environment",
            "neutral documentation light",
            ("traceable object", "archive surface"),
            ("the object remains anchored on the archive surface",),
            ("stable asset history",),
            "asset history certification",
            "A traceable scene used to verify asset history behavior.",
            ("no readable text", "no volatile details"),
        ),
    }
    visual_truth = scenes.get(
        category,
        (
            "cinematic certification subject",
            "holds a clear visual state",
            "controlled certification environment",
            "neutral cinematic moment",
            ("primary visible element",),
            ("the primary element remains clearly placed",),
            ("stable certification baseline",),
            "general image certification",
            "A cinematic certification scene with clear visual structure.",
            ("no readable text", "no logos", "realistic anatomy"),
        ),
    )
    (
        visible_subject,
        visible_action,
        visible_environment,
        time_context,
        key_objects,
        spatial_relationships,
        continuity_links,
        abstract_source,
        filmable_interpretation,
        visual_constraints,
    ) = visual_truth
    return {
        "visible_subject": visible_subject,
        "visible_action": visible_action,
        "visible_environment": visible_environment,
        "time_context": time_context,
        "key_objects": list(
            key_objects
        ),
        "spatial_relationships": list(
            spatial_relationships
        ),
        "continuity_links": list(
            continuity_links
        ),
        "abstract_source": abstract_source,
        "filmable_interpretation": filmable_interpretation,
        "visual_constraints": list(
            visual_constraints
        ),
        "visual_truth_status": "structured",
    }


def _category(
    scenario: CertificationScenario
) -> str:
    for tag in scenario.tags:
        if tag != "image":
            return tag
    return "image"


def _stable_path(
    path: Path
) -> str:
    return str(
        path
    ).replace(
        "\\",
        "/"
    )


def _file_fingerprint(
    path: Path
) -> str:
    if not path.exists():
        return ""
    import hashlib

    digest = hashlib.sha256()
    with path.open(
        "rb"
    ) as file:
        for chunk in iter(
            lambda: file.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(
                chunk
            )
    return digest.hexdigest()


def _restore_env(
    name: str,
    value: str | None
) -> None:
    if value is None:
        os.environ.pop(
            name,
            None
        )
    else:
        os.environ[
            name
        ] = value
