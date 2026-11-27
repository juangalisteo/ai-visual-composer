import ast
import json
import os
import inspect
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

from app.core import start
from app.core.script_length import SpeechPacing
from app.core.execution_request import (
    ApplicationExecutionRequest,
    StandardExecutionRequest,
)
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.managers.pipeline_summary import PipelineSummary
from app.modules.standard import StandardExecutionCoordinator
from app.modules.video_component import (
    BackendVideoPrompt,
    MinimalVisualContext,
    MotionIntent,
    VideoPreparationResult,
    VideoPromptPlan,
    VideoClipGenerationResult,
    WanIntermediateOutput,
)
from app.modules.video_component import clip_batch
from app.modules.video_component.direct_i2v import run_direct_i2v
from app.modules.video_component.profile_parameters import (
    build_video_backend_overrides,
)
from app.modules.video.intro_outro import (
    IntroOutroPlan,
    IntroOutroSelection,
)


def _video_request(
    *,
    pipeline_mode,
    operational_profile_key,
    subtitle_profile_key=None,
    intro_outro_plan=None,
):
    return ApplicationExecutionRequest(
        project_name="video runtime",
        overwrite_project=False,
        operational_profile_key=operational_profile_key,
        subtitle_profile_key=subtitle_profile_key,
        route=StandardExecutionRequest(
            pipeline_mode=pipeline_mode,
            visual_pipeline="video",
            script_source="generated",
            voice_config_id="test_voice",
            intro_outro_plan=intro_outro_plan,
        ),
    )



def _test_voice_configuration():
    """Selected voice of a topic-script route: only its pacing is read."""
    return SimpleNamespace(
        display_name="Voz de prueba",
        pacing=SpeechPacing(letters_per_second=13.0, words_per_second=2.5),
        voice=SimpleNamespace(voice_id="test_voice"),
    )

class FakeProject:
    def __init__(
        self,
        base_path
    ):
        self.project_name = "video runtime"
        self.base_path = Path(
            base_path
        )
        self.setup_called = False

    def setup(
        self
    ):
        self.setup_called = True
        self.base_path.mkdir(
            parents=True,
            exist_ok=True
        )

    def script_path(
        self
    ):
        return self.base_path / "scripts" / "guion.txt"

    def audio_path(
        self
    ):
        return self.base_path / "audio" / "voz.mp3"

    def final_audio_path(
        self
    ):
        return self.base_path / "audio" / "audio_final.mp3"

    def subtitle_path(
        self
    ):
        return self.base_path / "subtitles" / "subtitulos.srt"

    def storyboard_path(
        self
    ):
        return self.base_path / "storyboard" / "storyboard.json"

    def images_manifest_path(
        self
    ):
        return self.base_path / "images" / "images_manifest.json"

    def video_path(
        self
    ):
        return self.base_path / "video" / "video-runtime.mp4"


def FakeResult(
    output_clip,
    source_image=None,
    profile_name="Vertical",
    seed=123,
):
    return VideoClipGenerationResult(
        source_image=Path(source_image or output_clip),
        output_clip=Path(output_clip),
        manifest_path=None,
        prompt_id="prompt-id",
        backend="ComfyUI",
        model="wan2.2_ti2v_5B_fp16.safetensors",
        workflow="config/comfyui_wan22_ti2v_i2v_workflow_api.json",
        seed=seed,
        frames=49,
        fps=12.0,
        generation_width=384,
        generation_height=672,
        steps=12,
        cfg=5.0,
        sampler="uni_pc",
        scheduler="simple",
        profile_name=profile_name,
        duration_seconds=4.083333333333333,
        fingerprint="fake-fingerprint",
        positive_prompt="exact positive prompt",
        negative_prompt="exact negative prompt",
        motion_summary="subtle motion, high stability",
        camera_motion="slow stable drift",
        motion_intensity="subtle",
        stability="high",
        temporal_rhythm="slow and steady",
        motion_level="subtle",
        preservation_constraints=("preserve source composition",),
        avoidance_constraints=("avoid abrupt motion",),
        source_trace=("VisualTruth.visible_subject",),
    )


class FakeVideoComponentBuilder:
    def __init__(
        self,
        output_clip
    ):
        self.output_clip = Path(
            output_clip
        )
        self.calls = []

    def generate_clip(
        self,
        source_path=None,
        output_dir=None,
        output_name="clip_001.mp4",
        storyboard_scene=None,
        **overrides
    ):
        output_clip = (
            Path(
                output_dir
            )
            / output_name
        )
        self.calls.append({
            "source_path": Path(
                source_path
            ),
            "output_dir": Path(
                output_dir
            ),
            "output_name": output_name,
            "storyboard_scene": storyboard_scene,
            "overrides": overrides,
        })
        output_clip.parent.mkdir(
            parents=True,
            exist_ok=True
        )
        output_clip.write_bytes(
            b"video"
        )
        return FakeResult(
            output_clip,
            source_image=source_path,
            profile_name=overrides.get(
                "profile_name",
                "Vertical"
            ),
            seed=overrides.get(
                "seed",
                123
            )
        )


class VideoComponentRuntimeIntegrationTest(unittest.TestCase):

    def test_video_i2v_legacy_adapter_keeps_public_signature(self):
        self.assertEqual(
            (
                "pipeline_start",
                "project",
                "profile_key",
                "source_path",
                "video_builder",
            ),
            tuple(inspect.signature(run_direct_i2v).parameters),
        )
        self.assertIs(
            inspect.Parameter.empty,
            inspect.signature(run_direct_i2v).parameters["source_path"].default,
        )

    def test_video_i2v_runtime_dispatches_to_video_component(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            project = FakeProject(
                root / "output" / "video-runtime"
            )
            output_clip = (
                project.base_path
                / "video_clips"
                / "clip_001.mp4"
            )
            builder = FakeVideoComponentBuilder(
                output_clip
            )

            with patch(
                "app.modules.video_component.profile_parameters._random_video_seed",
                return_value=847291635
            ):
                result = run_direct_i2v(
                    pipeline_start=0,
                    project=project,
                    profile_key=OperationalProfileKey(
                        ProfileComponent.VIDEO,
                        "vertical",
                        "video_vertical",
                    ),
                    source_path=root / "source.png",
                    video_builder=builder,
                )

        self.assertEqual(
            output_clip,
            result
        )
        self.assertTrue(
            project.setup_called
        )
        self.assertEqual(
            1,
            len(
                builder.calls
            )
        )
        call = builder.calls[0]
        self.assertEqual(
            Path(
                temp_dir
            ) / "source.png",
            call["source_path"]
        )
        self.assertEqual(
            project.base_path
            / "video_clips",
            call["output_dir"]
        )
        self.assertEqual(
            448,
            call["overrides"]["generation_width"]
        )
        self.assertEqual(
            800,
            call["overrides"]["generation_height"]
        )
        self.assertEqual(
            81,
            call["overrides"]["frames"]
        )
        self.assertEqual(
            12.0,
            call["overrides"]["fps"]
        )
        self.assertEqual(
            20,
            call["overrides"]["steps"]
        )
        self.assertEqual(
            5.0,
            call["overrides"]["cfg"]
        )
        self.assertEqual(
            "uni_pc",
            call["overrides"]["sampler"]
        )
        self.assertEqual(
            "simple",
            call["overrides"]["scheduler"]
        )
        self.assertEqual(
            "lossless_ffv1",
            call["overrides"]["intermediate_output"]
        )
        self.assertEqual(
            847291635,
            call["overrides"]["seed"]
        )

    def test_video_i2v_legacy_adapter_delegates_to_direct_service(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = FakeProject(root / "output" / "video-runtime")
            builder = FakeVideoComponentBuilder(root / "unused.mp4")
            output_clip = project.base_path / "video_clips" / "clip_001.mkv"
            service = MagicMock()
            service.generate.return_value = SimpleNamespace(
                generation=SimpleNamespace(
                    output_clip=output_clip,
                    duration_seconds=4.0,
                )
            )
            profile_key = OperationalProfileKey(
                ProfileComponent.VIDEO,
                "vertical",
                "video_vertical",
            )
            source_path = root / "source.png"

            with patch(
                "app.modules.video_component.direct_i2v.DirectI2VGenerationService",
                return_value=service,
            ) as service_type:
                result = run_direct_i2v(
                    pipeline_start=0,
                    project=project,
                    profile_key=profile_key,
                    source_path=source_path,
                    video_builder=builder,
                )

        self.assertEqual(output_clip, result)
        self.assertTrue(project.setup_called)
        service_type.assert_called_once_with(video_builder=builder)
        service.generate.assert_called_once()
        request = service.generate.call_args.args[0]
        self.assertEqual(source_path, request.source_image)
        self.assertIs(profile_key, request.profile_key)
        self.assertEqual(project.base_path / "video_clips", request.output_dir)
        self.assertEqual("clip_001", request.output_stem)

    def test_video_i2v_legacy_adapter_propagates_service_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = MagicMock()
            service.generate.side_effect = RuntimeError("direct service failure")

            with patch(
                "app.modules.video_component.direct_i2v.DirectI2VGenerationService",
                return_value=service,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "direct service failure",
                ):
                    run_direct_i2v(
                        project=FakeProject(root / "output"),
                        profile_key=OperationalProfileKey(
                            ProfileComponent.VIDEO,
                            "vertical",
                            "video_vertical",
                        ),
                        source_path=root / "source.png",
                        video_builder=FakeVideoComponentBuilder(
                            root / "unused.mp4"
                        ),
                    )

    def test_run_application_has_no_video_i2v_special_dispatch(self):
        run_application_tree = ast.parse(
            inspect.getsource(start.run_application)
            + textwrap.dedent(inspect.getsource(StandardExecutionCoordinator.run))
        )
        mode_literals = {
            node.value
            for node in ast.walk(run_application_tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
        }
        called_names = {
            node.func.id
            for node in ast.walk(run_application_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
        }

        self.assertNotIn("video_i2v", mode_literals)
        self.assertNotIn("run_direct_i2v", called_names)

    def test_video_i2v_missing_source_path_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = (
                Path(
                    temp_dir
                )
                / "missing.png"
            )

            with self.assertRaises(
                FileNotFoundError
            ):
                run_direct_i2v(
                    project=FakeProject(
                        Path(
                            temp_dir
                        )
                        / "output"
                    ),
                    profile_key=OperationalProfileKey(
                        ProfileComponent.VIDEO,
                        "vertical",
                        "video_vertical",
                    ),
                    source_path=missing,
                )

    def test_video_profiles_exist_with_validated_parameters(self):
        cases = (
            (
                "config/profiles/video/vertical/wan_i2v_vertical.json",
                448,
                800,
                20,
            ),
            (
                "config/profiles/video/horizontal/wan_i2v_horizontal.json",
                800,
                448,
                20,
            ),
        )

        for (
            profile_path,
            generation_width,
            generation_height,
            steps,
        ) in cases:
            with self.subTest(
                profile_path=profile_path
            ):
                profile = json.loads(
                    Path(
                        profile_path
                    ).read_text(
                        encoding="utf-8"
                    )
                )
                video_component = profile[
                    "video_component"
                ]
                self.assertEqual(
                    generation_width,
                    video_component[
                        "generation"
                    ][
                        "width"
                    ]
                )
                self.assertEqual(
                    generation_height,
                    video_component[
                        "generation"
                    ][
                        "height"
                    ]
                )
                self.assertEqual(
                    81,
                    video_component[
                        "frames"
                    ]
                )
                self.assertEqual(
                    12,
                    video_component[
                        "fps"
                    ]
                )
                self.assertEqual(
                    steps,
                    video_component[
                        "sampling"
                    ][
                        "steps"
                    ]
                )
                self.assertEqual(
                    "random",
                    video_component[
                        "seed_mode"
                    ]
                )
                self.assertNotIn(
                    "seed",
                    video_component
                )

    def test_active_video_profiles_keep_quality_encoding_settings(self):
        profile_paths = (
            "config/profiles/guion/vertical/perfil_guion_vertical.json",
            "config/profiles/guion/horizontal/perfil_guion_horizontal.json",
            "config/profiles/imagen/vertical/perfil_imagen_vertical.json",
            "config/profiles/imagen/horizontal/perfil_imagen_horizontal.json",
            "config/profiles/video/vertical/perfil_video_vertical.json",
            "config/profiles/video/horizontal/perfil_video_horizontal.json",
        )

        for profile_path in profile_paths:
            with self.subTest(profile_path=profile_path):
                profile = json.loads(
                    Path(profile_path).read_text(encoding="utf-8")
                )

                self.assertEqual("slow", profile["video"]["preset"])
                self.assertEqual(16, profile["video"]["crf"])

    def test_random_seed_mode_resolves_single_valid_seed(self):
        profile = _video_profile(
            "Vertical"
        )

        with patch(
            "app.modules.video_component.profile_parameters._random_video_seed",
            return_value=111
        ):
            first = build_video_backend_overrides(
                profile
            )

        with patch(
            "app.modules.video_component.profile_parameters._random_video_seed",
            return_value=222
        ):
            second = build_video_backend_overrides(
                profile
            )

        self.assertEqual(
            111,
            first["seed"]
        )
        self.assertEqual(
            222,
            second["seed"]
        )
        self.assertGreaterEqual(
            first["seed"],
            0
        )
        self.assertGreaterEqual(
            second["seed"],
            0
        )

    def test_fixed_seed_mode_keeps_explicit_seed_for_reproducibility(
        self
    ):
        profile = _video_profile(
            "Vertical",
            seed_mode="fixed",
            seed=123456789
        )

        with patch(
            "app.modules.video_component.profile_parameters._random_video_seed"
        ) as random_mock:
            overrides = build_video_backend_overrides(
                profile
            )

        random_mock.assert_not_called()
        self.assertEqual(
            123456789,
            overrides["seed"]
        )

    def test_i2v_overrides_transport_intermediate_output_to_backend_prompt(
        self,
    ):
        preparation = VideoPreparationResult(
            visual_context=MinimalVisualContext(
                source_path=Path("source.png"),
                width=320,
                height=320,
                aspect_ratio="1:1",
                orientation="square",
                image_format="PNG",
            ),
            motion_intent=MotionIntent(
                source="test",
                camera_motion="still",
                motion_intensity="subtle",
                stability="high",
                temporal_rhythm="steady",
            ),
            prompt_plan=VideoPromptPlan(
                prompt="Prompt",
                negative_prompt="",
                motion_summary="still",
            ),
        )

        for intermediate_output, expected in (
            ("lossless_ffv1", WanIntermediateOutput.LOSSLESS_FFV1),
            ("savevideo_h264", WanIntermediateOutput.SAVEVIDEO_H264),
        ):
            with self.subTest(intermediate_output=intermediate_output):
                profile = _video_profile("Vertical")
                profile["video_component"]["delivery"] = {
                    "intermediate_output": intermediate_output,
                }

                with patch(
                    "app.modules.video_component.profile_parameters._random_video_seed",
                    return_value=123,
                ):
                    overrides = build_video_backend_overrides(profile)

                prompt = BackendVideoPrompt.from_preparation(
                    preparation,
                    **overrides,
                )

                self.assertEqual(expected, prompt.intermediate_output)
                self.assertEqual(384, prompt.generation_width)
                self.assertEqual(672, prompt.generation_height)
                self.assertEqual(49, prompt.frames)
                self.assertEqual(12.0, prompt.fps)
                self.assertEqual(12, prompt.steps)
                self.assertEqual(5.0, prompt.cfg)
                self.assertEqual("uni_pc", prompt.sampler)
                self.assertEqual("simple", prompt.scheduler)

    def test_i2v_overrides_preserve_legacy_intermediate_output_default(self):
        profile = _video_profile("Vertical")

        with patch(
            "app.modules.video_component.profile_parameters._random_video_seed",
            return_value=123,
        ):
            overrides = build_video_backend_overrides(profile)

        self.assertEqual("savevideo_h264", overrides["intermediate_output"])

    def test_run_application_video_product_composes_final_video_from_i2v_clips(
        self
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            project = FakeProject(
                root
                / "output"
                / "video-product"
            )
            video_clips_manifest = (
                project.base_path
                / "video_clips"
                / "video_clips_manifest.json"
            )
            final_video = (
                project.base_path
                / "video"
                / "video-runtime.mp4"
            )
            resolved_subtitle_profile = object()
            intro_outro_selection = IntroOutroPlan(
                intro=IntroOutroSelection(Path("intro.mp4"), "intro")
            )
            requested_subtitle_keys = []
            subtitle_key = SubtitleProfileKey(
                ProfileComponent.VIDEO,
                "vertical",
                "test_subtitle_profile",
                "test_family",
            )

            class FakeConfig:
                def get_ai_config(
                    self
                ):
                    return {
                        "script": {
                            "duration_margin": {"below": 0.10, "above": None},
                        },
                    }

                def get_tts_voice_configuration(self):
                    return _test_voice_configuration()

                def get_operational_profile_key(self):
                    return OperationalProfileKey(
                        ProfileComponent.VIDEO,
                        "vertical",
                        "video_vertical",
                    )

                def get_profile_config(
                    self
                ):
                    return {
                        "format": "vertical",
                        "duration": 4,
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

                def get_subtitle_profile_by_key(self, selected_key):
                    requested_subtitle_keys.append(selected_key)
                    return resolved_subtitle_profile

            with patch(
                "app.core.start.ProjectManager",
                return_value=project
            ), patch(
                "app.core.start.ConfigManager",
                return_value=FakeConfig()
            ), patch(
                "app.modules.standard.execution_coordinator.ScriptOperation.execute",
                return_value=type(
                    "PreparedScript",
                    (),
                    {
                        "text": "Guion de prueba."
                    }
                )()
            ), patch(
                "app.modules.standard.execution_coordinator.VoiceBuilder"
            ) as voice_builder, patch(
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
                "app.modules.standard.execution_coordinator.generate_video_clips",
                return_value=video_clips_manifest
            ) as clips_builder, patch(
                "app.modules.standard.execution_coordinator.VideoBuilder"
            ) as video_builder, patch(
                "app.shared.media_probe.MediaProbe.get_duration",
                return_value=4.0
            ):
                voice_builder.return_value.build.return_value = (
                    project.audio_path()
                )
                audio_mixer.return_value.build.return_value = (
                    project.final_audio_path()
                )
                subtitle_builder.return_value.build.return_value = (
                    project.subtitle_path()
                )
                srt_optimizer.return_value.optimize.return_value = (
                    project.subtitle_path()
                )
                storyboard_builder.return_value.build.return_value = (
                    project.storyboard_path()
                )
                image_builder.return_value.build.return_value = (
                    project.images_manifest_path()
                )
                video_builder.return_value.build.return_value = (
                    final_video
                )

                with patch(
                    "app.modules.standard.execution_coordinator.PipelineSummary",
                    wraps=PipelineSummary,
                ) as summary_class:
                    result = start.run_application(
                        request=_video_request(
                            pipeline_mode="full",
                            operational_profile_key=OperationalProfileKey(
                                ProfileComponent.VIDEO,
                                "vertical",
                                "video_vertical",
                            ),
                            subtitle_profile_key=subtitle_key,
                            intro_outro_plan=intro_outro_selection,
                        ),
                    )

        self.assertEqual(
            final_video,
            result
        )
        # A video made of clips has scenes, not still images (A2-C).
        self.assertIs(False, summary_class.call_args.kwargs["still_images"])
        self.assertEqual(
            [subtitle_key],
            requested_subtitle_keys,
        )
        clips_builder.assert_called_once()
        srt_optimizer.assert_called_once_with(
            subtitle_profile=resolved_subtitle_profile,
            render_fps=30,
            project=project,
        )
        srt_optimizer.return_value.optimize.assert_called_once_with(
            canonical_content="Guion de prueba.",
        )
        video_builder.assert_called_once_with(
            subtitle_profile=resolved_subtitle_profile,
            overlays_mode=None,
            intro_outro_selection=intro_outro_selection,
            config_manager=ANY,
            project=project,
        )
        video_builder.return_value.build.assert_called_once_with(
            video_clips_manifest_path=video_clips_manifest
        )

    def test_run_application_video_product_without_subtitles_uses_standard_operational_identity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = FakeProject(Path(temp_dir) / "output" / "video-product")
            final_video = project.video_path()
            clips_manifest = (
                project.base_path
                / "video_clips"
                / "video_clips_manifest.json"
            )
            class FakeConfig:
                profile_resolver = ProfileResolver()

                def get_ai_config(self):
                    return {
                        "script": {
                            "duration_margin": {"below": 0.10, "above": None},
                        },
                    }

                def get_tts_voice_configuration(self):
                    return _test_voice_configuration()

                def get_operational_profile_key(self):
                    return OperationalProfileKey(
                        ProfileComponent.GUION,
                        "vertical",
                        "guion_vertical",
                    )

                def get_profile_config(self):
                    return {
                        "duration": 4,
                        "builders": {
                            "script": True,
                            "voice": True,
                            "subtitles": True,
                            "storyboard": True,
                            "images": True,
                            "video": True,
                        },
                        "video_style": {"fps": 30},
                    }

                def get_subtitle_profile_by_key(self, subtitle_profile_key):
                    raise AssertionError(
                        "Subtitle profile must not be resolved"
                    )

            config = FakeConfig()
            with patch(
                "app.core.start.ProjectManager",
                return_value=project,
            ), patch(
                "app.core.start.ConfigManager",
                return_value=config,
            ), patch(
                "app.modules.standard.execution_coordinator.ScriptOperation.execute",
                return_value=type("Prepared", (), {"text": "Guion."})(),
            ), patch(
                "app.modules.standard.execution_coordinator.VoiceBuilder"
            ) as voice_builder, patch(
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
                "app.modules.standard.execution_coordinator.generate_video_clips",
                return_value=clips_manifest,
            ) as clips_builder, patch(
                "app.modules.standard.execution_coordinator.VideoBuilder"
            ) as video_builder, patch(
                "app.shared.media_probe.MediaProbe.get_duration",
                return_value=4.0,
            ):
                voice_builder.return_value.build.return_value = project.audio_path()
                audio_mixer.return_value.build.return_value = project.final_audio_path()
                storyboard_builder.return_value.build.return_value = project.storyboard_path()
                image_builder.return_value.build.return_value = project.images_manifest_path()
                video_builder.return_value.build.return_value = final_video

                result = start.run_application(
                    request=_video_request(
                        pipeline_mode="full_without_subtitles",
                        operational_profile_key=OperationalProfileKey(
                            ProfileComponent.GUION,
                            "vertical",
                            "guion_vertical",
                        ),
                    ),
                )

        self.assertEqual(final_video, result)
        subtitle_builder.assert_not_called()
        srt_optimizer.assert_not_called()
        clips_builder.assert_called_once()
        self.assertEqual(
            OperationalProfileKey(
                ProfileComponent.VIDEO,
                "vertical",
                "video_vertical",
            ),
            clips_builder.call_args.kwargs["profile_key"],
        )
        video_builder.assert_called_once_with(
            subtitle_profile=None,
            overlays_mode=None,
            render_subtitles=False,
            config_manager=config,
            project=project,
        )
        video_builder.return_value.build.assert_called_once_with(
            video_clips_manifest_path=clips_manifest,
        )
        self.assertNotIn("_sin_subtitulos", str(result))

    def test_generates_video_product_clips_from_storyboard_and_images(
        self
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            project = FakeProject(
                root
                / "output"
                / "video-product"
            )
            project.setup()

            image_1 = (
                root
                / "images"
                / "scene_001.png"
            )
            image_2 = (
                root
                / "images"
                / "scene_002.png"
            )
            image_1.parent.mkdir(
                parents=True,
                exist_ok=True
            )
            image_1.write_bytes(
                b"png1"
            )
            image_2.write_bytes(
                b"png2"
            )

            storyboard_path = (
                root
                / "storyboard.json"
            )
            storyboard_path.write_text(
                json.dumps(
                    [
                        _storyboard_scene(
                            1,
                            "Nikola Tesla",
                            "sentado junto a una lampara",
                        ),
                        _storyboard_scene(
                            2,
                            "Nikola Tesla",
                            "observa una bobina electrica",
                        ),
                    ],
                    ensure_ascii=False,
                    indent=4,
                ),
                encoding="utf-8"
            )

            images_manifest_path = (
                root
                / "images_manifest.json"
            )
            images_manifest_path.write_text(
                json.dumps(
                    [
                        {
                            "scene": 1,
                            "image": str(
                                image_1
                            ),
                            "duration": 4,
                        },
                        {
                            "scene": 2,
                            "image": str(
                                image_2
                            ),
                            "duration": 4,
                        },
                    ],
                    ensure_ascii=False,
                    indent=4,
                ),
                encoding="utf-8"
            )

            builder = FakeVideoComponentBuilder(
                project.base_path
                / "video_clips"
                / "unused.mp4"
            )

            with patch(
                "app.modules.video_component.clip_batch.os.replace",
                wraps=os.replace,
            ) as replace_file:
                with patch(
                    "app.modules.video_component.profile_parameters._random_video_seed",
                    return_value=847291635
                ):
                    manifest_path = clip_batch.generate_video_clips(
                        storyboard_path=storyboard_path,
                        images_manifest_path=images_manifest_path,
                        project=project,
                        video_builder=builder,
                        profile_key=OperationalProfileKey(
                            ProfileComponent.VIDEO,
                            "vertical",
                            "video_vertical",
                        ),
                    )
                    manifest = json.loads(
                        manifest_path.read_text(
                            encoding="utf-8"
                        )
                    )

                replace_file.assert_called_once()
                temporary_path, published_path = replace_file.call_args.args
                self.assertEqual(manifest_path, published_path)
                self.assertEqual(manifest_path.parent, temporary_path.parent)
                self.assertNotEqual(manifest_path, temporary_path)
                self.assertFalse(temporary_path.exists())

        self.assertEqual(
            project.base_path
            / "video_clips"
            / "video_clips_manifest.json",
            manifest_path
        )
        self.assertEqual(
            2,
            len(
                builder.calls
            )
        )
        self.assertEqual(
            "scene_001.mp4",
            builder.calls[0]["output_name"]
        )
        self.assertEqual(
            "scene_002.mp4",
            builder.calls[1]["output_name"]
        )
        self.assertEqual(
            1,
            builder.calls[0]["storyboard_scene"].scene_number
        )
        self.assertEqual(
            image_1,
            builder.calls[0]["source_path"]
        )
        self.assertEqual(
            448,
            builder.calls[0]["overrides"]["generation_width"]
        )
        self.assertEqual(
            847291635,
            builder.calls[0]["overrides"]["seed"]
        )

        self.assertEqual(
            2,
            len(
                manifest
            )
        )
        self.assertEqual(
            1,
            manifest[0]["scene"]
        )
        self.assertTrue(
            manifest[0]["output_clip"].endswith(
                "scene_001.mp4"
            )
        )
        self.assertEqual(
            "exact positive prompt",
            manifest[0]["positive_prompt"]
        )
        self.assertEqual(
            "exact negative prompt",
            manifest[0]["negative_prompt"]
        )
        self.assertEqual(
            "subtle motion, high stability",
            manifest[0]["motion_summary"]
        )
        self.assertEqual(
            "slow stable drift",
            manifest[0]["camera_motion"]
        )
        self.assertEqual(
            "subtle",
            manifest[0]["motion_intensity"]
        )
        self.assertEqual(
            "high",
            manifest[0]["stability"]
        )
        self.assertEqual(
            "slow and steady",
            manifest[0]["temporal_rhythm"]
        )
        self.assertEqual(
            "subtle",
            manifest[0]["motion_level"]
        )
        self.assertEqual(
            ["preserve source composition"],
            manifest[0]["preservation_constraints"]
        )
        self.assertEqual(
            ["avoid abrupt motion"],
            manifest[0]["avoidance_constraints"]
        )
        self.assertEqual(
            ["VisualTruth.visible_subject"],
            manifest[0]["source_trace"]
        )

    def test_failed_scene_keeps_existing_manifest_and_does_not_publish_partial_list(
        self
    ):
        class FailingSecondSceneBuilder(FakeVideoComponentBuilder):
            def generate_clip(self, *args, **kwargs):
                if self.calls:
                    raise RuntimeError("middle scene generation failed")
                return super().generate_clip(*args, **kwargs)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = FakeProject(root / "output" / "video-product")
            project.setup()
            images_dir = root / "images"
            images_dir.mkdir()
            first_image = images_dir / "scene_001.png"
            second_image = images_dir / "scene_002.png"
            first_image.write_bytes(b"png1")
            second_image.write_bytes(b"png2")
            storyboard_path = root / "storyboard.json"
            storyboard_path.write_text(
                json.dumps(
                    [
                        _storyboard_scene(1, "subject one", "moves"),
                        _storyboard_scene(2, "subject two", "moves"),
                    ]
                ),
                encoding="utf-8",
            )
            images_manifest_path = root / "images_manifest.json"
            images_manifest_path.write_text(
                json.dumps(
                    [
                        {"scene": 1, "image": str(first_image)},
                        {"scene": 2, "image": str(second_image)},
                    ]
                ),
                encoding="utf-8",
            )
            output_dir = project.base_path / "video_clips"
            output_dir.mkdir()
            manifest_path = output_dir / "video_clips_manifest.json"
            previous_manifest = b'[{"scene": 77, "published": true}]'
            manifest_path.write_bytes(previous_manifest)
            builder = FailingSecondSceneBuilder(output_dir / "unused.mp4")

            with patch(
                "app.modules.video_component.clip_batch._publish_video_clips_manifest_atomically",
            ) as publish_manifest:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "middle scene generation failed",
                ):
                    clip_batch.generate_video_clips(
                        storyboard_path=storyboard_path,
                        images_manifest_path=images_manifest_path,
                        project=project,
                        video_builder=builder,
                        profile_key=OperationalProfileKey(
                            ProfileComponent.VIDEO,
                            "vertical",
                            "video_vertical",
                        ),
                    )

            publish_manifest.assert_not_called()
            self.assertEqual(previous_manifest, manifest_path.read_bytes())
            self.assertTrue((output_dir / "scene_001.mp4").exists())
            self.assertEqual(
                [],
                list(output_dir.glob(".video_clips_manifest.json.*.tmp")),
            )

    def test_i2v_artifact_lease_cleans_only_owned_lossless_clips_after_public_render(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            clips_dir = root / "video_clips"
            clips_dir.mkdir()
            owned_lossless = clips_dir / "scene_001.mkv"
            h264_clip = clips_dir / "scene_002.mp4"
            external_lossless = root / "external.mkv"
            manifest_path = clips_dir / "video_clips_manifest.json"
            final_output = root / "video" / "final.mp4"
            owned_lossless.write_bytes(b"ffv1")
            h264_clip.write_bytes(b"h264")
            external_lossless.write_bytes(b"external")
            manifest_path.write_text(
                json.dumps(
                    [
                        {"scene": 1, "output_clip": str(owned_lossless)},
                        {"scene": 2, "output_clip": str(h264_clip)},
                        {"scene": 3, "output_clip": str(external_lossless)},
                    ]
                ),
                encoding="utf-8",
            )
            final_output.parent.mkdir()
            final_output.write_bytes(b"public-final")

            lease = clip_batch.I2VArtifactLease.from_manifest(manifest_path)
            failures = lease.cleanup_after_successful_public_render(final_output)

            self.assertEqual((owned_lossless,), lease.owned_lossless_paths)
            self.assertEqual((), failures)
            self.assertFalse(owned_lossless.exists())
            self.assertTrue(h264_clip.exists())
            self.assertTrue(external_lossless.exists())
            self.assertTrue(manifest_path.exists())
            self.assertTrue(final_output.exists())

    def test_i2v_artifact_lease_preserves_lossless_clip_without_confirmed_public_render(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            clips_dir = root / "video_clips"
            clips_dir.mkdir()
            owned_lossless = clips_dir / "scene_001.mkv"
            manifest_path = clips_dir / "video_clips_manifest.json"
            owned_lossless.write_bytes(b"ffv1")
            manifest_path.write_text(
                json.dumps([
                    {"scene": 1, "output_clip": str(owned_lossless)},
                ]),
                encoding="utf-8",
            )

            lease = clip_batch.I2VArtifactLease.from_manifest(manifest_path)
            failures = lease.cleanup_after_successful_public_render(
                root / "video" / "missing-final.mp4"
            )

            self.assertEqual((), failures)
            self.assertTrue(owned_lossless.exists())
            self.assertTrue(manifest_path.exists())

    def test_i2v_final_render_failure_preserves_lossless_clip_and_manifest(self):
        class FailingVideoBuilder:
            def build(self, **kwargs):
                raise RuntimeError("final render failed")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            clips_dir = root / "video_clips"
            clips_dir.mkdir()
            owned_lossless = clips_dir / "scene_001.mkv"
            manifest_path = clips_dir / "video_clips_manifest.json"
            owned_lossless.write_bytes(b"ffv1")
            manifest_path.write_text(
                json.dumps([
                    {"scene": 1, "output_clip": str(owned_lossless)},
                ]),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "final render failed"):
                clip_batch.build_public_video(
                    video_builder=FailingVideoBuilder(),
                    video_clips_manifest_path=manifest_path,
                )

            self.assertTrue(owned_lossless.exists())
            self.assertTrue(manifest_path.exists())

    def test_i2v_cleanup_failure_keeps_public_render_result(self):
        class SuccessfulVideoBuilder:
            def __init__(self, output_path):
                self.output_path = output_path

            def build(self, **kwargs):
                self.output_path.parent.mkdir(exist_ok=True)
                self.output_path.write_bytes(b"public-final")
                return self.output_path

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            clips_dir = root / "video_clips"
            clips_dir.mkdir()
            owned_lossless = clips_dir / "scene_001.mkv"
            manifest_path = clips_dir / "video_clips_manifest.json"
            output_path = root / "video" / "final.mp4"
            owned_lossless.write_bytes(b"ffv1")
            manifest_path.write_text(
                json.dumps([
                    {"scene": 1, "output_clip": str(owned_lossless)},
                ]),
                encoding="utf-8",
            )

            with patch.object(Path, "unlink", side_effect=OSError("locked")):
                result = clip_batch.build_public_video(
                    video_builder=SuccessfulVideoBuilder(output_path),
                    video_clips_manifest_path=manifest_path,
                )

            self.assertEqual(output_path, result)
            self.assertTrue(output_path.exists())
            self.assertTrue(owned_lossless.exists())
            self.assertTrue(manifest_path.exists())

    def test_direct_i2v_generation_does_not_consume_lossless_clip_lease(self):
        class LosslessBuilder(FakeVideoComponentBuilder):
            def generate_clip(
                self,
                source_path=None,
                output_dir=None,
                output_name="clip_001.mp4",
                storyboard_scene=None,
                **overrides,
            ):
                output_clip = Path(output_dir) / Path(output_name).with_suffix(".mkv")
                output_clip.parent.mkdir(parents=True, exist_ok=True)
                output_clip.write_bytes(b"ffv1")
                self.calls.append({
                    "source_path": Path(source_path),
                    "output_dir": Path(output_dir),
                    "output_name": output_name,
                    "storyboard_scene": storyboard_scene,
                    "overrides": overrides,
                })
                return FakeResult(output_clip, source_image=source_path)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = FakeProject(root / "output" / "video-product")
            project.setup()
            image_path = root / "images" / "scene_001.png"
            image_path.parent.mkdir()
            image_path.write_bytes(b"png")
            storyboard_path = root / "storyboard.json"
            storyboard_path.write_text(
                json.dumps([_storyboard_scene(1, "subject", "moves")]),
                encoding="utf-8",
            )
            images_manifest_path = root / "images_manifest.json"
            images_manifest_path.write_text(
                json.dumps([{"scene": 1, "image": str(image_path)}]),
                encoding="utf-8",
            )

            manifest_path = clip_batch.generate_video_clips(
                storyboard_path=storyboard_path,
                images_manifest_path=images_manifest_path,
                project=project,
                video_builder=LosslessBuilder(root / "unused.mkv"),
                profile_key=OperationalProfileKey(
                    ProfileComponent.VIDEO,
                    "vertical",
                    "video_vertical",
                ),
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            output_clip = Path(manifest[0]["output_clip"])

            self.assertEqual(".mkv", output_clip.suffix)
            self.assertTrue(output_clip.exists())


def _video_profile(
    name,
    seed_mode="random",
    seed=None
):
    if name == "Horizontal":
        profile = {
            "format": "horizontal",
            "video_component": {
                "profile": "Horizontal",
                "generation": {
                    "width": 672,
                    "height": 384,
                },
                "frames": 49,
                "fps": 12,
                "seed_mode": seed_mode,
                "sampling": {
                    "steps": 12,
                    "cfg": 5.0,
                    "sampler": "uni_pc",
                    "scheduler": "simple",
                },
            },
        }
        if seed is not None:
            profile["video_component"]["seed"] = seed
        return profile

    profile = {
        "format": "vertical",
        "video_component": {
            "profile": "Vertical",
            "generation": {
                "width": 384,
                "height": 672,
            },
            "frames": 49,
            "fps": 12,
            "seed_mode": seed_mode,
            "sampling": {
                "steps": 12,
                "cfg": 5.0,
                "sampler": "uni_pc",
                "scheduler": "simple",
            },
        },
    }
    if seed is not None:
        profile["video_component"]["seed"] = seed
    return profile


def _storyboard_scene(
    scene_number,
    subject,
    action
):
    return {
        "scene": scene_number,
        "text": f"{subject} {action}.",
        "visible_subject": subject,
        "visible_action": action,
        "visible_environment": "laboratorio electrico",
        "time_context": "noche",
        "key_objects": [
            "lampara",
            "bobina",
        ],
        "spatial_relationships": [
            "sujeto sentado junto a la mesa",
        ],
        "continuity_links": [
            "mismo laboratorio",
        ],
        "abstract_source": "descubrimiento cientifico",
        "filmable_interpretation": "escena cinematica realista",
        "visual_constraints": [
            "mantener ambiente de laboratorio",
        ],
        "visual_truth_status": "structured",
    }


if __name__ == "__main__":
    unittest.main()
