from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PreparedImageDesign:
    text: str
    source_path: Path
    source: str = "manual_design"
    target: str = "image"
    expected_images: int = 1
