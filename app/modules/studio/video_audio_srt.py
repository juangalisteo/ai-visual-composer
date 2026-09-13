from dataclasses import dataclass
from pathlib import Path
import subprocess

from app.modules.video.ffmpeg.runner import Runner
from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.modules.video.subtitles.subtitle_style_builder import SubtitleStyleBuilder
from app.modules.studio.input_preparation import StudioInputPreparationService
from app.modules.studio.render_service import StudioOutputValidator
from app.shared.media_probe import MediaProbe


class StudioVideoAudioSrtInputError(ValueError):
    pass


class StudioVideoAudioSrtError(RuntimeError):
    pass


@dataclass(frozen=True)
class StudioVideoAudioSrtPlan:
    video_path: Path
    audio_path: Path
    subtitle_path: Path | None = None


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
                "VIDEO + AUDIO SRT requiere seleccionar exactamente un "
                f"archivo {label}. Se encontraron: {names}."
            )
        return candidates[0]


class StudioVideoAudioSrtService:
    """Renderiza el vídeo ajustado con el audio nuevo como única autoridad."""

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
        try:
            audio_duration = self.probe.get_duration(plan.audio_path)
        except Exception as error:
            raise StudioVideoAudioSrtError("No se pudo detectar la duracion del audio nuevo.") from error
        if audio_duration <= 0:
            raise StudioVideoAudioSrtError("La duracion del audio nuevo debe ser positiva.")
        output_path = Path(output_path)
        if output_path.exists():
            raise FileExistsError(
                f"Ya existe el output STUDIO determinista: {output_path}"
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_name(f"{output_path.stem}.rendering.mp4")
        subtitle_style = self._subtitle_style(plan.subtitle_path, subtitle_profile)
        filters = [
            f"[0:v:0]scale={profile.width}:{profile.height}:"
            f"force_original_aspect_ratio=decrease,pad={profile.width}:"
            f"{profile.height}:(ow-iw)/2:(oh-ih),setsar=1,fps={profile.fps},"
            f"format={profile.pixel_format},trim=duration={audio_duration:.6f},"
            "setpts=PTS-STARTPTS[studio_base]"
        ]
        if plan.subtitle_path is None:
            filters.append("[studio_base]null[vout]")
        else:
            filters.append(
                "[studio_base]subtitles="
                f"'{self._escape_filter_path(plan.subtitle_path)}':"
                f"fontsdir='{self._escape_filter_path(self.FONTS_DIRECTORY)}':"
                f"force_style='{self._escape_style(subtitle_style)}'[vout]"
            )
        command = ["ffmpeg", "-y"]
        if audio_duration > video.duration:
            command.extend(["-stream_loop", "-1"])
        command.extend(["-i", str(plan.video_path), "-i", str(plan.audio_path)])
        filters.append(
            f"[1:a:0]aresample={profile.audio_sample_rate},apad,"
            f"atrim=duration={audio_duration:.6f},asetpts=PTS-STARTPTS[aout]"
        )
        command.extend(["-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]", "-t", f"{audio_duration:.6f}", "-c:v", profile.codec, "-preset", profile.preset, "-crf", str(profile.crf), "-pix_fmt", profile.pixel_format, "-c:a", profile.audio_codec, "-b:a", profile.audio_bitrate, "-ar", str(profile.audio_sample_rate), "-ac", str(profile.audio_channels), "-movflags", profile.movflags, str(temporary)])
        try:
            self.runner.run(command)
            duration = self.validator.validate(
                temporary,
                audio_duration,
                profile,
            )
            temporary.replace(output_path)
        except Exception as error:
            if temporary.exists():
                temporary.unlink()
            if isinstance(error, subprocess.CalledProcessError):
                raise StudioVideoAudioSrtError(
                    "FFmpeg no pudo generar VIDEO + AUDIO SRT."
                ) from error
            raise
        return output_path, duration, tuple(command)

    def _subtitle_style(self, subtitle_path, subtitle_profile):
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
        return self.style_builder.build(subtitle_profile.render_style)

    @staticmethod
    def _escape_filter_path(path):
        return (
            Path(path).resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
        )

    @staticmethod
    def _escape_style(style):
        return str(style).replace("'", r"\'")
