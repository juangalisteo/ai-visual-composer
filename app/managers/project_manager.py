import os
import re
from pathlib import Path


class ProjectManager:

    def __init__(self):
        project_name = os.environ.get(
            "MC_PROJECT_NAME",
            "default_project"
        )

        self.project_name = self._sanitize_name(
            project_name
        )

        self.base_path = (
            Path("output")
            / self.project_name
        )

    def setup(self):
        for folder in self.folders():
            folder.mkdir(
                parents=True,
                exist_ok=True
            )

    def folders(self):
        return [
            self.audio_dir(),
            self.images_dir(),
            self.scripts_dir(),
            self.storyboard_dir(),
            self.subtitles_dir(),
            self.video_dir()
        ]

    def audio_dir(self):
        return self.base_path / "audio"

    def images_dir(self):
        return self.base_path / "images"

    def scripts_dir(self):
        return self.base_path / "scripts"

    def storyboard_dir(self):
        return self.base_path / "storyboard"

    def subtitles_dir(self):
        return self.base_path / "subtitles"

    def video_dir(self):
        return self.base_path / "video"

    def script_path(self):
        return self.scripts_dir() / "guion.txt"

    def audio_path(self):
        return self.audio_dir() / "voz.mp3"

    def final_audio_path(self):
        return self.audio_dir() / "audio_final.mp3"

    def subtitle_path(self):
        return (
            self.subtitles_dir()
            / "subtitulos.srt"
        )

    def storyboard_path(self):
        return (
            self.storyboard_dir()
            / "storyboard.json"
        )

    def images_manifest_path(self):
        return (
            self.images_dir()
            / "images_manifest.json"
        )

    def video_path(self):
        return (
            self.video_dir()
            / f"{self.project_name}.mp4"
        )

    def _sanitize_name(self, name):
        name = name.strip()

        if not name:
            name = "default_project"

        name = re.sub(
            r'[<>:"/\\|?*]',
            "",
            name
        )

        name = re.sub(
            r"\s+",
            " ",
            name
        )

        return name
