import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main as app_main

from app.core import start
from app.modules.script import PreparedScript


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


class FakeVoiceBuilder:
    received_scripts = []

    def build(
        self,
        script
    ):
        self.received_scripts.append(
            script
        )
        return Path(
            "output/full test/audio/voz.mp3"
        )


class FakeScriptOperation:
    instances = []

    def __init__(
        self
    ):
        self.calls = []
        self.instances.append(
            self
        )

    def execute(
        self,
        **kwargs
    ):
        self.calls.append(
            kwargs
        )
        output_script_path = kwargs[
            "output_script_path"
        ]
        if kwargs["source_mode"] == "manual":
            text = (
                "Este es el guion manual entregado al componente Imagen."
            )
            source = "manual"
        else:
            text = (
                "Este es el guion generado por la fuente generada."
            )
            source = "generated"

        output_script_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )
        output_script_path.write_text(
            text,
            encoding="utf-8"
        )
        return PreparedScript(
            text=text,
            source=source,
            path=output_script_path,
            word_count=9
        )


def fake_ejecutar_guion(
    *,
    output_script_path,
    **_
):
    text = (
        "Este es el guion generado por el flujo productivo "
        "normal del sistema."
    )
    output_script_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )
    output_script_path.write_text(
        text,
        encoding="utf-8"
    )
    FakeScriptBuilder.prompts.append(
        "PROMPT PRODUCTIVO: conciencia / 10"
    )
    return PreparedScript(
        text=text,
        source="generated",
        path=output_script_path,
        word_count=10
    )


class ScriptOnlyModeTest(unittest.TestCase):

    def test_main_script_component_uses_manual_script_and_stops(self):
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
                    / "guion.txt"
                ).write_text(
                    "Guion manual del componente principal.",
                    encoding="utf-8"
                )
                (
                    input_dir
                    / "tema.txt"
                ).write_text(
                    "este tema no debe usarse",
                    encoding="utf-8"
                )

                with patch.dict(
                    os.environ,
                    {
                        "MC_VISUAL_PIPELINE": "script",
                        "MC_SCRIPT_SOURCE": "manual",
                        "MC_PIPELINE_MODE": "script",
                        "MC_PROJECT_NAME": "guion component",
                    },
                    clear=False
                ), patch(
                    "app.core.start.ConfigManager",
                    FakeConfigManager
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

                script_path = (
                    root
                    / "output"
                    / "guion component"
                    / "scripts"
                    / "guion.txt"
                )
                self.assertTrue(
                    os.path.samefile(
                        script_path,
                        root / result
                    )
                )
                self.assertEqual(
                    "Guion manual del componente principal.",
                    script_path.read_text(
                        encoding="utf-8"
                    )
                )
            finally:
                os.chdir(
                    previous_cwd
                )

    def test_main_script_component_does_not_generate_from_topic(self):
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

                with patch.dict(
                    os.environ,
                    {
                        "MC_VISUAL_PIPELINE": "script",
                        "MC_SCRIPT_SOURCE": "manual",
                        "MC_PIPELINE_MODE": "script",
                        "MC_PROJECT_NAME": "guion component",
                    },
                    clear=False
                ), patch(
                    "app.core.start.ConfigManager",
                    FakeConfigManager
                ):
                    with self.assertRaises(
                        FileNotFoundError
                    ):
                        start.iniciar()

                self.assertFalse(
                    (
                        root
                        / "output"
                        / "guion component"
                        / "scripts"
                        / "guion.txt"
                    ).exists()
                )
            finally:
                os.chdir(
                    previous_cwd
                )

    def test_main_script_to_image_persists_manual_script_after_output_reset(self):
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
                    / "guion.txt"
                ).write_text(
                    "Guion manual persistido tras reset.",
                    encoding="utf-8"
                )
                (
                    input_dir
                    / "tema.txt"
                ).write_text(
                    "tema que no debe usarse",
                    encoding="utf-8"
                )
                stale_path = (
                    root
                    / "output"
                    / "guion component"
                    / "stale.txt"
                )
                stale_path.parent.mkdir(
                    parents=True
                )
                stale_path.write_text(
                    "stale",
                    encoding="utf-8"
                )

                FakeVoiceBuilder.received_scripts = []

                with patch(
                    "main.RunController"
                ) as run_controller, patch(
                    "app.core.start.ConfigManager",
                    FakeConfigManager
                ), patch(
                    "app.modules.script.preparation.PromptEngine",
                    side_effect=AssertionError(
                        "PromptEngine must not run for manual source"
                    )
                ), patch(
                    "app.modules.script.preparation.ScriptBuilder",
                    side_effect=AssertionError(
                        "ScriptBuilder must not run for manual source"
                    )
                ), patch(
                    "app.core.start.VoiceBuilder",
                    FakeVoiceBuilder
                ), patch(
                    "app.core.start.MusicSelector",
                    side_effect=AssertionError(
                        "MusicSelector must not run without music"
                    )
                ), patch(
                    "app.core.start.AudioMixer"
                ) as audio_mixer, patch(
                    "app.core.start.SubtitleBuilder"
                ) as subtitle_builder, patch(
                    "app.core.start.SrtOptimizer"
                ) as srt_optimizer, patch(
                    "app.core.start.StoryboardBuilder"
                ) as storyboard_builder, patch(
                    "app.core.start.ImageBuilder"
                ) as image_builder, patch(
                    "app.core.start.VideoBuilder"
                ) as video_builder, patch(
                    "app.core.start.MediaProbe.get_duration",
                    return_value=None
                ), patch.dict(
                    os.environ,
                    {},
                    clear=False
                ):
                    run_controller.return_value.run.return_value = {
                        "visual_pipeline": "image",
                        "script_source": "manual",
                        "pipeline_mode": "full",
                        "profile_path": (
                            "config/profiles/guion/instagram.json"
                        ),
                        "subtitle_config": "single_line",
                        "voice_config": "masculina",
                        "music_category": None,
                        "overlays_mode": "smart",
                        "project_name": "guion component",
                        "clear_output": True
                    }
                    audio_mixer.return_value.build.return_value = Path(
                        "output/guion component/audio/audio_final.mp3"
                    )
                    subtitle_builder.return_value.build.return_value = Path(
                        "output/guion component/subtitles/subtitulos.srt"
                    )
                    srt_optimizer.return_value.optimize.return_value = Path(
                        "output/guion component/subtitles/subtitulos.srt"
                    )
                    storyboard_builder.return_value.build.return_value = Path(
                        "output/guion component/storyboard/storyboard.json"
                    )
                    image_builder.return_value.build.return_value = Path(
                        "output/guion component/images/images_manifest.json"
                    )
                    video_builder.return_value.build.return_value = Path(
                        "output/guion component/video/guion component.mp4"
                    )

                    app_main.main()

                script_path = (
                    root
                    / "output"
                    / "guion component"
                    / "scripts"
                    / "guion.txt"
                )
                self.assertFalse(
                    stale_path.exists()
                )
                self.assertEqual(
                    "Guion manual persistido tras reset.",
                    script_path.read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(
                    [
                        "Guion manual persistido tras reset."
                    ],
                    FakeVoiceBuilder.received_scripts
                )
                video_builder.return_value.build.assert_called_once()
                image_builder.return_value.build.assert_called_once()
                storyboard_builder.return_value.build.assert_called_once()
                subtitle_builder.return_value.build.assert_called_once()
                audio_mixer.return_value.build.assert_called_once()
            finally:
                os.chdir(
                    previous_cwd
                )

    def test_main_script_to_video_uses_manual_script_and_video_flow(self):
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
                    / "guion.txt"
                ).write_text(
                    "Guion manual para generar un video completo.",
                    encoding="utf-8"
                )
                (
                    input_dir
                    / "tema.txt"
                ).write_text(
                    "tema que no debe usarse",
                    encoding="utf-8"
                )

                FakeVoiceBuilder.received_scripts = []

                with patch(
                    "main.RunController"
                ) as run_controller, patch(
                    "app.core.start.ConfigManager",
                    FakeConfigManager
                ), patch(
                    "app.modules.script.preparation.PromptEngine",
                    side_effect=AssertionError(
                        "PromptEngine must not run for manual source"
                    )
                ), patch(
                    "app.modules.script.preparation.ScriptBuilder",
                    side_effect=AssertionError(
                        "ScriptBuilder must not run for manual source"
                    )
                ), patch(
                    "app.core.start.VoiceBuilder",
                    FakeVoiceBuilder
                ), patch(
                    "app.core.start.MusicSelector",
                    side_effect=AssertionError(
                        "MusicSelector must not run without music"
                    )
                ), patch(
                    "app.core.start.AudioMixer"
                ) as audio_mixer, patch(
                    "app.core.start.SubtitleBuilder"
                ) as subtitle_builder, patch(
                    "app.core.start.SrtOptimizer"
                ) as srt_optimizer, patch(
                    "app.core.start.StoryboardBuilder"
                ) as storyboard_builder, patch(
                    "app.core.start.ImageBuilder"
                ) as image_builder, patch(
                    "app.core.start.generar_video_clips_i2v"
                ) as video_clips_builder, patch(
                    "app.core.start.VideoBuilder"
                ) as video_builder, patch(
                    "app.core.start.MediaProbe.get_duration",
                    return_value=None
                ), patch.dict(
                    os.environ,
                    {},
                    clear=False
                ):
                    run_controller.return_value.run.return_value = {
                        "visual_pipeline": "video",
                        "script_source": "manual",
                        "pipeline_mode": "full",
                        "profile_path": (
                            "config/profiles/guion/instagram.json"
                        ),
                        "subtitle_config": "single_line",
                        "voice_config": "masculina",
                        "music_category": None,
                        "overlays_mode": "smart",
                        "project_name": "guion video",
                        "clear_output": False
                    }
                    audio_mixer.return_value.build.return_value = Path(
                        "output/guion video/audio/audio_final.mp3"
                    )
                    subtitle_builder.return_value.build.return_value = Path(
                        "output/guion video/subtitles/subtitulos.srt"
                    )
                    srt_optimizer.return_value.optimize.return_value = Path(
                        "output/guion video/subtitles/subtitulos.srt"
                    )
                    storyboard_builder.return_value.build.return_value = Path(
                        "output/guion video/storyboard/storyboard.json"
                    )
                    image_builder.return_value.build.return_value = Path(
                        "output/guion video/images/images_manifest.json"
                    )
                    video_clips_builder.return_value = Path(
                        "output/guion video/video_clips/"
                        "video_clips_manifest.json"
                    )
                    video_builder.return_value.build.return_value = Path(
                        "output/guion video/video/guion video.mp4"
                    )

                    app_main.main()

                script_path = (
                    root
                    / "output"
                    / "guion video"
                    / "scripts"
                    / "guion.txt"
                )
                self.assertEqual(
                    "Guion manual para generar un video completo.",
                    script_path.read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(
                    [
                        "Guion manual para generar un video completo."
                    ],
                    FakeVoiceBuilder.received_scripts
                )
                video_clips_builder.assert_called_once()
                video_builder.return_value.build.assert_called_once_with(
                    video_clips_manifest_path=Path(
                        "output/guion video/video_clips/"
                        "video_clips_manifest.json"
                    )
                )
                image_builder.return_value.build.assert_called_once()
                storyboard_builder.return_value.build.assert_called_once()
                subtitle_builder.return_value.build.assert_called_once()
                audio_mixer.return_value.build.assert_called_once()
            finally:
                os.chdir(
                    previous_cwd
                )

    def test_full_mode_reuses_script_operation_and_continues_with_prepared_text(self):
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
                FakeVoiceBuilder.received_scripts = []

                with patch.dict(
                    os.environ,
                    {
                        "MC_PIPELINE_MODE": "full",
                        "MC_PROJECT_NAME": "full test",
                        "MC_MUSIC_CATEGORY": "",
                    },
                    clear=False
                ), patch(
                    "app.core.start.ConfigManager",
                    FakeConfigManager
                ), patch(
                    "app.core.start.ejecutar_guion",
                    side_effect=fake_ejecutar_guion
                ) as script_operation, patch(
                    "app.core.start.VoiceBuilder",
                    FakeVoiceBuilder
                ), patch(
                    "app.core.start.MusicSelector",
                    side_effect=AssertionError(
                        "MusicSelector must not run without music"
                    )
                ), patch(
                    "app.core.start.AudioMixer"
                ) as audio_mixer, patch(
                    "app.core.start.SubtitleBuilder"
                ) as subtitle_builder, patch(
                    "app.core.start.SrtOptimizer"
                ) as srt_optimizer, patch(
                    "app.core.start.StoryboardBuilder"
                ) as storyboard_builder, patch(
                    "app.core.start.ImageBuilder"
                ) as image_builder, patch(
                    "app.core.start.VideoBuilder"
                ) as video_builder, patch(
                    "app.core.start.MediaProbe.get_duration",
                    return_value=None
                ):
                    audio_mixer.return_value.build.return_value = Path(
                        "output/full test/audio/audio_final.mp3"
                    )
                    subtitle_builder.return_value.build.return_value = Path(
                        "output/full test/subtitles/subtitulos.srt"
                    )
                    srt_optimizer.return_value.optimize.return_value = Path(
                        "output/full test/subtitles/subtitulos.srt"
                    )
                    storyboard_builder.return_value.build.return_value = Path(
                        "output/full test/storyboard/storyboard.json"
                    )
                    image_builder.return_value.build.return_value = Path(
                        "output/full test/images/images_manifest.json"
                    )
                    video_builder.return_value.build.return_value = Path(
                        "output/full test/video/full test.mp4"
                    )

                    result = start.iniciar()

                self.assertEqual(
                    1,
                    script_operation.call_count
                )
                self.assertEqual(
                    [
                        "Este es el guion generado por el flujo productivo "
                        "normal del sistema."
                    ],
                    FakeVoiceBuilder.received_scripts
                )
                self.assertEqual(
                    Path(
                        "output/full test/video/full test.mp4"
                    ),
                    result
                )
            finally:
                os.chdir(
                    previous_cwd
                )

    def test_image_full_mode_requests_generated_script_source(self):
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
                    / "guion.txt"
                ).write_text(
                    "Guion manual que Imagen no debe usar.",
                    encoding="utf-8"
                )
                (
                    input_dir
                    / "tema.txt"
                ).write_text(
                    "conciencia",
                    encoding="utf-8"
                )

                FakeVoiceBuilder.received_scripts = []
                FakeScriptOperation.instances = []

                with patch.dict(
                    os.environ,
                    {
                        "MC_VISUAL_PIPELINE": "image",
                        "MC_SCRIPT_SOURCE": "generated",
                        "MC_PIPELINE_MODE": "full",
                        "MC_PROJECT_NAME": "full generated source",
                        "MC_MUSIC_CATEGORY": "",
                    },
                    clear=False
                ), patch(
                    "app.core.start.ConfigManager",
                    FakeConfigManager
                ), patch(
                    "app.core.start.ScriptOperation",
                    FakeScriptOperation
                ), patch(
                    "app.core.start.VoiceBuilder",
                    FakeVoiceBuilder
                ), patch(
                    "app.core.start.MusicSelector",
                    side_effect=AssertionError(
                        "MusicSelector must not run without music"
                    )
                ), patch(
                    "app.core.start.AudioMixer"
                ) as audio_mixer, patch(
                    "app.core.start.SubtitleBuilder"
                ) as subtitle_builder, patch(
                    "app.core.start.SrtOptimizer"
                ) as srt_optimizer, patch(
                    "app.core.start.StoryboardBuilder"
                ) as storyboard_builder, patch(
                    "app.core.start.ImageBuilder"
                ) as image_builder, patch(
                    "app.core.start.VideoBuilder"
                ) as video_builder, patch(
                    "app.core.start.MediaProbe.get_duration",
                    return_value=None
                ):
                    audio_mixer.return_value.build.return_value = Path(
                        "output/full generated source/audio/audio_final.mp3"
                    )
                    subtitle_builder.return_value.build.return_value = Path(
                        "output/full generated source/subtitles/subtitulos.srt"
                    )
                    srt_optimizer.return_value.optimize.return_value = Path(
                        "output/full generated source/subtitles/subtitulos.srt"
                    )
                    storyboard_builder.return_value.build.return_value = Path(
                        "output/full generated source/storyboard/storyboard.json"
                    )
                    image_builder.return_value.build.return_value = Path(
                        "output/full generated source/images/images_manifest.json"
                    )
                    video_builder.return_value.build.return_value = Path(
                        "output/full generated source/video/full generated source.mp4"
                    )

                    start.iniciar()

                self.assertEqual(
                    1,
                    len(FakeScriptOperation.instances)
                )
                self.assertEqual(
                    "generated",
                    FakeScriptOperation.instances[0].calls[0]["source_mode"]
                )
                self.assertEqual(
                    [
                        "Este es el guion generado por la fuente generada."
                    ],
                    FakeVoiceBuilder.received_scripts
                )
            finally:
                os.chdir(
                    previous_cwd
                )


if __name__ == "__main__":
    unittest.main()
