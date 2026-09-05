import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import subprocess


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

    @property
    def has_audio(self):
        return self.audio_codec is not None


class MediaProbe:

    @staticmethod
    def inspect(media_path):
        media_path = Path(media_path)
        if not media_path.is_file():
            raise FileNotFoundError(
                f"No existe el archivo multimedia: {media_path}"
            )

        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                (
                    "format=duration:"
                    "stream=codec_type,codec_name,width,height,"
                    "avg_frame_rate,pix_fmt,sample_rate,channels"
                ),
                "-of",
                "json",
                str(media_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        video = next(
            (
                stream
                for stream in streams
                if stream.get("codec_type") == "video"
            ),
            None,
        )
        audio = next(
            (
                stream
                for stream in streams
                if stream.get("codec_type") == "audio"
            ),
            None,
        )
        if video is None:
            raise RuntimeError(
                "FFprobe no encontro un stream de video."
            )

        try:
            duration = float(data["format"]["duration"])
            width = int(video["width"])
            height = int(video["height"])
            fps = float(Fraction(video["avg_frame_rate"]))
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
            raise RuntimeError(
                "FFprobe devolvio metadata multimedia incompleta."
            ) from error

        if duration <= 0 or width <= 0 or height <= 0 or fps <= 0:
            raise RuntimeError(
                "FFprobe devolvio metadata multimedia no valida."
            )

        return MediaInfo(
            duration=duration,
            width=width,
            height=height,
            fps=fps,
            pixel_format=str(video.get("pix_fmt", "")),
            video_codec=str(video.get("codec_name", "")),
            audio_codec=(
                str(audio.get("codec_name", ""))
                if audio is not None
                else None
            ),
            audio_sample_rate=(
                int(audio["sample_rate"])
                if audio is not None and audio.get("sample_rate")
                else None
            ),
            audio_channels=(
                int(audio["channels"])
                if audio is not None and audio.get("channels")
                else None
            ),
        )

    @staticmethod
    def get_duration(media_path):
        media_path = Path(
            media_path
        )

        if not media_path.exists():
            raise FileNotFoundError(
                f"No existe el archivo multimedia: "
                f"{media_path}"
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

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )

        duration_text = (
            result.stdout.strip()
        )

        if not duration_text:
            raise RuntimeError(
                "FFprobe no devolvió "
                "la duración del archivo."
            )

        try:
            return float(
                duration_text
            )

        except ValueError as error:
            raise RuntimeError(
                "FFprobe devolvió una duración "
                "que no se pudo interpretar."
            ) from error

    @staticmethod
    def get_video_frame_count(media_path):
        media_path = Path(
            media_path
        )

        if not media_path.exists():
            raise FileNotFoundError(
                f"No existe el archivo multimedia: "
                f"{media_path}"
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

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )

        try:
            frame_count = int(
                result.stdout.strip()
            )
        except ValueError as error:
            raise RuntimeError(
                "FFprobe no devolvió un número de "
                "fotogramas válido."
            ) from error

        if frame_count <= 0:
            raise RuntimeError(
                "FFprobe devolvió un número de "
                "fotogramas no positivo."
            )

        return frame_count
