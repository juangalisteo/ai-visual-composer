import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY, patch

import main as app_main

from app.core import start
from app.core.execution_request import (
    ApplicationExecutionRequest,
    StandardExecutionRequest,
)
from app.modules.script import PreparedScript
from app.modules.video.intro_outro import (
    IntroOutroPlan,
    IntroOutroSelection,
)
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
from app.shared.profile_resolver import OperationalProfileDescriptor
from app.shared.subtitle_profile_identity import SubtitleProfileKey


class FakeConfigManager:

    subtitle_profile = object()
    script_operational_key = OperationalProfileKey(
        ProfileComponent.GUION,
        "test_format",
        "test_profile",
    )
    video_operational_key = OperationalProfileKey(
        ProfileComponent.VIDEO,
        "test_format",
        "test_profile",
    )
    subtitle_profile_key = SubtitleProfileKey(
        component=ProfileComponent.GUION,
        format="test_format",
        family="test_family",
        profile_id="test_profile",
    )

    def __init__(
        self,
        operational_profile_key=None,
        voice_config_id=None,
    ):
        self._operational_profile_key = operational_profile_key
        self._voice_config_id = voice_config_id

    def get_operational_profile_key(self):
        return (
            self._operational_profile_key
            or self.script_operational_key
        )

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
            "video_style": {
                "fps": 30,
            },
        }

    def get_subtitle_profile_by_key(
        self,
        subtitle_profile_key,
    ):
        if subtitle_profile_key != self.subtitle_profile_key:
            raise AssertionError(
                "La prueba debe transportar la SubtitleProfileKey completa."
            )
        return self.subtitle_profile


class FakeProfileResolver:
    def discover_operational_profiles(self, component, profile_format):
        if (
            component is not ProfileComponent.VIDEO
            or profile_format != FakeConfigManager.video_operational_key.format
        ):
            raise AssertionError("La prueba debe conservar la identidad VIDEO.")
        return (
            OperationalProfileDescriptor(
                key=FakeConfigManager.video_operational_key,
                path=Path("test_video_profile.json"),
                display_name="Test profile",
            ),
        )


FakeConfigManager.profile_resolver = FakeProfileResolver()


def _standard_request(
    *,
    project_name,
    pipeline_mode,
    script_source,
    visual_pipeline="image",
    subtitle_profile_key=None,
):
    return ApplicationExecutionRequest(
        project_name=project_name,
        clear_output=False,
        operational_profile_key=FakeConfigManager.script_operational_key,
        subtitle_profile_key=subtitle_profile_key,
        route=StandardExecutionRequest(
            pipeline_mode=pipeline_mode,
            visual_pipeline=visual_pipeline,
            script_source=script_source,
            voice_config_id="test_voice",
        ),
    )


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

    def __init__(self, config_manager=None):
        self.config_manager = config_manager

    def build(
        self,
        script,
        output_path=None,
    ):
        self.received_scripts.append(
            script
        )
        return Path(output_path) if output_path is not None else Path(
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


def fake_script_execute(
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

                with patch(
                    "app.core.start.ConfigManager",
                    FakeConfigManager
                ):
                    with self.assertRaises(
                        FileNotFoundError
                    ):
                        start.iniciar(
                            request=_standard_request(
                                project_name="guion component",
                                pipeline_mode="audio",
                                visual_pipeline="image",
                                script_source="manual",
                            ),
                        )

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
                intro_outro_selection = IntroOutroPlan(
                    intro=IntroOutroSelection(
                        Path("assets/videos/intro.mp4"),
                        "intro",
                    )
                )

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
                    "app.modules.standard.execution_coordinator.VoiceBuilder",
                    FakeVoiceBuilder
                ), patch(
                    "app.modules.standard.execution_coordinator.MusicSelector",
                    side_effect=AssertionError(
                        "MusicSelector must not run without music"
                    )
                ), patch(
                    "app.modules.standard.execution_coordinator.AudioMixer"
                ) as audio_mixer, patch(
                    "app.modules.standard.execution_coordinator.SubtitleBuilder"
                ) as subtitle_builder, patch(
                    "app.modules.standard.execution_coordinator.SrtOptimizer"
                ) as srt_optimizer, patch(
                    "app.modules.standard.execution_coordinator.StoryboardBuilder"
                ) as storyboard_builder, patch(
                    "app.modules.standard.execution_coordinator.ImageBuilder"
                ) as image_builder, patch(
                    "app.modules.standard.execution_coordinator.VideoBuilder"
                ) as video_builder, patch(
                    "app.shared.media_probe.MediaProbe.get_duration",
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
                            "config/profiles/guion/vertical/estandar/"
                            "perfil_guion_vertical.json"
                        ),
                        "subtitle_profile_key": (
                            FakeConfigManager.subtitle_profile_key
                        ),
                        "voice_config": "masculina",
                        "music_category": None,
                        "overlays_mode": "smart",
                        "intro_outro_selection": intro_outro_selection,
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
                video_builder.assert_called_once()
                self.assertIs(
                    FakeConfigManager.subtitle_profile,
                    video_builder.call_args.kwargs["subtitle_profile"],
                )
                self.assertIsNotNone(
                    video_builder.call_args.kwargs["warnings"]
                )
                self.assertEqual(
                    intro_outro_selection,
                    video_builder.call_args.kwargs["intro_outro_selection"],
                )
                self.assertIsInstance(
                    video_builder.call_args.kwargs["config_manager"],
                    FakeConfigManager,
                )
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
                    "app.modules.standard.execution_coordinator.VoiceBuilder",
                    FakeVoiceBuilder
                ), patch(
                    "app.modules.standard.execution_coordinator.MusicSelector",
                    side_effect=AssertionError(
                        "MusicSelector must not run without music"
                    )
                ), patch(
                    "app.modules.standard.execution_coordinator.AudioMixer"
                ) as audio_mixer, patch(
                    "app.modules.standard.execution_coordinator.SubtitleBuilder"
                ) as subtitle_builder, patch(
                    "app.modules.standard.execution_coordinator.SrtOptimizer"
                ) as srt_optimizer, patch(
                    "app.modules.standard.execution_coordinator.StoryboardBuilder"
                ) as storyboard_builder, patch(
                    "app.modules.standard.execution_coordinator.ImageBuilder"
                ) as image_builder, patch(
                    "app.modules.standard.execution_coordinator.generate_video_clips"
                ) as video_clips_builder, patch(
                    "app.modules.standard.execution_coordinator.VideoBuilder"
                ) as video_builder, patch(
                    "app.shared.media_probe.MediaProbe.get_duration",
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
                        "profile_component": "guion",
                        "profile_format": (
                            FakeConfigManager.script_operational_key.format
                        ),
                        "profile_id": (
                            FakeConfigManager.script_operational_key.profile_id
                        ),
                        "subtitle_profile_key": (
                            FakeConfigManager.subtitle_profile_key
                        ),
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
                self.assertEqual(
                    FakeConfigManager.video_operational_key,
                    video_clips_builder.call_args.kwargs[
                        "profile_key"
                    ]
                )
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

    def test_full_without_subtitles_skips_srt_and_renders_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            previous_cwd = Path.cwd()

            try:
                os.chdir(root)
                input_dir = root / "input"
                input_dir.mkdir()
                (input_dir / "tema.txt").write_text(
                    "conciencia",
                    encoding="utf-8",
                )

                with patch(
                    "app.core.start.ConfigManager",
                    FakeConfigManager,
                ), patch.object(
                    FakeConfigManager,
                    "get_subtitle_profile_by_key",
                    side_effect=AssertionError(
                        "Subtitle profile must not be resolved"
                    ),
                ), patch(
                    "app.modules.standard.execution_coordinator.ScriptOperation.execute",
                    side_effect=fake_script_execute,
                ), patch(
                    "app.modules.standard.execution_coordinator.VoiceBuilder",
                    FakeVoiceBuilder,
                ), patch(
                    "app.modules.standard.execution_coordinator.MusicSelector",
                    side_effect=AssertionError(
                        "MusicSelector must not run without music"
                    ),
                ), patch(
                    "app.modules.standard.execution_coordinator.AudioMixer"
                ) as audio_mixer, patch(
                    "app.modules.standard.execution_coordinator.SubtitleBuilder"
                ) as subtitle_builder, patch(
                    "app.modules.standard.execution_coordinator.SrtOptimizer"
                ) as srt_optimizer, patch(
                    "app.modules.standard.execution_coordinator.StoryboardBuilder"
                ) as storyboard_builder, patch(
                    "app.modules.standard.execution_coordinator.ImageBuilder"
                ) as image_builder, patch(
                    "app.modules.standard.execution_coordinator.VideoBuilder"
                ) as video_builder, patch(
                    "app.shared.media_probe.MediaProbe.get_duration",
                    return_value=None,
                ):
                    final_video = Path(
                        "output/full without subtitles/video/"
                        "full without subtitles.mp4"
                    )
                    audio_mixer.return_value.build.return_value = Path(
                        "output/full without subtitles/audio/audio_final.mp3"
                    )
                    storyboard_builder.return_value.build.return_value = Path(
                        "output/full without subtitles/storyboard/storyboard.json"
                    )
                    image_builder.return_value.build.return_value = Path(
                        "output/full without subtitles/images/images_manifest.json"
                    )
                    video_builder.return_value.build.return_value = final_video

                    result = start.iniciar(
                        request=_standard_request(
                            project_name="full without subtitles",
                            pipeline_mode="full_without_subtitles",
                            script_source="generated",
                        ),
                    )

                self.assertEqual(final_video, result)
                subtitle_builder.assert_not_called()
                srt_optimizer.assert_not_called()
                video_builder.assert_called_once_with(
                    subtitle_profile=None,
                    warnings=ANY,
                    overlays_mode=None,
                    render_subtitles=False,
                    config_manager=ANY,
                    project=ANY,
                )
                video_builder.return_value.build.assert_called_once_with()
                self.assertFalse(
                    (root / "output/full without subtitles/subtitles/subtitulos.srt")
                    .exists()
                )
                self.assertNotIn("_sin_subtitulos", str(result))
            finally:
                os.chdir(previous_cwd)

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

                with patch(
                    "app.core.start.ConfigManager",
                    FakeConfigManager
                ), patch(
                    "app.modules.standard.execution_coordinator.ScriptOperation.execute",
                    side_effect=fake_script_execute
                ) as script_operation, patch(
                    "app.modules.standard.execution_coordinator.VoiceBuilder",
                    FakeVoiceBuilder
                ), patch(
                    "app.modules.standard.execution_coordinator.MusicSelector",
                    side_effect=AssertionError(
                        "MusicSelector must not run without music"
                    )
                ), patch(
                    "app.modules.standard.execution_coordinator.AudioMixer"
                ) as audio_mixer, patch(
                    "app.modules.standard.execution_coordinator.SubtitleBuilder"
                ) as subtitle_builder, patch(
                    "app.modules.standard.execution_coordinator.SrtOptimizer"
                ) as srt_optimizer, patch(
                    "app.modules.standard.execution_coordinator.StoryboardBuilder"
                ) as storyboard_builder, patch(
                    "app.modules.standard.execution_coordinator.ImageBuilder"
                ) as image_builder, patch(
                    "app.modules.standard.execution_coordinator.VideoBuilder"
                ) as video_builder, patch(
                    "app.shared.media_probe.MediaProbe.get_duration",
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

                    result = start.iniciar(
                        request=_standard_request(
                            project_name="full test",
                            pipeline_mode="full",
                            script_source="generated",
                            subtitle_profile_key=FakeConfigManager.subtitle_profile_key,
                        ),
                    )

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

                with patch(
                    "app.core.start.ConfigManager",
                    FakeConfigManager
                ), patch(
                    "app.modules.standard.execution_coordinator.ScriptOperation",
                    FakeScriptOperation
                ), patch(
                    "app.modules.standard.execution_coordinator.VoiceBuilder",
                    FakeVoiceBuilder
                ), patch(
                    "app.modules.standard.execution_coordinator.MusicSelector",
                    side_effect=AssertionError(
                        "MusicSelector must not run without music"
                    )
                ), patch(
                    "app.modules.standard.execution_coordinator.AudioMixer"
                ) as audio_mixer, patch(
                    "app.modules.standard.execution_coordinator.SubtitleBuilder"
                ) as subtitle_builder, patch(
                    "app.modules.standard.execution_coordinator.SrtOptimizer"
                ) as srt_optimizer, patch(
                    "app.modules.standard.execution_coordinator.StoryboardBuilder"
                ) as storyboard_builder, patch(
                    "app.modules.standard.execution_coordinator.ImageBuilder"
                ) as image_builder, patch(
                    "app.modules.standard.execution_coordinator.VideoBuilder"
                ) as video_builder, patch(
                    "app.shared.media_probe.MediaProbe.get_duration",
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

                    start.iniciar(
                        request=_standard_request(
                            project_name="full generated source",
                            pipeline_mode="full",
                            script_source="generated",
                            subtitle_profile_key=FakeConfigManager.subtitle_profile_key,
                        ),
                    )

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
