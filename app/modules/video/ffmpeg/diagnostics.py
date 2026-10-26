import json
from pathlib import Path

from app.shared.config_manager import ConfigManager


class FFmpegDiagnostics:

    def __init__(
        self,
        output_path,
        scene_count,
        config_manager=None,
    ):
        output_path = Path(output_path)
        self.path = output_path.parent / "ffmpeg_diagnostics.json"
        self._config_manager = config_manager
        self.data = {
            "profile": self._profile_metadata(),
            "scene_count": scene_count,
            "normalization": {
                "status": "NOT_REQUIRED",
                "duration_seconds": 0.0,
                "clips": [],
            },
            "final_assembly": {
                "status": "PENDING",
                "duration_seconds": None,
                "command": [],
                "stderr": "",
            },
            "result": "PENDING",
            "peak_rss_bytes": None,
            "peak_rss_note": (
                "No se mide RSS para evitar dependencias "
                "adicionales o una medicion fragil."
            ),
        }
        self._persist()

    def _profile_metadata(self):
        config = self._config_manager or ConfigManager()
        profile_key = config.get_operational_profile_key()
        if profile_key is None:
            return None

        return {
            "component": profile_key.component.value,
            "format": profile_key.format,
            "profile_id": profile_key.profile_id,
            "path": str(
                config.profile_resolver.resolve_operational(
                    profile_key
                )
            ),
        }

    def start_normalization(self):
        self.data["normalization"]["status"] = "RUNNING"
        self._persist()

    def record_normalized_clip(
        self,
        scene_number,
        command,
        elapsed,
        stderr="",
        status="SUCCESS",
    ):
        self.data["normalization"]["clips"].append(
            {
                "scene": scene_number,
                "command": list(command),
                "duration_seconds": elapsed,
                "stderr": stderr,
                "status": status,
            }
        )
        self._persist()

    def finish_normalization(
        self,
        elapsed,
        status="SUCCESS",
    ):
        normalization = self.data["normalization"]
        normalization["status"] = status
        normalization["duration_seconds"] = elapsed
        self._persist()

    def record_final_assembly(
        self,
        command,
        elapsed,
        stderr="",
        status="SUCCESS",
    ):
        self.data["final_assembly"] = {
            "status": status,
            "duration_seconds": elapsed,
            "command": list(command),
            "stderr": stderr,
        }
        self._persist()

    def finish(
        self,
        status,
        error="",
    ):
        self.data["result"] = status
        if error:
            self.data["error"] = error
        self._persist()

    def _persist(self):
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.path.write_text(
            json.dumps(
                self.data,
                ensure_ascii=False,
                indent=4,
            ),
            encoding="utf-8",
        )
