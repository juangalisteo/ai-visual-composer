from pathlib import Path
import json
import math
import time

from app.core.prompt_engine import PromptEngine
from app.managers.project_manager import ProjectManager

from app.shared.config_manager import ConfigManager
from app.shared.media_probe import MediaProbe
from app.shared.progress_logger import ProgressLogger

from app.modules.storyboard.scene_splitter import SceneSplitter
from app.modules.storyboard.storyboard_ai_builder import (
    StoryboardAIBuilder
)
from app.modules.storyboard.storyboard_composer import (
    StoryboardComposer
)
from app.modules.storyboard.storyboard_response_parser import (
    StoryboardResponseParser
)
from app.modules.storyboard.storyboard_validator import (
    StoryboardValidator
)


class StoryboardBuilder:

    def build(
        self,
        script_path=None,
        output_path=None,
        target_scene_duration=None
    ):
        total_start = time.perf_counter()

        ProgressLogger.start(
            "GENERANDO STORYBOARD"
        )

        project = ProjectManager()

        script_path = Path(
            script_path
            or project.script_path()
        )

        output_path = Path(
            output_path
            or project.storyboard_path()
        )

        audio_path = self._resolve_audio_path(
            project
        )

        config = ConfigManager()

        ai_config = (
            config.get_ai_config()
        )

        profile = (
            config.get_profile_config()
        )

        resolved_scene_duration = (
            self._resolve_scene_duration(
                profile=profile,
                target_scene_duration=target_scene_duration
            )
        )

        self._validate_inputs(
            script_path=script_path,
            audio_path=audio_path,
            target_scene_duration=resolved_scene_duration
        )

        script = script_path.read_text(
            encoding="utf-8"
        ).strip()

        if not script:
            raise ValueError(
                "El guion está vacío."
            )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        audio_duration = (
            MediaProbe.get_duration(
                audio_path
            )
        )

        requested_scene_count = max(
            1,
            math.ceil(
                audio_duration
                / resolved_scene_duration
            )
        )

        ProgressLogger.info(
            f"Duración objetivo por imagen: "
            f"{resolved_scene_duration:.2f} segundos"
        )

        ProgressLogger.info(
            f"Escenas solicitadas: "
            f"{requested_scene_count}"
        )

        scene_texts = SceneSplitter().split(
            text=script,
            scene_count=requested_scene_count
        )

        if not scene_texts:
            raise ValueError(
                "No se pudieron generar "
                "escenas desde el guion."
            )

        scene_count = len(
            scene_texts
        )

        scene_duration = (
            audio_duration
            / scene_count
        )

        ProgressLogger.info(
            f"Escenas generadas: "
            f"{scene_count}"
        )

        ProgressLogger.info(
            f"Duración real por escena: "
            f"{scene_duration:.2f} segundos"
        )

        base_scenes = [
            {
                "scene": index,
                "text": scene_text
            }
            for index, scene_text in enumerate(
                scene_texts,
                start=1
            )
        ]

        prompt = (
            PromptEngine()
            .build_storyboard_prompt(
                scenes=base_scenes,
                profile=profile
            )
        )

        raw_response = (
            StoryboardAIBuilder(
                ai_config
            )
            .build(
                prompt
            )
        )

        parsed_response = (
            StoryboardResponseParser()
            .parse(
                raw_response
            )
        )

        visual_scenes = (
            StoryboardValidator()
            .validate(
                visual_scenes=parsed_response,
                expected_scene_count=scene_count
            )
        )

        scenes = (
            StoryboardComposer()
            .compose(
                base_scenes=base_scenes,
                visual_scenes=visual_scenes,
                scene_duration=scene_duration
            )
        )

        output_path.write_text(
            json.dumps(
                scenes,
                ensure_ascii=False,
                indent=4
            ),
            encoding="utf-8"
        )

        self._validate_output(
            output_path
        )

        total_elapsed = (
            time.perf_counter()
            - total_start
        )

        ProgressLogger.finish(
            "Finalizado",
            total_elapsed
        )

        return output_path

    def _resolve_scene_duration(
        self,
        profile,
        target_scene_duration
    ):
        if target_scene_duration is not None:
            return float(
                target_scene_duration
            )

        if not isinstance(
            profile,
            dict
        ):
            raise TypeError(
                "El perfil debe ser un diccionario."
            )

        video_style = profile.get(
            "video_style",
            {}
        )

        if not isinstance(
            video_style,
            dict
        ):
            raise TypeError(
                "La configuración video_style "
                "debe ser un diccionario."
            )

        storyboard_config = video_style.get(
            "storyboard",
            {}
        )

        if not isinstance(
            storyboard_config,
            dict
        ):
            raise TypeError(
                "La configuración "
                "video_style.storyboard "
                "debe ser un diccionario."
            )

        return float(
            storyboard_config.get(
                "seconds_per_image",
                10.0
            )
        )

    def _resolve_audio_path(
        self,
        project
    ):
        final_audio_path = (
            project.final_audio_path()
        )

        if final_audio_path.exists():
            return final_audio_path

        voice_audio_path = (
            project.audio_path()
        )

        if voice_audio_path.exists():
            return voice_audio_path

        raise FileNotFoundError(
            "No existe audio_final.mp3 "
            "ni voz.mp3 para calcular "
            "el storyboard."
        )

    def _validate_inputs(
        self,
        script_path,
        audio_path,
        target_scene_duration
    ):
        if not script_path.exists():
            raise FileNotFoundError(
                f"No existe el guion: "
                f"{script_path}"
            )

        if not audio_path.exists():
            raise FileNotFoundError(
                f"No existe el audio: "
                f"{audio_path}"
            )

        if target_scene_duration <= 0:
            raise ValueError(
                "seconds_per_image debe "
                "ser superior a 0."
            )

    def _validate_output(
        self,
        output_path
    ):
        if not output_path.exists():
            raise FileNotFoundError(
                "El storyboard terminó, "
                "pero no se encontró el archivo: "
                f"{output_path}"
            )

        if output_path.stat().st_size <= 0:
            raise RuntimeError(
                "El storyboard generado está vacío."
            )