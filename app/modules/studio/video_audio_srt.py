from dataclasses import dataclass
from pathlib import Path
import subprocess

from app.modules.video.ffmpeg.runner import Runner
from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.modules.video.subtitles.subtitle_style_builder import SubtitleStyleBuilder
from app.modules.video.subtitles.subtitle_render_preparation import (
    SubtitleRenderPreparation,
)
from app.modules.video.subtitles.ass_subtitle_builder import (
    SubtitleRenderBackend,
)
from app.modules.studio.input_preparation import StudioInputPreparationService
from app.modules.studio.render_service import StudioOutputValidator
from app.shared.media_probe import MediaProbe
from app.shared.operational_error import (
    OperationalError,
    create_operational_error,
    summarize_technical_text,
)


class StudioVideoAudioSrtInputError(ValueError):
    pass


class StudioVideoAudioSrtError(RuntimeError):
    pass


@dataclass(frozen=True)
class StudioVideoAudioSrtPlan:
    video_path: Path
    audio_path: Path
    subtitle_path: Path | None = None
    audio_tail_mode: str = "silence"
    music_path: Path | None = None
    video_duration: float | None = None
    audio_duration: float | None = None


@dataclass(frozen=True)
class StudioVideoAudioSrtCandidates:
    directory: Path
    videos: tuple[Path, ...]
    audios: tuple[Path, ...]
    subtitles: tuple[Path, ...]


class StudioVideoAudioSrtInputService:
    audio_extensions = (".mp3", ".wav", ".m4a", ".aac", ".flac")

    def __init__(self, directory=Path("input/studio/video_audio_srt")):
        self.directory = Path(directory)

    def discover(self, subtitles=False):
        videos = self._candidates((".mp4",))
        audios = self._candidates(self.audio_extensions)
        subtitle_paths = (
            self._valid_subtitle_candidates(self._candidates((".srt",)))
            if subtitles
            else ()
        )
        self._require_candidates(videos, "MP4")
        self._require_candidates(audios, "audio")
        if subtitles:
            self._require_candidates(subtitle_paths, "SRT")
        return StudioVideoAudioSrtCandidates(
            directory=self.directory,
            videos=videos,
            audios=audios,
            subtitles=subtitle_paths,
        )

    def create_plan(
        self,
        subtitles=False,
        video_path=None,
        audio_path=None,
        subtitle_path=None,
    ):
        candidates = self.discover(subtitles)
        plan = StudioVideoAudioSrtPlan(
            self._selected_candidate(candidates.videos, video_path, "MP4"),
            self._selected_candidate(candidates.audios, audio_path, "audio"),
            (
                self._selected_candidate(
                    candidates.subtitles,
                    subtitle_path,
                    "SRT",
                )
                if subtitles
                else None
            ),
        )
        return plan

    def _candidates(self, extensions):
        return StudioInputPreparationService._candidates(
            self.directory,
            extensions,
        )

    @staticmethod
    def _valid_subtitle_candidates(candidates):
        valid = []
        errors = []
        for candidate in candidates:
            try:
                StudioInputPreparationService._validate_subtitle(
                    candidate
                )
            except ValueError as error:
                errors.append(str(error))
            else:
                valid.append(candidate)
        if candidates and not valid:
            raise StudioVideoAudioSrtInputError(errors[0])
        return tuple(valid)

    def _require_candidates(self, candidates, label):
        if not candidates:
            raise StudioVideoAudioSrtInputError(
                f"No se encontro ningun archivo {label} en {self.directory}."
            )

    def _selected_candidate(self, candidates, selected_path, label):
        if selected_path is not None:
            selected_path = Path(selected_path)
            if selected_path not in candidates:
                raise StudioVideoAudioSrtInputError(
                    "La seleccion VIDEO + AUDIO SRT de "
                    f"{label} no es valida: {selected_path}."
                )
            return selected_path
        if len(candidates) > 1:
            names = ", ".join(path.name for path in candidates)
            raise StudioVideoAudioSrtInputError(
                "VIDEO + AUDIO SRT requiere seleccionar un archivo "
                f"{label}. Se encontraron: {names}."
            )
        return candidates[0]


class StudioVideoAudioSrtService:
    """Renderiza el vídeo completo con el audio nuevo como pista de salida."""

    FONTS_DIRECTORY = Path("assets/fonts")

    def __init__(self, probe=None, runner=None, validator=None, style_builder=None):
        self.probe = probe or MediaProbe()
        self.runner = runner or Runner()
        self.validator = validator or StudioOutputValidator(
            probe=self.probe,
            runner=self.runner,
        )
        self.style_builder = style_builder or SubtitleStyleBuilder()

    def render(self, plan, output_path, profile, subtitle_profile=None):
        if not isinstance(plan, StudioVideoAudioSrtPlan):
            raise TypeError("VIDEO + AUDIO SRT requiere un plan estructurado.")
        if not plan.video_path.is_file():
            raise FileNotFoundError(
                f"No existe el MP4 VIDEO + AUDIO SRT: {plan.video_path}"
            )
        if not plan.audio_path.is_file():
            raise FileNotFoundError(
                f"No existe el audio VIDEO + AUDIO SRT: {plan.audio_path}"
            )
        video = self.probe.inspect(plan.video_path)
        video_duration = video.duration
        if video_duration <= 0:
            raise StudioVideoAudioSrtError(
                "La duracion del video debe ser positiva."
            )
        try:
            audio_duration = self.probe.get_duration(plan.audio_path)
        except Exception as error:
            raise StudioVideoAudioSrtError("No se pudo detectar la duracion del audio nuevo.") from error
        if audio_duration <= 0:
            raise StudioVideoAudioSrtError("La duracion del audio nuevo debe ser positiva.")
        music_path = self._validated_music_path(plan, audio_duration, video_duration)
        output_path = Path(output_path)
        if output_path.exists():
            raise FileExistsError(
                f"Ya existe el output STUDIO determinista: {output_path}"
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_name(f"{output_path.stem}.rendering.mp4")
        prepared_subtitle = self._prepare_subtitles(
            plan.subtitle_path,
            subtitle_profile,
            profile,
        )
        filters = [
            f"[0:v:0]scale={profile.width}:{profile.height}:"
            f"force_original_aspect_ratio=decrease,pad={profile.width}:"
            f"{profile.height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={profile.fps},"
            f"format={profile.pixel_format},trim=duration={video_duration:.6f},"
            "setpts=PTS-STARTPTS[studio_base]"
        ]
        if prepared_subtitle is None:
            filters.append("[studio_base]null[vout]")
        elif prepared_subtitle.backend is SubtitleRenderBackend.DYNAMIC:
            filters.append(
                "[studio_base]ass="
                f"'{self._escape_filter_path(prepared_subtitle.path)}':"
                f"fontsdir='{self._escape_filter_path(self.FONTS_DIRECTORY)}'[vout]"
            )
        else:
            filters.append(
                "[studio_base]subtitles="
                f"'{self._escape_filter_path(prepared_subtitle.path)}':"
                f"fontsdir='{self._escape_filter_path(self.FONTS_DIRECTORY)}':"
                f"force_style='{self._escape_style(prepared_subtitle.force_style)}'[vout]"
            )
        command = ["ffmpeg", "-y", "-i", str(plan.video_path), "-i", str(plan.audio_path)]
        if audio_duration < video_duration and music_path is not None:
            command.extend(["-stream_loop", "-1", "-i", str(music_path)])
            remaining_duration = video_duration - audio_duration
            filters.extend([
                f"[1:a:0]aresample={profile.audio_sample_rate},"
                f"atrim=duration={audio_duration:.6f},asetpts=PTS-STARTPTS[new_audio]",
                f"[2:a:0]volume={profile.music.volume:.6f},"
                f"aresample={profile.audio_sample_rate},"
                f"atrim=duration={remaining_duration:.6f},asetpts=PTS-STARTPTS,"
                f"alimiter=limit={profile.music.limiter_limit:.6f}:"
                "level=false:latency=true[tail_music]",
                "[new_audio][tail_music]concat=n=2:v=0:a=1[aout]",
            ])
        elif audio_duration < video_duration:
            filters.append(
                f"[1:a:0]aresample={profile.audio_sample_rate},apad,"
                f"atrim=duration={video_duration:.6f},asetpts=PTS-STARTPTS[aout]"
            )
        else:
            filters.append(
                f"[1:a:0]aresample={profile.audio_sample_rate},"
                f"atrim=duration={video_duration:.6f},asetpts=PTS-STARTPTS[aout]"
            )
        command.extend(["-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]", "-t", f"{video_duration:.6f}", "-c:v", profile.codec, "-preset", profile.preset, "-crf", str(profile.crf), "-pix_fmt", profile.pixel_format, "-c:a", profile.audio_codec, "-b:a", profile.audio_bitrate, "-ar", str(profile.audio_sample_rate), "-ac", str(profile.audio_channels), "-movflags", profile.movflags, str(temporary)])
        try:
            self.runner.run(command)
            duration = self.validator.validate(
                temporary,
                video_duration,
                profile,
            )
            temporary.replace(output_path)
        except Exception as error:
            if temporary.exists():
                temporary.unlink()
            if isinstance(error, OperationalError):
                raise
            if isinstance(error, subprocess.CalledProcessError):
                metadata = {
                    "command": tuple(map(str, error.cmd or command)),
                    "returncode": error.returncode,
                    "phase": "video_audio_srt_render",
                }
                stderr = summarize_technical_text(error.stderr)
                if stderr:
                    metadata["stderr_summary"] = stderr
                raise create_operational_error(
                    family="FFMPEG",
                    user_message="FFmpeg no pudo generar VIDEO + AUDIO SRT.",
                    recommended_action="Revisa los archivos de entrada y el diagnóstico del proceso.",
                    operation="STUDIO/video_audio_srt",
                    resource=str(output_path),
                    technical_metadata=metadata,
                ) from error
            raise
        finally:
            if prepared_subtitle is not None:
                prepared_subtitle.cleanup()
        return output_path, duration, tuple(command)

    @staticmethod
    def _validated_music_path(plan, audio_duration, video_duration):
        if audio_duration >= video_duration:
            return None
        if plan.audio_tail_mode not in {"silence", "music"}:
            raise ValueError(
                "El tratamiento final de audio VIDEO + AUDIO SRT no es valido."
            )
        if plan.audio_tail_mode == "silence":
            return None
        if plan.music_path is None:
            raise ValueError(
                "COMPLETAR CON MUSICA requiere una pista musical seleccionada."
            )
        music_path = Path(plan.music_path)
        if not music_path.is_file():
            raise FileNotFoundError(
                f"No existe la musica VIDEO + AUDIO SRT: {music_path}"
            )
        return music_path

    def _prepare_subtitles(self, subtitle_path, subtitle_profile, profile):
        if subtitle_path is None:
            if subtitle_profile is not None:
                raise ValueError(
                    "VIDEO + AUDIO SRT sin subtitulos no admite perfil de subtitulos."
                )
            return None
        if subtitle_profile is None:
            raise ValueError(
                "VIDEO + AUDIO SRT con SRT requiere perfil de subtitulos STUDIO."
            )
        if not Path(subtitle_path).is_file():
            raise FileNotFoundError(
                f"No existe el SRT VIDEO + AUDIO SRT: {subtitle_path}"
            )
        if not self.FONTS_DIRECTORY.is_dir():
            raise FileNotFoundError(
                f"No existe la carpeta de fuentes: {self.FONTS_DIRECTORY}"
            )
        render_style = SubtitleConfigLoader().load_render_style(
            subtitle_profile.render_style
        )
        if abs(render_style.offset) > 0.000001:
            raise ValueError(
                "STUDIO requiere offset=0 para preservar los timings SRT."
            )
        return SubtitleRenderPreparation(
            style_builder=self.style_builder
        ).prepare(
            subtitle_path=subtitle_path,
            render_style=render_style,
            width=profile.width,
            height=profile.height,
            style_source=subtitle_profile.render_style,
            cue_policy=getattr(subtitle_profile, "cue_policy", None),
        )

    @staticmethod
    def _escape_filter_path(path):
        return (
            Path(path).resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
        )

    @staticmethod
    def _escape_style(style):
        return str(style).replace("'", r"\'")
