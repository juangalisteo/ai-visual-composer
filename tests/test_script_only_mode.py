import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core import start


class FakeConfigManager:

    def get_ai_config(
        self
    ):
        return {
            "model": "test-model"
        }

    def get_profile_config(
        self
    ):
        return {
            "tone": "modo_conciencia",
            "platform": "youtube",
            "format": "horizontal",
            "duration": 10,
            "builders": {
                "script": True,
                "voice": True,
                "subtitles": True,
                "storyboard": True,
                "images": True,
                "video": True,
            },
        }


class FakePromptEngine:

    def build_script_prompt(
        self,
        topic,
        profile
    ):
        return (
            "PROMPT PRODUCTIVO: "
            f"{topic} / {profile['duration']}"
        )


class FakeScriptBuilder:
    prompts = []

    def __init__(
        self,
        ai_config
    ):
        self.ai_config = ai_config

    def build(
        self,
        prompt
    ):
        self.prompts.append(
            prompt
        )
        return (
            "Este es el guion generado por el flujo productivo "
            "normal del sistema."
        )


class ScriptOnlyModeTest(unittest.TestCase):

    def test_script_mode_creates_standard_project_writes_script_and_stops(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            previous_cwd = Path.cwd()

            try:
                os.chdir(
                    root
                )
                input_dir = root / "input"
                input_dir.mkdir()
                (
                    input_dir
                    / "tema.txt"
                ).write_text(
                    "conciencia",
                    encoding="utf-8"
                )

                FakeScriptBuilder.prompts = []
                original_defaults = (
                    start
                    .cargar_o_generar_guion
                    .__defaults__
                )

                try:
                    (
                        start
                        .cargar_o_generar_guion
                        .__defaults__
                    ) = (
                        FakeScriptBuilder,
                    )

                    with patch.dict(
                        os.environ,
                        {
                            "MC_PIPELINE_MODE": "script",
                            "MC_PROJECT_NAME": "solo guion test",
                        },
                        clear=False
                    ), patch(
                        "app.core.start.ConfigManager",
                        FakeConfigManager
                    ), patch(
                        "app.core.start.PromptEngine",
                        FakePromptEngine
                    ), patch(
                        "app.core.start.VoiceBuilder",
                        side_effect=AssertionError(
                            "VoiceBuilder must not run"
                        )
                    ), patch(
                        "app.core.start.AudioMixer",
                        side_effect=AssertionError(
                            "AudioMixer must not run"
                        )
                    ), patch(
                        "app.core.start.SubtitleBuilder",
                        side_effect=AssertionError(
                            "SubtitleBuilder must not run"
                        )
                    ), patch(
                        "app.core.start.SrtOptimizer",
                        side_effect=AssertionError(
                            "SrtOptimizer must not run"
                        )
                    ), patch(
                        "app.core.start.StoryboardBuilder",
                        side_effect=AssertionError(
                            "StoryboardBuilder must not run"
                        )
                    ), patch(
                        "app.core.start.ImageBuilder",
                        side_effect=AssertionError(
                            "ImageBuilder must not run"
                        )
                    ), patch(
                        "app.core.start.VideoBuilder",
                        side_effect=AssertionError(
                            "VideoBuilder must not run"
                        )
                    ):
                        result = start.iniciar()
                finally:
                    (
                        start
                        .cargar_o_generar_guion
                        .__defaults__
                    ) = original_defaults

                project_root = (
                    root
                    / "output"
                    / "solo guion test"
                )

                for folder_name in (
                    "audio",
                    "images",
                    "scripts",
                    "storyboard",
                    "subtitles",
                    "video",
                ):
                    self.assertTrue(
                        (
                            project_root
                            / folder_name
                        ).is_dir(),
                        folder_name,
                    )

                script_path = (
                    project_root
                    / "scripts"
                    / "guion.txt"
                )
                self.assertTrue(
                    os.path.samefile(
                        script_path,
                        root / result
                    ),
                    (
                        script_path,
                        result,
                    )
                )
                self.assertEqual(
                    "Este es el guion generado por el flujo productivo "
                    "normal del sistema.",
                    script_path.read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(
                    [
                        "PROMPT PRODUCTIVO: conciencia / 10"
                    ],
                    FakeScriptBuilder.prompts,
                )
                self.assertEqual(
                    [],
                    list(
                        (
                            project_root
                            / "audio"
                        ).iterdir()
                    ),
                )
                self.assertEqual(
                    [],
                    list(
                        (
                            project_root
                            / "storyboard"
                        ).iterdir()
                    ),
                )
                self.assertEqual(
                    [],
                    list(
                        (
                            project_root
                            / "images"
                        ).iterdir()
                    ),
                )
                self.assertEqual(
                    [],
                    list(
                        (
                            project_root
                            / "subtitles"
                        ).iterdir()
                    ),
                )
                self.assertEqual(
                    [],
                    list(
                        (
                            project_root
                            / "video"
                        ).iterdir()
                    ),
                )
            finally:
                os.chdir(
                    previous_cwd
                )


if __name__ == "__main__":
    unittest.main()
