from dataclasses import dataclass
from pathlib import Path
import random


@dataclass(frozen=True)
class StudioLightLeakSegment:
    start_time: float
    end_time: float
    active: bool

    @property
    def duration(self):
        return self.end_time - self.start_time


@dataclass(frozen=True)
class StudioLightLeakOperation:
    start_time: float
    end_time: float
    asset_path: Path
    input_position: int
    opacity: float
    blend_mode: str


class StudioLightLeaksPlanner:

    def __init__(self, config):
        self.config = config

    def build(self, duration):
        if duration <= 0:
            raise ValueError("La duracion STUDIO debe ser positiva.")

        segments = []
        start_time = 0.0
        active = True
        while start_time < duration:
            segment_duration = (
                self.config.active_duration_seconds
                if active
                else self.config.clean_duration_seconds
            )
            end_time = min(duration, start_time + segment_duration)
            segments.append(
                StudioLightLeakSegment(
                    start_time=start_time,
                    end_time=end_time,
                    active=active,
                )
            )
            start_time = end_time
            active = not active
        return tuple(segments)


class StudioLightLeakSelector:

    extensions = frozenset({".mov", ".mp4"})

    def __init__(
        self,
        directory=Path("assets/videos/overlays/Light Leaks"),
        rng=None,
    ):
        self.directory = Path(directory)
        self.rng = rng or random.SystemRandom()
        self.previous_asset = None

    def select(self, avoid_immediate_repeat):
        if not self.directory.exists():
            raise FileNotFoundError(
                "No existe la carpeta STUDIO de Light Leaks: "
                f"{self.directory}"
            )
        if not self.directory.is_dir():
            raise NotADirectoryError(
                "La ruta STUDIO de Light Leaks no es una carpeta: "
                f"{self.directory}"
            )

        candidates = tuple(
            sorted(
                (
                    path.resolve()
                    for path in self.directory.iterdir()
                    if path.is_file() and path.suffix.lower() in self.extensions
                ),
                key=lambda path: path.name.lower(),
            )
        )
        if not candidates:
            raise FileNotFoundError(
                "STUDIO requiere al menos un asset valido en Light Leaks."
            )

        available = candidates
        if (
            avoid_immediate_repeat
            and self.previous_asset is not None
            and len(candidates) > 1
        ):
            available = tuple(
                asset for asset in candidates
                if asset != self.previous_asset
            )

        selected = self.rng.choice(available)
        self.previous_asset = selected
        return selected


class StudioLightLeaksPlanBuilder:

    def __init__(self, planner, selector):
        self.planner = planner
        self.selector = selector

    def build(self, duration):
        operations = []
        for segment in self.planner.build(duration):
            if not segment.active:
                continue
            operations.append(
                StudioLightLeakOperation(
                    start_time=segment.start_time,
                    end_time=segment.end_time,
                    asset_path=self.selector.select(
                        self.planner.config.avoid_immediate_repeat
                    ),
                    input_position=len(operations),
                    opacity=self.planner.config.opacity,
                    blend_mode=self.planner.config.blend_mode,
                )
            )
        return tuple(operations)
