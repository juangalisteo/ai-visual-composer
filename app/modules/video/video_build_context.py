from dataclasses import dataclass


@dataclass(frozen=True)
class VideoBuildContext:

    config: object
    media: object
    timeline: object


@dataclass(frozen=True)
class VideoBuildComponents:

    motion_builder: object
    transition_builder: object
    overlay_builder: object
    visual_effect_builder: object


@dataclass(frozen=True)
class VideoBuildArtifacts:

    filter_complex: str
    command: list[str]
    render_output_path: object = None
