from pathlib import Path
import subprocess


class MediaProbe:

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