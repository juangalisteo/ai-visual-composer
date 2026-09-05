import json
import os
import secrets
import time
from pathlib import Path

from app.managers.pipeline_summary import PipelineSummary
from app.managers.project_manager import ProjectManager

from app.modules.audio.audio_mixer import AudioMixer
from app.modules.audio.music_selector import MusicSelector
from app.modules.audio.voice_builder import VoiceBuilder
from app.modules.images.image_builder import ImageBuilder
from app.modules.images import (
    ImageDesignPreparationService,
    ImageDesignVisualTruthAdapter,
)
from app.modules.script import (
    ScriptOperation,
    ScriptPreparationService,
)
from app.modules.storyboard.storyboard_builder import StoryboardBuilder
from app.modules.subtitles.srt_optimizer import SrtOptimizer
from app.modules.subtitles.subtitle_builder import SubtitleBuilder
from app.modules.video.video_builder import VideoBuilder
from app.modules.video_component import (
    VideoComponentBuilder,
    VideoDesignPreparationService,
    VideoDesignVisualTruthAdapter,
)
from app.modules.studio import (
    StudioInputPreparationService,
    StudioPhase1Preparation,
    StudioProfileLoader,
)

from app.domain.adapters import StoryboardSceneAdapter
from app.shared.config_contract import (
    require_bool,
    require_int,
    require_mapping,
)
from app.shared.config_manager import ConfigManager
from app.shared.media_probe import MediaProbe
from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
)
from app.shared.profile_resolver import ProfileResolver


def iniciar(
    subtitle_style=None,
    intro_outro_selection=None,
):
    pipeline_start = time.perf_counter()

    pipeline_mode = os.environ.get(
        "MC_PIPELINE_MODE",
        "full"
    ).strip().lower()

    if pipeline_mode == "studio":
        return ejecutar_studio_fase_1(
            subtitle_style=subtitle_style
        )

    project = ProjectManager()

    visual_pipeline = os.environ.get(
        "MC_VISUAL_PIPELINE",
        "image"
    ).strip().lower()

    if pipeline_mode == "design_image":
        return ejecutar_diseno_imagen(
            pipeline_start=pipeline_start,
            project=project
        )

    if pipeline_mode == "design_video":
        return ejecutar_diseno_video(
            pipeline_start=pipeline_start,
            project=project
        )

    config = ConfigManager()

    if pipeline_mode != "script":
        project.setup()

    ai_config = config.get_ai_config()
    profile = config.get_profile_config()

    if pipeline_mode == "video_i2v":
        return ejecutar_video_i2v(
            pipeline_start=pipeline_start,
            project=project,
            profile_key=config.get_profile_key()
        )

    builders = _required_builders(
        profile
    )
    subtitle_profile = None

    if (
        pipeline_mode in {
            "full",
            "subtitles",
            "storyboard",
        }
        and builders.get(
            "subtitles",
            False
        )
    ):
        subtitle_profile = (
            config.get_subtitle_profile(
                subtitle_style
            )
        )

    input_script_path = Path(
        "input/guion.txt"
    )

    input_topic_path = Path(
        "input/tema.txt"
    )

    output_script_path = (
        project.script_path()
    )
    storyboard_path = None
    images_manifest_path = None

    summary = PipelineSummary(
        project.project_name
    )

    stage_times = {}

    prepared_script, script_elapsed = _measure_stage(
        ejecutar_guion,
        builders=builders,
        ai_config=ai_config,
        profile=profile,
        input_script_path=input_script_path,
        input_topic_path=input_topic_path,
        output_script_path=output_script_path
    )

    stage_times["Script"] = (
        script_elapsed
    )

    final_result = (
        output_script_path
    )

    if pipeline_mode == "script":
        _complete_summary(
            summary=summary,
            stage_times=stage_times,
            project=project,
            pipeline_start=pipeline_start
        )

        return final_result

    if builders.get(
        "voice",
        False
    ):
        voice_path, voice_elapsed = _measure_stage(
            VoiceBuilder().build,
            prepared_script.text
        )

        stage_times["Voces"] = (
            voice_elapsed
        )

        final_result = voice_path

        music_category = os.environ.get(
            "MC_MUSIC_CATEGORY",
            ""
        ).strip()

        audio_start = time.perf_counter()

        if music_category:
            music_path = (
                MusicSelector().select(
                    music_category
                )
            )
        else:
            music_path = None

        final_audio_path = (
            AudioMixer().build(
                music_path=music_path
            )
        )

        stage_times["Audio"] = (
            time.perf_counter()
            - audio_start
        )

        final_result = final_audio_path

    if pipeline_mode == "audio":
        _complete_summary(
            summary=summary,
            stage_times=stage_times,
            project=project,
            pipeline_start=pipeline_start
        )

        return final_result

    if builders.get(
        "subtitles",
        False
    ):
        subtitles_start = (
            time.perf_counter()
        )

        subtitle_path = (
            SubtitleBuilder().build()
        )

        optimized_subtitle_path = (
            SrtOptimizer(
                subtitle_profile=subtitle_profile,
                render_fps=_required_render_fps(
                    profile
                )
            ).optimize()
        )

        stage_times["Subtítulos"] = (
            time.perf_counter()
            - subtitles_start
        )

        final_result = (
            optimized_subtitle_path
            or subtitle_path
        )

    if pipeline_mode == "subtitles":
        _complete_summary(
            summary=summary,
            stage_times=stage_times,
            project=project,
            pipeline_start=pipeline_start
        )

        return final_result

    if builders.get(
        "storyboard",
        False
    ):
        storyboard_path, storyboard_elapsed = (
            _measure_stage(
                StoryboardBuilder().build
            )
        )

        stage_times["Storyboard"] = (
            storyboard_elapsed
        )

        final_result = storyboard_path

    if pipeline_mode == "storyboard":
        _complete_summary(
            summary=summary,
            stage_times=stage_times,
            project=project,
            pipeline_start=pipeline_start
        )

        return final_result

    if builders.get(
        "images",
        False
    ):
        images_manifest_path, images_elapsed = (
            _measure_stage(
                ImageBuilder().build
            )
        )

        stage_times["Imágenes"] = (
            images_elapsed
        )

        final_result = (
            images_manifest_path
        )

    if (
        visual_pipeline == "video"
        and pipeline_mode == "full"
    ):
        profile_key = config.get_profile_key()
        if (
            isinstance(
                profile_key,
                ProfileKey
            )
            and profile_key.component is ProfileComponent.GUION
        ):
            profile_key = ProfileKey.for_component(
                ProfileComponent.VIDEO,
                profile_key.platform
            )
        video_clips_manifest_path, video_i2v_elapsed = (
            _measure_stage(
                generar_video_clips_i2v,
                storyboard_path=(
                    storyboard_path
                    or project.storyboard_path()
                ),
                images_manifest_path=(
                    images_manifest_path
                    or project.images_manifest_path()
                ),
                project=project,
                profile_key=profile_key
            )
        )

        stage_times["Video I2V"] = (
            video_i2v_elapsed
        )

        final_result = (
            video_clips_manifest_path
        )

        video_builder_options = {
            "subtitle_profile": subtitle_profile
        }
        if intro_outro_selection is not None:
            video_builder_options[
                "intro_outro_selection"
            ] = intro_outro_selection

        video_path, video_elapsed = (
            _measure_stage(
                VideoBuilder(
                    **video_builder_options
                ).build,
                video_clips_manifest_path=(
                    video_clips_manifest_path
                )
            )
        )

        stage_times["Vídeo"] = (
            video_elapsed
        )

        final_result = video_path

    if (
        visual_pipeline != "video"
        and builders.get(
            "video",
            False
        )
    ):
        video_path, video_elapsed = (
            _measure_stage(
                VideoBuilder(
                    subtitle_profile=subtitle_profile
                ).build
            )
        )

        stage_times["Vídeo"] = (
            video_elapsed
        )

        final_result = video_path

    _complete_summary(
        summary=summary,
        stage_times=stage_times,
        project=project,
        pipeline_start=pipeline_start
    )

    return final_result


def ejecutar_studio_fase_1(
    subtitle_style,
    config_manager=None,
    profile_loader=None,
    input_preparation_service=None,
):
    """Validate and transport Studio inputs without creating a project."""
    config = config_manager or ConfigManager()
    profile_key = config.get_profile_key()
    if profile_key is None:
        raise ValueError(
            "STUDIO requiere una identidad de perfil estructurada."
        )
    if profile_key.component is not ProfileComponent.STUDIO:
        raise ValueError(
            "La ejecucion STUDIO requiere component=studio."
        )

    profile = (profile_loader or StudioProfileLoader()).load(
        config.get_profile_config(),
        profile_key,
    )
    subtitle_profile = config.get_subtitle_profile(subtitle_style)
    prepared_input = (
        input_preparation_service
        or StudioInputPreparationService()
    ).prepare(profile)

    return StudioPhase1Preparation(
        profile_key=profile_key,
        profile=profile,
        subtitle_profile=subtitle_profile,
        video_path=prepared_input.video_path,
        subtitle_path=prepared_input.subtitle_path,
    )


def cargar_o_generar_guion(
    builders,
    ai_config,
    profile,
    input_script_path,
    input_topic_path,
    output_script_path,
    script_builder_factory=None
):
    return preparar_guion(
        builders=builders,
        ai_config=ai_config,
        profile=profile,
        input_script_path=input_script_path,
        input_topic_path=input_topic_path,
        output_script_path=output_script_path,
        script_builder_factory=script_builder_factory
    ).text


def ejecutar_guion(
    builders,
    ai_config,
    profile,
    input_script_path,
    input_topic_path,
    output_script_path
):
    source_mode = os.environ.get(
        "MC_SCRIPT_SOURCE",
        "generated"
    ).strip().lower()

    return ScriptOperation().execute(
        builders=builders,
        ai_config=ai_config,
        profile=profile,
        input_script_path=input_script_path,
        input_topic_path=input_topic_path,
        output_script_path=output_script_path,
        source_mode=source_mode
    )


def ejecutar_diseno_imagen(
    pipeline_start=None,
    project=None,
    input_design_path=None,
    preparation_service=None,
    visual_truth_adapter=None,
    image_builder=None
):
    if pipeline_start is None:
        pipeline_start = time.perf_counter()

    project = (
        project
        or ProjectManager()
    )

    summary = PipelineSummary(
        project.project_name
    )

    preparation_service = (
        preparation_service
        or ImageDesignPreparationService()
    )
    visual_truth_adapter = (
        visual_truth_adapter
        or ImageDesignVisualTruthAdapter()
    )
    image_builder = (
        image_builder
        or ImageBuilder()
    )

    prepared_design = preparation_service.prepare(
        input_path=(
            input_design_path
            or Path("input/guion_imagen.txt")
        )
    )

    scenes = visual_truth_adapter.adapt(
        prepared_design
    )

    _ensure_single_design_scene(
        scenes
    )

    storyboard_path = (
        project.storyboard_path()
    )
    storyboard_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )
    storyboard_path.write_text(
        json.dumps(
            scenes,
            ensure_ascii=False,
            indent=4
        ),
        encoding="utf-8"
    )

    images_manifest_path, images_elapsed = _measure_stage(
        image_builder.build,
        storyboard_path=storyboard_path,
        output_dir=project.images_dir()
    )

    _ensure_single_design_image(
        images_manifest_path
    )

    _complete_summary(
        summary=summary,
        stage_times={
            "Imágenes": images_elapsed
        },
        project=project,
        pipeline_start=pipeline_start
    )

    return images_manifest_path


def ejecutar_diseno_video(
    pipeline_start=None,
    project=None,
    input_design_path=None,
    preparation_service=None,
    visual_truth_adapter=None,
    image_builder=None,
    video_builder=None,
    profile=None,
    profile_key=None
):
    if pipeline_start is None:
        pipeline_start = time.perf_counter()

    project = (
        project
        or ProjectManager()
    )

    summary = PipelineSummary(
        project.project_name
    )

    preparation_service = (
        preparation_service
        or VideoDesignPreparationService()
    )
    visual_truth_adapter = (
        visual_truth_adapter
        or VideoDesignVisualTruthAdapter()
    )
    image_builder = (
        image_builder
        or ImageBuilder()
    )
    video_builder = (
        video_builder
        or VideoComponentBuilder()
    )
    if profile is None:
        config = ConfigManager()
        profile = config.get_profile_config()
        if profile_key is None:
            profile_key = config.get_profile_key()

    prepared_design = preparation_service.prepare(
        input_path=(
            input_design_path
            or Path("input/guion_video.txt")
        )
    )

    scenes = visual_truth_adapter.adapt(
        prepared_design
    )

    _ensure_single_video_design_scene(
        scenes
    )

    storyboard_path = (
        project.storyboard_path()
    )
    storyboard_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )
    storyboard_path.write_text(
        json.dumps(
            scenes,
            ensure_ascii=False,
            indent=4
        ),
        encoding="utf-8"
    )

    images_manifest_path, images_elapsed = _measure_stage(
        image_builder.build,
        storyboard_path=storyboard_path,
        output_dir=project.images_dir()
    )

    _ensure_single_design_image(
        images_manifest_path
    )

    video_clips_manifest_path, video_elapsed = _measure_stage(
        generar_video_clips_i2v,
        storyboard_path=storyboard_path,
        images_manifest_path=images_manifest_path,
        project=project,
        video_builder=video_builder,
        profile_key=profile_key
    )

    output_clip = _ensure_single_video_design_clip(
        video_clips_manifest_path
    )

    _complete_summary(
        summary=summary,
        stage_times={
            "Imágenes": images_elapsed,
            "Video I2V": video_elapsed
        },
        project=project,
        pipeline_start=pipeline_start
    )

    return output_clip


def ejecutar_video_i2v(
    pipeline_start=None,
    project=None,
    profile_key=None,
    source_path=None,
    video_builder=None
):
    if pipeline_start is None:
        pipeline_start = time.perf_counter()

    project = (
        project
        or ProjectManager()
    )

    project.setup()

    video_profile = _load_video_component_profile(
        profile_key
    )

    video_builder = (
        video_builder
        or VideoComponentBuilder()
    )

    output_dir = (
        project.base_path
        / "video_clips"
    )

    result, video_elapsed = _measure_stage(
        video_builder.generate_clip,
        source_path=(
            source_path
            or Path("tests/fixtures/video/source.png")
        ),
        output_dir=output_dir,
        **_video_i2v_overrides(
            video_profile
        )
    )

    summary = PipelineSummary(
        project.project_name
    )
    summary.set_media_duration(
        result.duration_seconds
    )
    summary.add_stage(
        "Video I2V",
        video_elapsed
    )
    summary.set_total_time(
        time.perf_counter()
        - pipeline_start
    )
    summary.print()

    return result.output_clip


def generar_video_clips_i2v(
    storyboard_path,
    images_manifest_path,
    project=None,
    video_builder=None,
    profile_key=None
):
    project = (
        project
        or ProjectManager()
    )

    video_profile = _load_video_component_profile(
        profile_key
    )

    video_builder = (
        video_builder
        or VideoComponentBuilder()
    )

    storyboard_path = Path(
        storyboard_path
    )
    images_manifest_path = Path(
        images_manifest_path
    )

    scenes = _load_storyboard_scenes(
        storyboard_path
    )
    image_entries = _load_image_manifest_entries(
        images_manifest_path
    )

    scenes_by_number = {
        int(
            scene.get(
                "scene"
            )
        ): scene
        for scene in scenes
    }

    output_dir = (
        project.base_path
        / "video_clips"
    )
    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    clip_entries = []

    for entry in image_entries:
        scene_number = _required_manifest_scene_number(
            entry
        )
        scene = scenes_by_number.get(
            scene_number
        )
        if scene is None:
            raise ValueError(
                "No existe una escena de storyboard "
                f"para la imagen {scene_number}."
            )

        source_image = Path(
            entry.get(
                "image",
                ""
            )
        )
        if not source_image.exists():
            raise FileNotFoundError(
                "No existe la imagen base para Video: "
                f"{source_image}"
            )

        storyboard_scene = (
            StoryboardSceneAdapter.from_visual_truth(
                scene=scene,
                default_scene_number=scene_number
            )
        )

        result = video_builder.generate_clip(
            source_path=source_image,
            output_dir=output_dir,
            output_name=f"scene_{scene_number:03d}.mp4",
            storyboard_scene=storyboard_scene,
            **_video_i2v_overrides(
                video_profile
            )
        )

        clip_entries.append(
            _build_video_clip_manifest_entry(
                result=result,
                storyboard_scene=storyboard_scene,
                image_entry=entry
            )
        )

    manifest_path = (
        output_dir
        / "video_clips_manifest.json"
    )
    manifest_path.write_text(
        json.dumps(
            clip_entries,
            ensure_ascii=False,
            indent=4
        ),
        encoding="utf-8"
    )

    return manifest_path


def _load_storyboard_scenes(
    storyboard_path
):
    data = json.loads(
        Path(
            storyboard_path
        ).read_text(
            encoding="utf-8"
        )
    )
    if not isinstance(
        data,
        list
    ):
        raise ValueError(
            "El storyboard de Video debe ser una lista de escenas."
        )
    return data


def _load_image_manifest_entries(
    images_manifest_path
):
    data = json.loads(
        Path(
            images_manifest_path
        ).read_text(
            encoding="utf-8"
        )
    )
    if not isinstance(
        data,
        list
    ):
        raise ValueError(
            "El manifiesto de imágenes debe ser una lista."
        )
    return data


def _required_manifest_scene_number(
    entry
):
    if not isinstance(
        entry,
        dict
    ):
        raise ValueError(
            "Cada entrada del manifiesto de imágenes "
            "debe ser un diccionario."
        )

    try:
        return int(
            entry[
                "scene"
            ]
        )
    except (
        KeyError,
        TypeError,
        ValueError
    ) as error:
        raise ValueError(
            "Cada imagen base de Video debe declarar scene."
        ) from error


def _load_video_component_profile(
    profile_key
):
    if not isinstance(
        profile_key,
        ProfileKey
    ):
        raise TypeError(
            "La configuracion Wan requiere un ProfileKey "
            "VIDEO explicito."
        )

    if profile_key.component is not ProfileComponent.VIDEO:
        raise ValueError(
            "La configuracion Wan requiere identidad del "
            "componente video."
        )

    return ProfileResolver().load_video_component(
        profile_key
    )


def _build_video_clip_manifest_entry(
    result,
    storyboard_scene,
    image_entry
):
    return {
        "scene": storyboard_scene.scene_number,
        "source_image": str(
            result.source_image
        ),
        "image_manifest_entry": image_entry,
        "output_clip": str(
            result.output_clip
        ),
        "positive_prompt": result.positive_prompt,
        "negative_prompt": result.negative_prompt,
        "motion_summary": result.motion_summary,
        "camera_motion": result.camera_motion,
        "motion_intensity": result.motion_intensity,
        "stability": result.stability,
        "temporal_rhythm": result.temporal_rhythm,
        "motion_level": result.motion_level,
        "preservation_constraints": list(
            result.preservation_constraints
        ),
        "avoidance_constraints": list(
            result.avoidance_constraints
        ),
        "source_trace": list(
            result.source_trace
        ),
        "profile": result.profile_name,
        "backend": result.backend,
        "model": result.model,
        "workflow": result.workflow,
        "prompt_id": result.prompt_id,
        "seed": result.seed,
        "frames": result.frames,
        "fps": result.fps,
        "generation_width": result.generation_width,
        "generation_height": result.generation_height,
        "target_width": result.target_width,
        "target_height": result.target_height,
        "steps": result.steps,
        "cfg": result.cfg,
        "sampler": result.sampler,
        "scheduler": result.scheduler,
        "duration_seconds": result.duration_seconds,
        "fingerprint": result.fingerprint,
    }


def preparar_guion(
    builders,
    ai_config,
    profile,
    input_script_path,
    input_topic_path,
    output_script_path,
    script_builder_factory=None
):
    service_kwargs = {}

    if script_builder_factory is not None:
        service_kwargs[
            "script_builder_factory"
        ] = script_builder_factory

    return ScriptPreparationService(
        **service_kwargs
    ).prepare(
        builders=builders,
        ai_config=ai_config,
        profile=profile,
        input_script_path=input_script_path,
        input_topic_path=input_topic_path,
        output_script_path=output_script_path
    )


def _video_i2v_overrides(
    profile
):
    video_component = profile.get(
        "video_component",
        {}
    )

    if not video_component:
        raise ValueError(
            "El perfil de Video debe definir video_component."
        )

    generation = video_component.get(
        "generation",
        {}
    )
    target = video_component.get(
        "target",
        {}
    )
    sampling = video_component.get(
        "sampling",
        {}
    )

    return {
        "profile_name": str(
            video_component.get(
                "profile",
                profile.get(
                    "platform",
                    ""
                )
            )
        ),
        "generation_width": _required_int(
            generation,
            "width",
            "generation.width"
        ),
        "generation_height": _required_int(
            generation,
            "height",
            "generation.height"
        ),
        "target_width": _required_int(
            target,
            "width",
            "target.width"
        ),
        "target_height": _required_int(
            target,
            "height",
            "target.height"
        ),
        "frames": _required_int(
            video_component,
            "frames",
            "frames"
        ),
        "fps": _required_float(
            video_component,
            "fps",
            "fps"
        ),
        "seed": _resolve_video_seed(
            video_component
        ),
        "steps": _required_int(
            sampling,
            "steps",
            "sampling.steps"
        ),
        "cfg": _required_float(
            sampling,
            "cfg",
            "sampling.cfg"
        ),
        "sampler": _required_text(
            sampling,
            "sampler",
            "sampling.sampler"
        ),
        "scheduler": _required_text(
            sampling,
            "scheduler",
            "sampling.scheduler"
        ),
    }


def _resolve_video_seed(
    video_component
):
    seed_mode = str(
        video_component.get(
            "seed_mode",
            ""
        )
    ).strip().lower()

    if seed_mode == "random":
        return _random_video_seed()

    if seed_mode == "fixed":
        return _required_seed(
            video_component
        )

    raise ValueError(
        "Parámetro de vídeo inválido: seed_mode."
    )


def _random_video_seed():
    return secrets.randbelow(
        2 ** 63
    )


def _required_seed(
    video_component
):
    try:
        seed = int(
            video_component[
                "seed"
            ]
        )
    except (
        KeyError,
        TypeError,
        ValueError
    ) as error:
        raise ValueError(
            "Parámetro de vídeo inválido: seed."
        ) from error

    if seed < 0:
        raise ValueError(
            "Parámetro de vídeo inválido: seed."
        )

    return seed


def _required_int(
    data,
    key,
    label
):
    try:
        value = int(
            data[key]
        )
    except (
        KeyError,
        TypeError,
        ValueError
    ) as error:
        raise ValueError(
            f"Parámetro de vídeo inválido: {label}."
        ) from error

    if value <= 0:
        raise ValueError(
            f"Parámetro de vídeo inválido: {label}."
        )

    return value


def _required_float(
    data,
    key,
    label
):
    try:
        value = float(
            data[key]
        )
    except (
        KeyError,
        TypeError,
        ValueError
    ) as error:
        raise ValueError(
            f"Parámetro de vídeo inválido: {label}."
        ) from error

    if value <= 0:
        raise ValueError(
            f"Parámetro de vídeo inválido: {label}."
        )

    return value


def _required_text(
    data,
    key,
    label
):
    value = str(
        data.get(
            key,
            ""
        )
    ).strip()

    if not value:
        raise ValueError(
            f"Parámetro de vídeo inválido: {label}."
        )

    return value


def _required_builders(profile):
    builders = require_mapping(
        profile,
        "builders",
        "builders"
    )
    required_names = (
        "script",
        "voice",
        "subtitles",
        "storyboard",
        "images",
        "video",
    )
    return {
        name: require_bool(
            builders,
            name,
            f"builders.{name}"
        )
        for name in required_names
    }


def _required_render_fps(profile):
    video_style = require_mapping(
        profile,
        "video_style",
        "video_style"
    )
    fps = require_int(
        video_style,
        "fps",
        "video_style.fps"
    )
    if fps <= 0:
        raise ValueError(
            "La configuracion video_style.fps debe ser "
            "superior a cero."
        )
    return fps


def _measure_stage(
    function,
    *args,
    **kwargs
):
    start = time.perf_counter()

    result = function(
        *args,
        **kwargs
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    return result, elapsed


def _ensure_single_design_scene(
    scenes
):
    if not isinstance(
        scenes,
        list
    ):
        raise ValueError(
            "El diseño visual debe producir una lista "
            "de escenas."
        )

    if len(
        scenes
    ) != 1:
        raise ValueError(
            "El diseño visual debe producir exactamente "
            "una escena."
        )


def _ensure_single_design_image(
    images_manifest_path
):
    manifest_path = Path(
        images_manifest_path
    )
    manifest = json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        manifest,
        list
    ):
        raise ValueError(
            "El manifiesto de diseño debe contener "
            "una lista de imágenes."
        )

    if len(
        manifest
    ) != 1:
        raise ValueError(
            "El diseño visual debe generar exactamente "
            "una imagen."
        )

    image_name = Path(
        str(
            manifest[0].get(
                "image",
                ""
            )
        )
    ).name

    if image_name != "scene_001.png":
        raise ValueError(
            "La imagen de diseño debe corresponder a "
            "scene_001.png."
        )


def _ensure_single_video_design_scene(
    scenes
):
    _ensure_single_design_scene(
        scenes
    )

    scene = scenes[0]
    if not isinstance(
        scene,
        dict
    ):
        raise ValueError(
            "El diseño de vídeo debe producir una escena válida."
        )

    if int(
        scene.get(
            "scene",
            0
        )
    ) != 1:
        raise ValueError(
            "El diseño de vídeo debe producir scene 1."
        )


def _ensure_single_video_design_clip(
    video_clips_manifest_path
):
    manifest_path = Path(
        video_clips_manifest_path
    )
    manifest = json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        manifest,
        list
    ):
        raise ValueError(
            "El manifiesto de diseño de vídeo debe "
            "contener una lista de clips."
        )

    if len(
        manifest
    ) != 1:
        raise ValueError(
            "El diseño de vídeo debe generar exactamente "
            "un clip."
        )

    try:
        scene_number = int(
            manifest[0][
                "scene"
            ]
        )
    except (
        KeyError,
        TypeError,
        ValueError
    ) as error:
        raise ValueError(
            "El clip de diseño de vídeo debe declarar scene 1."
        ) from error

    if scene_number != 1:
        raise ValueError(
            "El clip de diseño de vídeo debe corresponder "
            "a scene 1."
        )

    output_clip = Path(
        str(
            manifest[0].get(
                "output_clip",
                ""
            )
        )
    )

    if output_clip.name != "scene_001.mp4":
        raise ValueError(
            "El clip de diseño de vídeo debe corresponder "
            "a scene_001.mp4."
        )

    if not output_clip.exists():
        raise FileNotFoundError(
            "No existe el clip de diseño de vídeo: "
            f"{output_clip}"
        )

    return output_clip


def _complete_summary(
    summary,
    stage_times,
    project,
    pipeline_start
):
    scene_count = _count_json_items(
        project.storyboard_path()
    )

    image_count = _count_json_items(
        project.images_manifest_path()
    )

    media_duration = _resolve_media_duration(
        project
    )

    summary.set_scene_count(
        scene_count
    )

    summary.set_image_count(
        image_count
    )

    summary.set_media_duration(
        media_duration
    )

    stage_order = (
        "Script",
        "Storyboard",
        "Imágenes",
        "Video I2V",
        "Voces",
        "Subtítulos",
        "Audio",
        "Vídeo"
    )

    for stage_name in stage_order:
        if stage_name in stage_times:
            summary.add_stage(
                stage_name,
                stage_times[stage_name]
            )

    measured_total = (
        time.perf_counter()
        - pipeline_start
    )

    recorded_total = (
        summary.total_time()
    )

    if measured_total > recorded_total:
        summary.set_total_time(
            measured_total
        )

    summary.print()


def _count_json_items(
    json_path
):
    json_path = Path(
        json_path
    )

    if not json_path.exists():
        return 0

    try:
        data = json.loads(
            json_path.read_text(
                encoding="utf-8"
            )
        )

    except (
        json.JSONDecodeError,
        OSError
    ):
        return 0

    if not isinstance(
        data,
        list
    ):
        return 0

    return len(
        data
    )


def _resolve_media_duration(
    project
):
    candidate_paths = (
        project.final_audio_path(),
        project.audio_path()
    )

    for media_path in candidate_paths:
        if media_path.exists():
            try:
                return MediaProbe.get_duration(
                    media_path
                )
            except (
                OSError,
                RuntimeError,
                ValueError
            ):
                return None

    return None
