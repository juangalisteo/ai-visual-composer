import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import subprocess

from app.shared.operational_error import (
    OperationalError,
    create_operational_error,
    summarize_technical_text,
)


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    width: int
    height: int
    fps: float
    pixel_format: str
    video_codec: str
    audio_codec: str | None
    audio_sample_rate: int | None
    audio_channels: int | None
    nominal_fps: float | None = None
    time_base: str | None = None
    sample_aspect_ratio: str | None = None
    audio_channel_layout: str | None = None
    video_duration: float | None = None

    @property
    def has_audio(self):
        return self.audio_codec is not None


class MediaProbe:

    @staticmethod
    def _failure(error, media_path, operation, command=None):
        if isinstance(error, OperationalError):
            raise error
        if isinstance(error, FileNotFoundError):
            family = "FILESYSTEM"
            message = "No se encontro el archivo multimedia solicitado."
            action = "Comprueba que el archivo exista y sea accesible."
        else:
            family = "FFMPEG"
            message = "No se pudo inspeccionar el archivo multimedia con FFprobe."
            action = "Comprueba que FFprobe este disponible y que el archivo sea valido."
        metadata = {}
        if command:
            metadata["command"] = tuple(map(str, command))
        if hasattr(error, "returncode"):
            metadata["returncode"] = error.returncode
        stderr = summarize_technical_text(getattr(error, "stderr", None))
        if stderr:
            metadata["stderr_summary"] = stderr
        raise create_operational_error(
            family=family,
            user_message=message,
            recommended_action=action,
            operation=operation,
            resource=str(media_path),
            technical_metadata=metadata,
        ) from error

    @staticmethod
    def inspect(media_path):
        media_path = Path(media_path)
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            (
                "format=duration:"
                "stream=codec_type,codec_name,width,height,"
                "avg_frame_rate,r_frame_rate,time_base,"
                "sample_aspect_ratio,pix_fmt,duration,sample_rate,channels,"
                "channel_layout"
            ),
            "-of",
            "json",
            str(media_path),
        ]
        try:
            if not media_path.is_file():
                raise FileNotFoundError(
                    f"No existe el archivo multimedia: {media_path}"
                )
            result = subprocess.run(
                command, capture_output=True, text=True, check=True,
            )
            data = json.loads(result.stdout)
            streams = data.get("streams", [])
            video = next(
                (stream for stream in streams if stream.get("codec_type") == "video"),
                None,
            )
            audio = next(
                (stream for stream in streams if stream.get("codec_type") == "audio"),
                None,
            )
            if video is None:
                raise RuntimeError("FFprobe no encontro un stream de video.")

            try:
                duration = float(data["format"]["duration"])
                width = int(video["width"])
                height = int(video["height"])
                fps = float(Fraction(video["avg_frame_rate"]))
                nominal_fps = float(Fraction(video["r_frame_rate"]))
            except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
                raise RuntimeError(
                    "FFprobe devolvio metadata multimedia incompleta."
                ) from error

            if duration <= 0 or width <= 0 or height <= 0 or fps <= 0:
                raise RuntimeError("FFprobe devolvio metadata multimedia no valida.")

            return MediaInfo(
                duration=duration,
                width=width,
                height=height,
                fps=fps,
                pixel_format=str(video.get("pix_fmt", "")),
                video_codec=str(video.get("codec_name", "")),
                audio_codec=(str(audio.get("codec_name", "")) if audio is not None else None),
                audio_sample_rate=(int(audio["sample_rate"]) if audio is not None and audio.get("sample_rate") else None),
                audio_channels=(int(audio["channels"]) if audio is not None and audio.get("channels") else None),
                nominal_fps=nominal_fps,
                time_base=MediaProbe._optional_text(video.get("time_base")),
                sample_aspect_ratio=MediaProbe._optional_text(video.get("sample_aspect_ratio")),
                audio_channel_layout=(MediaProbe._optional_text(audio.get("channel_layout")) if audio is not None else None),
                video_duration=MediaProbe._optional_duration(video.get("duration"), fallback=duration),
            )
        except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError, RuntimeError) as error:
            MediaProbe._failure(
                error, media_path, "Inspeccionar multimedia con FFprobe", command
            )

    @staticmethod
    def _optional_text(value):
        text = str(value or "").strip()
        return text if text and text.upper() != "N/A" else None

    @staticmethod
    def _optional_duration(value, fallback):
        try:
            duration = float(value)
        except (TypeError, ValueError):
            return fallback
        return duration if duration > 0 else fallback

    @staticmethod
    def get_duration(media_path):
        media_path = Path(
            media_path
        )

        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            (
                "default="
                "noprint_wrappers=1:"
                "nokey=1"
            ),
            str(media_path)
        ]

        try:
            if not media_path.exists():
                raise FileNotFoundError(
                    f"No existe el archivo multimedia: {media_path}"
                )
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
            )
            duration_text = result.stdout.strip()
            if not duration_text:
                raise RuntimeError("FFprobe no devolvió la duración del archivo.")
            return float(duration_text)
        except ValueError as error:
            MediaProbe._failure(
                error,
                media_path,
                "Leer duración multimedia con FFprobe",
                command,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, RuntimeError) as error:
            MediaProbe._failure(
                error,
                media_path,
                "Leer duración multimedia con FFprobe",
                command,
            )

    @staticmethod
    def get_video_frame_count(media_path):
        media_path = Path(
            media_path
        )

        command = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(media_path),
        ]

        try:
            if not media_path.exists():
                raise FileNotFoundError(
                    f"No existe el archivo multimedia: {media_path}"
                )
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
            )
            frame_count = int(result.stdout.strip())
        except ValueError as error:
            MediaProbe._failure(
                error,
                media_path,
                "Contar fotogramas con FFprobe",
                command,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as error:
            MediaProbe._failure(
                error,
                media_path,
                "Contar fotogramas con FFprobe",
                command,
            )

        if frame_count <= 0:
            MediaProbe._failure(
                RuntimeError(
                    "FFprobe devolvió un número de fotogramas no positivo."
                ),
                media_path,
                "Contar fotogramas con FFprobe",
                command,
            )

        return frame_count
