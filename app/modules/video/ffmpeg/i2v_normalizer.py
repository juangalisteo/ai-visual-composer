from dataclasses import replace
from pathlib import Path
import time

from app.modules.video.ffmpeg.runner import Runner
from app.modules.video.video_validator import VideoValidator
from app.shared.media_probe import MediaProbe
from app.shared.operational_error import (
    OperationalError,
    create_operational_error,
    summarize_technical_text,
)
import subprocess


class I2VClipNormalizer:

    def normalize(
        self,
        build_context,
        diagnostics,
    ):
        media = build_context.media
        video_indexes = tuple(
            index
            for index in range(len(media.image_paths))
            if self._media_type(media, index) == "video"
        )

        if not video_indexes:
            return build_context

        total_start = time.perf_counter()
        diagnostics.start_normalization()
        normalized_directory = (
            Path(media.output_path).parent
            / "i2v_normalized"
        )
        normalized_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        normalized_paths = list(media.image_paths)
        normalized_durations = list(media.media_durations)

        try:
            for index in video_indexes:
                duration = self._scene_duration(
                    build_context,
                    index,
                )
                source_path = media.image_paths[index]
                output_path = (
                    normalized_directory
                    / f"scene_{index + 1:03d}.mp4"
                )
                command = self.build_command(
                    source_path=source_path,
                    output_path=output_path,
                    source_frame_count=(
                        MediaProbe.get_video_frame_count(
                            source_path
                        )
                    ),
                    duration=duration,
                    config=build_context.config,
                )
                clip_start = time.perf_counter()

                try:
                    result = Runner().run(command)
                    elapsed = time.perf_counter() - clip_start
                    VideoValidator().validate(
                        output_path=output_path,
                        expected_duration=duration,
                        max_duration_difference=(
                            build_context
                            .config
                            .validation
                            .max_duration_difference
                        ),
                    )
                except Exception as error:
                    diagnostics.record_normalized_clip(
                        scene_number=index + 1,
                        command=command,
                        elapsed=time.perf_counter() - clip_start,
                        stderr=self._stderr(error),
                        status="FAILED",
                    )
                    if isinstance(error, OperationalError):
                        raise
                    if isinstance(error, subprocess.CalledProcessError):
                        metadata = {
                            "command": tuple(map(str, error.cmd or command)),
                            "returncode": error.returncode,
                            "phase": "i2v_normalization",
                            "scene_number": index + 1,
                        }
                        stderr = summarize_technical_text(error.stderr)
                        if stderr:
                            metadata["stderr_summary"] = stderr
                        raise create_operational_error(
                            family="FFMPEG",
                            user_message="FFmpeg no pudo normalizar el clip I2V.",
                            recommended_action="Revisa el diagnostico de FFmpeg generado para esta escena.",
                            operation="Normalizar clip I2V",
                            resource=str(output_path),
                            diagnostic_reference=str(diagnostics.path),
                            technical_metadata=metadata,
                        ) from error
                    raise

                diagnostics.record_normalized_clip(
                    scene_number=index + 1,
                    command=command,
                    elapsed=elapsed,
                    stderr=getattr(result, "stderr", ""),
                )
                normalized_paths[index] = output_path
                normalized_durations[index] = duration

        except Exception:
            diagnostics.finish_normalization(
                elapsed=time.perf_counter() - total_start,
                status="FAILED",
            )
            raise

        diagnostics.finish_normalization(
            elapsed=time.perf_counter() - total_start,
        )
        return replace(
            build_context,
            media=replace(
                media,
                image_paths=tuple(normalized_paths),
                media_durations=tuple(normalized_durations),
            ),
        )

    def build_command(
        self,
        source_path,
        output_path,
        source_frame_count,
        duration,
        config,
    ):
        filter_complex = self.build_filter(
            source_frame_count=source_frame_count,
            duration=duration,
            width=config.width,
            height=config.height,
            fps=config.fps,
            pixel_format=config.pixel_format,
        )
        return [
            "ffmpeg",
            "-y",
            "-i",
            str(Path(source_path)),
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-an",
            "-c:v",
            config.codec,
            "-preset",
            config.preset,
            "-crf",
            str(config.crf),
            "-r",
            str(config.fps),
            "-pix_fmt",
            config.pixel_format,
            "-movflags",
            config.movflags,
            str(Path(output_path)),
        ]

    def build_filter(
        self,
        source_frame_count,
        duration,
        width,
        height,
        fps,
        pixel_format,
    ):
        source_frame_count = max(1, int(source_frame_count))
        parts = [
            "[0:v]trim=start_frame=0:"
            f"end_frame={source_frame_count},"
            "setpts=PTS-STARTPTS[source]"
        ]

        if source_frame_count > 2:
            reverse_frame_count = source_frame_count - 2
            period_frame_count = (
                source_frame_count + reverse_frame_count
            )
            parts.extend([
                "[source]split=2[forward][reverse_source]",
                "[reverse_source]reverse,"
                "trim=start_frame=1:"
                f"end_frame={source_frame_count - 1},"
                "setpts=PTS-STARTPTS[reverse_trimmed]",
                "[forward][reverse_trimmed]"
                "concat=n=2:v=1:a=0[pingpong_period]",
                "[pingpong_period]loop=loop=-1:"
                f"size={period_frame_count}:start=0,"
                f"trim=duration={duration:.6f},"
                "setpts=PTS-STARTPTS[looped]",
            ])
        else:
            parts.append(
                "[source]loop=loop=-1:"
                f"size={source_frame_count}:start=0,"
                f"trim=duration={duration:.6f},"
                "setpts=PTS-STARTPTS[looped]"
            )

        parts.append(
            "[looped]"
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"fps={fps},"
            f"format={pixel_format},"
            "setsar=1,"
            "settb=AVTB,"
            "setpts=PTS-STARTPTS[vout]"
        )
        return ";".join(parts)

    def _scene_duration(
        self,
        build_context,
        index,
    ):
        duration = build_context.timeline.image_duration
        is_last = index == len(build_context.media.image_paths) - 1
        if (
            build_context.config.transitions.enabled
            and not is_last
        ):
            duration += build_context.config.transitions.duration
        return duration

    def _media_type(
        self,
        media,
        index,
    ):
        media_types = getattr(media, "media_types", ())
        if not media_types:
            return "image"
        return str(media_types[index]).strip().lower()

    def _stderr(
        self,
        error,
    ):
        return str(getattr(error, "stderr", "") or "")
