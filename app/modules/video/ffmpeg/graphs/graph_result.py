from dataclasses import dataclass


@dataclass(frozen=True)
class GraphResult:
    """
    Resultado devuelto por una etapa del grafo FFmpeg.
    """

    parts: list[str]

    current_stream: str = ""

    video_streams: tuple[
        str,
        ...
    ] = ()

    visual_effect_streams: tuple[
        str,
        ...
    ] = ()

    overlay_streams: tuple[
        str,
        ...
    ] = ()
