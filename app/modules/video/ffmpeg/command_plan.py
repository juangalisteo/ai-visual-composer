from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FFmpegInputPlan:

    arguments: tuple[str, ...]


@dataclass(frozen=True)
class FFmpegOutputOptions:

    filter_complex: str
    audio_index: int
    audio_duration: float
    codec: str
    preset: str
    crf: int
    fps: int
    pixel_format: str
    audio_codec: str
    audio_bitrate: str
    movflags: str
    output_path: Path


@dataclass(frozen=True)
class FFmpegCommandPlan:

    inputs: tuple[FFmpegInputPlan, ...]
    output_options: FFmpegOutputOptions


class CommandPlanBuilder:

    def build(
        self,
        images,
        audio_path,
        output_path,
        filter_complex,
        codec,
        preset,
        crf,
        fps,
        pixel_format,
        audio_codec,
        audio_bitrate,
        movflags,
        audio_duration,
        transition_duration,
        overlay_inputs=(),
        visual_effect_inputs=(),
        overlay_loop_file=True,
        visual_effect_loop_file=True
    ):
        image_count = len(
            images
        )

        if image_count <= 0:
            raise ValueError(
                "No hay imÃ¡genes para construir "
                "el comando de FFmpeg."
            )

        inputs = list(
            self._image_inputs(
                images=images,
                fps=fps,
                audio_duration=audio_duration,
                transition_duration=transition_duration
            )
        )

        inputs.append(
            self._audio_input(
                audio_path
            )
        )

        for overlay_path in overlay_inputs:
            inputs.append(
                self._aux_video_input(
                    path=overlay_path,
                    loop_file=overlay_loop_file,
                    missing_message="No existe el overlay"
                )
            )

        for effect_path in visual_effect_inputs:
            inputs.append(
                self._aux_video_input(
                    path=effect_path,
                    loop_file=visual_effect_loop_file,
                    missing_message=(
                        "No existe el efecto visual"
                    )
                )
            )

        return FFmpegCommandPlan(
            inputs=tuple(
                inputs
            ),
            output_options=FFmpegOutputOptions(
                filter_complex=filter_complex,
                audio_index=image_count,
                audio_duration=audio_duration,
                codec=codec,
                preset=preset,
                crf=crf,
                fps=fps,
                pixel_format=pixel_format,
                audio_codec=audio_codec,
                audio_bitrate=audio_bitrate,
                movflags=movflags,
                output_path=Path(
                    output_path
                )
            )
        )

    def _image_inputs(
        self,
        images,
        fps,
        audio_duration,
        transition_duration
    ):
        image_count = len(
            images
        )
        image_duration = (
            audio_duration
            / image_count
        )

        for index, image in enumerate(
            images
        ):
            input_duration = (
                image_duration
            )

            if index < image_count - 1:
                input_duration += (
                    transition_duration
                )

            yield FFmpegInputPlan(
                arguments=(
                    "-loop",
                    "1",
                    "-framerate",
                    str(
                        fps
                    ),
                    "-t",
                    f"{input_duration:.6f}",
                    "-i",
                    str(
                        Path(image)
                    )
                )
            )

    def _audio_input(
        self,
        audio_path
    ):
        return FFmpegInputPlan(
            arguments=(
                "-i",
                str(
                    Path(audio_path)
                )
            )
        )

    def _aux_video_input(
        self,
        path,
        loop_file,
        missing_message
    ):
        path = Path(
            path
        )

        if not path.exists():
            raise FileNotFoundError(
                f"{missing_message}: {path}"
            )

        arguments = []

        if loop_file:
            arguments.extend([
                "-stream_loop",
                "-1"
            ])

        arguments.extend([
            "-i",
            str(
                path
            )
        ])

        return FFmpegInputPlan(
            arguments=tuple(
                arguments
            )
        )
