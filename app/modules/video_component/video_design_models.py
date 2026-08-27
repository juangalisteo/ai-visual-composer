from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PreparedVideoDesign:
    text: str
    source_path: Path
    visual_truth: dict
    source: str = "manual_design"
    target: str = "video"
    expected_clips: int = 1
