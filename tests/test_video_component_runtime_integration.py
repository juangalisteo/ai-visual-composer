import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core import start
from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
    ProfilePlatform,
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


class FakeResult:
    def __init__(
        self,
        output_clip,
        source_image=None,
        profile_name="Instagram",
        seed=123
    ):
        self.source_image = Path(
            source_image
            or output_clip
        )
        self.output_clip = Path(
            output_clip
        )
        self.manifest_path = None
        self.prompt_id = "prompt-id"
        self.backend = "ComfyUI"
        self.model = "wan2.2_ti2v_5B_fp16.safetensors"
        self.workflow = (
            "config/comfyui_wan22_ti2v_i2v_workflow_api.json"
        )
        self.seed = seed
        self.frames = 49
        self.fps = 12.0
        self.generation_width = 384
        self.generation_height = 672
        self.target_width = 1080
        self.target_height = 1920
        self.steps = 12
        self.cfg = 5.0
        self.sampler = "uni_pc"
        self.scheduler = "simple"
        self.profile_name = profile_name
        self.duration_seconds = 4.083333333333333
        self.fingerprint = "fake-fingerprint"
        self.positive_prompt = "exact positive prompt"
        self.negative_prompt = "exact negative prompt"
        self.motion_summary = "subtle motion, high stability"
        self.camera_motion = "slow stable drift"
        self.motion_intensity = "subtle"
        self.stability = "high"
        self.temporal_rhythm = "slow and steady"
        self.motion_level = "subtle"
        self.preservation_constraints = (
            "preserve source composition",
        )
        self.avoidance_constraints = (
            "avoid abrupt motion",
        )
        self.source_trace = (
            "VisualTruth.visible_subject",
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
                "Instagram"
            ),
            seed=overrides.get(
                "seed",
                123
            )
        )


class VideoComponentRuntimeIntegrationTest(unittest.TestCase):

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
                "app.core.start._random_video_seed",
                return_value=847291635
            ):
                result = start.ejecutar_video_i2v(
                    pipeline_start=0,
                    project=project,
                    profile_key=ProfileKey.for_component(
                        ProfileComponent.VIDEO,
                        ProfilePlatform.INSTAGRAM
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
            1080,
            call["overrides"]["target_width"]
        )
        self.assertEqual(
            1920,
            call["overrides"]["target_height"]
        )
        self.assertEqual(
            49,
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
            847291635,
            call["overrides"]["seed"]
        )

    def test_iniciar_dispatches_video_i2v_without_script_pipeline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            project = FakeProject(
                root / "output" / "runtime"
            )
            output_clip = (
                project.base_path
                / "video_clips"
                / "clip_001.mp4"
            )
            builder = FakeVideoComponentBuilder(
                output_clip
            )

            class FakeConfig:
                def get_ai_config(
                    self
                ):
                    return {}

                def get_profile_key(
                    self
                ):
                    return ProfileKey.for_component(
                        ProfileComponent.VIDEO,
                        ProfilePlatform.YOUTUBE
                    )

                def get_profile_config(
                    self
                ):
                    return _video_profile(
                        "YouTube"
                    )

            with patch.dict(
                "os.environ",
                {
                    "MC_PIPELINE_MODE": "video_i2v",
                },
                clear=False,
            ), patch(
                "app.core.start.ProjectManager",
                return_value=project
            ), patch(
                "app.core.start.ConfigManager",
                return_value=FakeConfig()
            ), patch(
                "app.core.start.VideoComponentBuilder",
                return_value=builder
            ), patch(
                "app.core.start.ejecutar_guion"
            ) as script_mock, patch(
                "app.core.start._random_video_seed",
                return_value=998877
            ):
                result = start.iniciar()

        script_mock.assert_not_called()
        self.assertEqual(
            output_clip,
            result
        )
        self.assertEqual(
            800,
            builder.calls[0]["overrides"]["generation_width"]
        )
        self.assertEqual(
            448,
            builder.calls[0]["overrides"]["generation_height"]
        )
        self.assertEqual(
            998877,
            builder.calls[0]["overrides"]["seed"]
        )

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
                start.ejecutar_video_i2v(
                    project=FakeProject(
                        Path(
                            temp_dir
                        )
                        / "output"
                    ),
                    profile_key=ProfileKey.for_component(
                        ProfileComponent.VIDEO,
                        ProfilePlatform.INSTAGRAM
                    ),
                    source_path=missing,
                )

    def test_video_profiles_exist_with_validated_parameters(self):
        cases = (
            (
                "config/profiles/video/instagram/wan_i2v_instagram.json",
                448,
                800,
                1080,
                1920,
                20,
            ),
            (
                "config/profiles/video/youtube/wan_i2v_youtube.json",
                800,
                448,
                1920,
                1080,
                20,
            ),
        )

        for (
            profile_path,
            generation_width,
            generation_height,
            target_width,
            target_height,
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
                    target_width,
                    video_component[
                        "target"
                    ][
                        "width"
                    ]
                )
                self.assertEqual(
                    target_height,
                    video_component[
                        "target"
                    ][
                        "height"
                    ]
                )
                self.assertEqual(
                    49,
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
            "config/profiles/guion/instagram/perfil_guion_instagram.json",
            "config/profiles/guion/youtube/perfil_guion_youtube.json",
            "config/profiles/imagen/instagram/perfil_imagen_instagram.json",
            "config/profiles/imagen/youtube/perfil_imagen_youtube.json",
            "config/profiles/video/instagram/perfil_video_instagram.json",
            "config/profiles/video/youtube/perfil_video_youtube.json",
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
            "Instagram"
        )

        with patch(
            "app.core.start._random_video_seed",
            return_value=111
        ):
            first = start._video_i2v_overrides(
                profile
            )

        with patch(
            "app.core.start._random_video_seed",
            return_value=222
        ):
            second = start._video_i2v_overrides(
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
            "Instagram",
            seed_mode="fixed",
            seed=123456789
        )

        with patch(
            "app.core.start._random_video_seed"
        ) as random_mock:
            overrides = start._video_i2v_overrides(
                profile
            )

        random_mock.assert_not_called()
        self.assertEqual(
            123456789,
            overrides["seed"]
        )

    def test_iniciar_video_product_composes_final_video_from_i2v_clips(
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
            intro_outro_selection = object()
            requested_subtitle_styles = []

            class FakeConfig:
                def get_ai_config(
                    self
                ):
                    return {}

                def get_profile_key(
                    self
                ):
                    return ProfileKey.for_component(
                        ProfileComponent.VIDEO,
                        ProfilePlatform.INSTAGRAM
                    )

                def get_profile_config(
                    self
                ):
                    return {
                        "platform": "instagram",
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

                def get_subtitle_profile(
                    self,
                    style
                ):
                    requested_subtitle_styles.append(style)
                    return resolved_subtitle_profile

            with patch.dict(
                "os.environ",
                {
                    "MC_VISUAL_PIPELINE": "video",
                    "MC_PIPELINE_MODE": "full",
                    "MC_MUSIC_CATEGORY": "",
                },
                clear=False,
            ), patch(
                "app.core.start.ProjectManager",
                return_value=project
            ), patch(
                "app.core.start.ConfigManager",
                return_value=FakeConfig()
            ), patch(
                "app.core.start.ejecutar_guion",
                return_value=type(
                    "PreparedScript",
                    (),
                    {
                        "text": "Guion de prueba."
                    }
                )()
            ), patch(
                "app.core.start.VoiceBuilder"
            ) as voice_builder, patch(
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
                "app.core.start.generar_video_clips_i2v",
                return_value=video_clips_manifest
            ) as clips_builder, patch(
                "app.core.start.VideoBuilder"
            ) as video_builder, patch(
                "app.core.start.MediaProbe.get_duration",
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

                result = start.iniciar(
                    subtitle_style="single_line",
                    intro_outro_selection=(
                        intro_outro_selection
                    ),
                )

        self.assertEqual(
            final_video,
            result
        )
        self.assertEqual(
            ["single_line"],
            requested_subtitle_styles
        )
        clips_builder.assert_called_once()
        srt_optimizer.assert_called_once_with(
            subtitle_profile=resolved_subtitle_profile,
            render_fps=30
        )
        srt_optimizer.return_value.optimize.assert_called_once_with(
            canonical_content="Guion de prueba.",
        )
        video_builder.assert_called_once_with(
            subtitle_profile=resolved_subtitle_profile,
            intro_outro_selection=intro_outro_selection,
        )
        video_builder.return_value.build.assert_called_once_with(
            video_clips_manifest_path=video_clips_manifest
        )

    def test_iniciar_video_product_without_subtitles_keeps_design_i2v_identity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = FakeProject(Path(temp_dir) / "output" / "video-product")
            final_video = project.video_path()
            clips_manifest = (
                project.base_path
                / "video_clips"
                / "video_clips_manifest.json"
            )
            subtitle_profile = object()

            class FakeConfig:
                def get_ai_config(self):
                    return {}

                def get_profile_key(self):
                    return ProfileKey.for_component(
                        ProfileComponent.GUION,
                        ProfilePlatform.INSTAGRAM,
                        family="design",
                        profile_id=(
                            "guion_instagram_design_"
                            "modo_conciencia_reels"
                        ),
                    )

                def get_profile_config(self):
                    return {
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

                def get_subtitle_profile(self, style):
                    raise AssertionError(
                        "Subtitle profile must not be resolved"
                    )

            config = FakeConfig()
            with patch.dict(
                "os.environ",
                {
                    "MC_VISUAL_PIPELINE": "video",
                    "MC_PIPELINE_MODE": "full_without_subtitles",
                    "MC_MUSIC_CATEGORY": "",
                },
                clear=False,
            ), patch(
                "app.core.start.ProjectManager",
                return_value=project,
            ), patch(
                "app.core.start.ConfigManager",
                return_value=config,
            ), patch(
                "app.core.start.ejecutar_guion",
                return_value=type("Prepared", (), {"text": "Guion."})(),
            ), patch(
                "app.core.start.VoiceBuilder"
            ) as voice_builder, patch(
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
                "app.core.start.generar_video_clips_i2v",
                return_value=clips_manifest,
            ) as clips_builder, patch(
                "app.core.start.VideoBuilder"
            ) as video_builder, patch(
                "app.core.start.MediaProbe.get_duration",
                return_value=4.0,
            ):
                voice_builder.return_value.build.return_value = project.audio_path()
                audio_mixer.return_value.build.return_value = project.final_audio_path()
                storyboard_builder.return_value.build.return_value = project.storyboard_path()
                image_builder.return_value.build.return_value = project.images_manifest_path()
                video_builder.return_value.build.return_value = final_video

                result = start.iniciar()

        self.assertEqual(final_video, result)
        subtitle_builder.assert_not_called()
        srt_optimizer.assert_not_called()
        clips_builder.assert_called_once()
        self.assertEqual(
            ProfileKey.for_component(
                ProfileComponent.VIDEO,
                ProfilePlatform.INSTAGRAM,
                family="design",
                profile_id=(
                    "video_instagram_design_"
                    "modo_conciencia_reels"
                ),
            ),
            clips_builder.call_args.kwargs["profile_key"],
        )
        video_builder.assert_called_once_with(
            subtitle_profile=None,
            render_subtitles=False,
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
                "app.core.start._random_video_seed",
                return_value=847291635
            ):
                manifest_path = start.generar_video_clips_i2v(
                    storyboard_path=storyboard_path,
                    images_manifest_path=images_manifest_path,
                    project=project,
                    video_builder=builder,
                    profile_key=ProfileKey.for_component(
                        ProfileComponent.VIDEO,
                        ProfilePlatform.INSTAGRAM
                    ),
                )
                manifest = json.loads(
                    manifest_path.read_text(
                        encoding="utf-8"
                    )
                )

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


def _video_profile(
    name,
    seed_mode="random",
    seed=None
):
    if name == "YouTube":
        profile = {
            "platform": "video",
            "format": "youtube",
            "video_component": {
                "profile": "YouTube",
                "generation": {
                    "width": 672,
                    "height": 384,
                },
                "target": {
                    "width": 1920,
                    "height": 1080,
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
        "platform": "video",
        "format": "instagram",
        "video_component": {
            "profile": "Instagram",
            "generation": {
                "width": 384,
                "height": 672,
            },
            "target": {
                "width": 1080,
                "height": 1920,
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
