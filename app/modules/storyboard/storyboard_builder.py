from pathlib import Path
import json
import time

from app.core.prompt_engine import PromptEngine
from app.managers.project_manager import ProjectManager

from app.shared.config_contract import require_text
from app.shared.config_manager import ConfigManager
from app.shared.format_catalog import FormatCatalog
from app.shared.media_probe import MediaProbe
from app.shared.progress_logger import ProgressLogger

from app.modules.storyboard.scene_segmenter import segment_scenes
from app.modules.subtitles.policies.punctuation import (
    script_tokens,
    script_word_timings,
)
from app.modules.subtitles.policies.timing import (
    SubtitleTimingResolver,
    approximate_voiced_word_timings,
)
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

    def __init__(
        self,
        config_manager=None,
        project=None,
        format_catalog=None,
    ):
        self.config_manager = config_manager
        self.project = project
        self.format_catalog = format_catalog

    def build(
        self,
        script_path=None,
        output_path=None,
        subtitle_path=None,
        voice_pauses=()
    ):
        """Divide the script into scenes and describe what each one shows.

        Scenes are cut at the end of sentences (``segment_scenes``), with the
        duration of the format (``FormatCatalog.scene_seconds``). The words
        take their times from the Whisper transcription of ``subtitle_path``;
        without it, they are spread over the audio in proportion to their
        letters, skipping the ``voice_pauses`` the voice wrote.
        """
        total_start = time.perf_counter()

        ProgressLogger.start(
            "GENERANDO STORYBOARD"
        )

        project = self.project or ProjectManager()

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

        config = self.config_manager or ConfigManager()

        ai_config = (
            config.get_ai_config()
        )

        profile = (
            config.get_profile_config()
        )

        scene_seconds = self._scene_seconds(
            profile
        )

        self._validate_inputs(
            script_path=script_path,
            audio_path=audio_path
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

        timed_words, timing_source = self._timed_words(
            script=script,
            audio_duration=audio_duration,
            subtitle_path=subtitle_path,
            voice_pauses=voice_pauses
        )

        spans = segment_scenes(
            words=timed_words,
            audio_duration=audio_duration,
            scene_seconds=scene_seconds
        )

        durations = [
            span.duration
            for span in spans
        ]

        ProgressLogger.info(
            f"Tiempos de las escenas: {timing_source}"
        )

        ProgressLogger.info(
            f"Escenas: {len(spans)} · "
            f"de {min(durations):.2f} a {max(durations):.2f} s "
            f"(objetivo {scene_seconds.target_min:g}–"
            f"{scene_seconds.target_max:g} s)"
        )

        base_scenes = [
            {
                "scene": index,
                "text": span.text
            }
            for index, span in enumerate(
                spans,
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
                expected_scene_count=len(spans)
            )
        )

        scenes = (
            StoryboardComposer()
            .compose(
                base_scenes=base_scenes,
                visual_scenes=visual_scenes,
                scene_durations=durations
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

    def _scene_seconds(
        self,
        profile
    ):
        if not isinstance(
            profile,
            dict
        ):
            raise TypeError(
                "El perfil debe ser un diccionario."
            )

        catalog = (
            self.format_catalog
            or FormatCatalog()
        )

        return catalog.scene_seconds(
            require_text(
                profile,
                "format",
                "format"
            ).lower()
        )

    @staticmethod
    def _timed_words(
        script,
        audio_duration,
        subtitle_path,
        voice_pauses
    ):
        """The script's words with their times, and where the times come from."""
        if subtitle_path is not None:
            timed_words = script_word_timings(
                script,
                SubtitleTimingResolver().resolve(
                    subtitle_path=subtitle_path
                )
            )

            if timed_words:
                return timed_words, "Whisper"

        tokens = script_tokens(
            script
        )
        words = approximate_voiced_word_timings(
            0.0,
            audio_duration,
            [text for text, _ in tokens],
            voice_pauses,
            [closes for _, closes in tokens]
        )

        return (
            tuple(
                zip(
                    words,
                    (closes for _, closes in tokens)
                )
            ),
            "estimados por letras y pausas de la voz (sin Whisper)"
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
        audio_path
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
