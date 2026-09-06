from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from app.modules.subtitles.cue_transformer import SubtitleCueTransformer

from app.modules.video.config.loaders.subtitle_loader import (
    SubtitleConfigLoader,
)
from app.modules.video.ffmpeg.runner import Runner
from app.modules.video.subtitles.subtitle_style_builder import (
    SubtitleStyleBuilder,
)
from app.modules.video.video_validator import VideoValidator
from app.modules.video.intro_outro import (
    IntroOutroComposer,
    IntroOutroPlan,
    IntroOutroSelection,
)
from app.shared.media_probe import MediaProbe
from app.shared.profile_identity import ProfileComponent, ProfileKey
from app.shared.subtitle_profile_identity import ResolvedSubtitleProfile
from app.managers.project_manager import ProjectManager


@dataclass(frozen=True)
class StudioRenderResult:
    source_video_path: Path
    source_subtitle_path: Path
    output_path: Path
    command: tuple[str, ...]
    expected_duration: float
    generated_duration: float
    source_had_audio: bool
    silence_added: bool
    music_path: Path | None
    intro_outro_selection: IntroOutroPlan | None = None
    intro_outro_command: tuple[str, ...] = ()
    normalized_intro_outro_positions: tuple[str, ...] = ()


@dataclass(frozen=True)
class StudioInputLayout:
    source_video: int
    source_audio: int
    music: int | None


class StudioOutputPathResolver:

    def __init__(self, project=None):
        self.project = project

    def resolve(
        self,
        profile_key,
        project=None,
    ):
        if not isinstance(profile_key, ProfileKey):
            raise TypeError("STUDIO requiere un ProfileKey explicito.")
        if profile_key.component is not ProfileComponent.STUDIO:
            raise ValueError("El output STUDIO requiere component=studio.")

        project = project or self.project or ProjectManager()
        return project.video_path()

    @staticmethod
    def _intro_outro_plan(selection):
        if isinstance(selection, IntroOutroPlan):
            return selection
        if isinstance(selection, IntroOutroSelection):
            if selection.position == "intro":
                return IntroOutroPlan(intro=selection)
            return IntroOutroPlan(outro=selection)
        raise TypeError("La seleccion INTRO / OUTRO de STUDIO no es valida.")


class StudioOutputValidator:

    def __init__(self, probe=None, validator=None, runner=None):
        self.probe = probe or MediaProbe()
        self.validator = validator or VideoValidator()
        self.runner = runner or Runner()

    def validate(self, output_path, expected_duration, profile):
        generated_duration = self.validator.validate(
            output_path=output_path,
            expected_duration=expected_duration,
            max_duration_difference=profile.max_duration_difference,
        )
        info = self.probe.inspect(output_path)
        expected_codec = {
            "libx264": "h264",
            "libx265": "hevc",
        }.get(profile.codec, profile.codec)
        mismatches = []
        if (info.width, info.height) != (profile.width, profile.height):
            mismatches.append("resolucion")
        effective_fps = (
            info.nominal_fps
            if info.nominal_fps is not None
            else info.fps
        )
        if abs(effective_fps - profile.fps) > 0.01:
            mismatches.append("fps")
        if info.video_codec != expected_codec:
            mismatches.append("codec de video")
        if info.pixel_format != profile.pixel_format:
            mismatches.append("pixel format")
        if not info.has_audio:
            mismatches.append("stream de audio")
        if info.audio_codec != profile.audio_codec:
            mismatches.append("codec de audio")
        if info.audio_sample_rate != profile.audio_sample_rate:
            mismatches.append("sample rate de audio")
        if info.audio_channels != profile.audio_channels:
            mismatches.append("canales de audio")
        if mismatches:
            raise RuntimeError(
                "El output STUDIO incumple el contrato: "
                + ", ".join(mismatches)
                + "."
            )

        self.runner.run([
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(Path(output_path)),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-f",
            "null",
            "-",
        ])
        return generated_duration


class StudioRenderService:

    FONTS_DIRECTORY = Path("assets/fonts")

    def __init__(
        self,
        runner=None,
        probe=None,
        output_validator=None,
        style_builder=None,
        intro_outro_composer=None,
    ):
        self.runner = runner or Runner()
        self.probe = probe or MediaProbe()
        self.output_validator = output_validator or StudioOutputValidator()
        self.style_builder = style_builder or SubtitleStyleBuilder()
        self.intro_outro_composer = (
            intro_outro_composer or IntroOutroComposer()
        )

    def render(
        self,
        video_path,
        subtitle_path,
        profile_key,
        profile,
        subtitle_profile,
        output_path,
        music_path=None,
        intro_outro_selection=None,
        subtitle_timing=None,
    ):
        self._require_contract(
            video_path,
            subtitle_path,
            profile_key,
            subtitle_profile,
        )
        video_path = Path(video_path)
        subtitle_path = Path(subtitle_path)
        output_path = Path(output_path)
        music_path = Path(music_path) if music_path is not None else None
        if music_path is not None and not music_path.is_file():
            raise FileNotFoundError(
                f"No existe la pista musical STUDIO: {music_path}"
            )
        if output_path.exists():
            raise FileExistsError(
                f"Ya existe el output STUDIO determinista: {output_path}"
            )
        principal_path = (
            self._principal_path(output_path)
            if intro_outro_selection is not None
            else output_path
        )
        if principal_path != output_path and principal_path.exists():
            raise FileExistsError(
                f"Ya existe el principal STUDIO temporal: {principal_path}"
            )

        source_info = self.probe.inspect(video_path)
        render_style = SubtitleConfigLoader().load_render_style(
            subtitle_profile.render_style
        )
        if abs(render_style.offset) > 0.000001:
            raise ValueError(
                "STUDIO requiere offset=0 para preservar los timings SRT."
            )
        subtitle_style = self.style_builder.build(
            subtitle_profile.render_style
        )
        temporary_path = principal_path.with_name(
            f"{principal_path.stem}.rendering{principal_path.suffix}"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._remove_temporary(temporary_path)
        subtitle_directory = TemporaryDirectory(
            prefix="ai_visual_composer_studio_subtitles_"
        )
        try:
            render_subtitle_path = self._write_render_subtitle(
                source_path=subtitle_path,
                target_directory=subtitle_directory.name,
                subtitle_profile=subtitle_profile,
                render_fps=profile.fps,
                timing=subtitle_timing,
            )
            command = self.build_command(
                video_path=video_path,
                subtitle_path=render_subtitle_path,
                output_path=temporary_path,
                source_info=source_info,
                profile=profile,
                subtitle_style=subtitle_style,
                music_path=music_path,
            )
            self.runner.run(command)
            generated_duration = self.output_validator.validate(
                output_path=temporary_path,
                expected_duration=source_info.duration,
                profile=profile,
            )
            self.promote(temporary_path, principal_path)
        except Exception:
            self._remove_temporary(temporary_path)
            raise
        finally:
            subtitle_directory.cleanup()

        final_output_path = principal_path
        final_expected_duration = source_info.duration
        final_generated_duration = generated_duration
        intro_outro_command = ()
        normalized_positions = ()
        normalized_selection = None
        if intro_outro_selection is not None:
            normalized_selection = StudioOutputPathResolver._intro_outro_plan(
                intro_outro_selection
            )
            composition = self.intro_outro_composer.compose(
                main_path=principal_path,
                final_path=output_path,
                selection=normalized_selection,
                config=profile,
                expected_main_duration=generated_duration,
            )
            try:
                final_generated_duration = self.output_validator.validate(
                    output_path=composition.output_path,
                    expected_duration=composition.expected_duration,
                    profile=profile,
                )
                self.promote(composition.output_path, output_path)
            except Exception:
                self._remove_temporary(composition.output_path)
                raise
            principal_path.unlink()
            final_output_path = output_path
            final_expected_duration = composition.expected_duration
            intro_outro_command = composition.command
            normalized_positions = composition.normalized_positions

        return StudioRenderResult(
            source_video_path=video_path,
            source_subtitle_path=subtitle_path,
            output_path=final_output_path,
            command=tuple(command),
            expected_duration=final_expected_duration,
            generated_duration=final_generated_duration,
            source_had_audio=source_info.has_audio,
            silence_added=not source_info.has_audio,
            music_path=music_path,
            intro_outro_selection=normalized_selection,
            intro_outro_command=intro_outro_command,
            normalized_intro_outro_positions=normalized_positions,
        )

    def build_command(
        self,
        video_path,
        subtitle_path,
        output_path,
        source_info,
        profile,
        subtitle_style,
        music_path=None,
    ):
        command, inputs = self._build_inputs(
            video_path=video_path,
            source_info=source_info,
            profile=profile,
            music_path=music_path,
        )
        audio_source = f"[{inputs.source_audio}:a:0]"

        escaped_subtitle = self._escape_filter_path(subtitle_path)
        escaped_fonts = self._escape_filter_path(self.FONTS_DIRECTORY)
        video_filters = [
            (
                f"scale={profile.width}:{profile.height}:"
                "force_original_aspect_ratio=decrease"
            ),
            (
                f"pad={profile.width}:{profile.height}:"
                "(ow-iw)/2:(oh-ih)/2"
            ),
            "setsar=1",
            f"fps={profile.fps}",
            f"format={profile.pixel_format}",
            "setpts=PTS-STARTPTS",
        ]
        filter_parts = [
            f"[{inputs.source_video}:v:0]"
            + ",".join(video_filters)
            + "[studio_base]"
        ]
        filter_parts.append(
            f"[studio_base]subtitles='{escaped_subtitle}':"
            f"fontsdir='{escaped_fonts}':"
            f"force_style='{self._escape_style(subtitle_style)}'[vout]"
        )

        duration = f"{source_info.duration:.6f}"
        audio_format = (
            f"aresample={profile.audio_sample_rate},"
            "aformat="
            f"sample_rates={profile.audio_sample_rate}:"
            f"channel_layouts={self._channel_layout(profile.audio_channels)},"
            "apad,"
            f"atrim=duration={duration},"
            "asetpts=PTS-STARTPTS"
        )
        if inputs.music is None:
            audio_graph = audio_source + audio_format + "[aout]"
        else:
            audio_graph = (
                audio_source
                + audio_format
                + "[studio_source_audio];"
                + f"[{inputs.music}:a:0]"
                + f"volume={profile.music.volume:.6f},"
                + audio_format
                + "[studio_music];"
                + "[studio_source_audio][studio_music]"
                + "amix=inputs=2:duration=first:"
                + "dropout_transition=0:normalize=0,"
                + f"alimiter=limit={profile.music.limiter_limit:.6f}:"
                + "level=false:latency=true[aout]"
            )
        filter_complex = ";".join(filter_parts) + ";" + audio_graph
        command.extend([
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-t",
            duration,
            "-c:v",
            profile.codec,
            "-preset",
            profile.preset,
            "-crf",
            str(profile.crf),
            "-r",
            str(profile.fps),
            "-pix_fmt",
            profile.pixel_format,
            "-c:a",
            profile.audio_codec,
            "-b:a",
            profile.audio_bitrate,
            "-ar",
            str(profile.audio_sample_rate),
            "-ac",
            str(profile.audio_channels),
            "-movflags",
            profile.movflags,
            str(Path(output_path)),
        ])
        return command

    def _build_inputs(
        self,
        video_path,
        source_info,
        profile,
        music_path,
    ):
        command = ["ffmpeg", "-y", "-i", str(Path(video_path))]
        next_index = 1
        if source_info.has_audio:
            source_audio_index = 0
        else:
            command.extend([
                "-f",
                "lavfi",
                "-i",
                (
                    "anullsrc="
                    f"r={profile.audio_sample_rate}:"
                    f"cl={self._channel_layout(profile.audio_channels)}"
                ),
            ])
            source_audio_index = next_index
            next_index += 1

        music_index = None
        if music_path is not None:
            command.extend([
                "-stream_loop",
                "-1",
                "-i",
                str(Path(music_path)),
            ])
            music_index = next_index

        return command, StudioInputLayout(
            source_video=0,
            source_audio=source_audio_index,
            music=music_index,
        )

    def promote(self, temporary_path, output_path):
        Path(temporary_path).replace(output_path)

    @staticmethod
    def _write_render_subtitle(
        source_path,
        target_directory,
        subtitle_profile,
        render_fps,
        timing=None,
    ):
        source_path = Path(source_path)
        transformed = SubtitleCueTransformer(
            subtitle_profile=subtitle_profile,
            render_fps=render_fps,
        ).transform(
            source_path.read_text(encoding="utf-8"),
            timing=timing,
        )
        if not transformed.strip():
            raise ValueError(
                "El SRT de STUDIO no produjo cues renderizables."
            )

        target_path = Path(target_directory) / "studio_render.srt"
        target_path.write_text(transformed, encoding="utf-8")
        return target_path

    def _require_contract(
        self,
        video_path,
        subtitle_path,
        profile_key,
        subtitle_profile,
    ):
        if not isinstance(profile_key, ProfileKey):
            raise TypeError("StudioRenderService requiere ProfileKey.")
        if profile_key.component is not ProfileComponent.STUDIO:
            raise ValueError("StudioRenderService requiere component=studio.")
        if not isinstance(subtitle_profile, ResolvedSubtitleProfile):
            raise TypeError(
                "StudioRenderService requiere ResolvedSubtitleProfile."
            )
        if subtitle_profile.key.component is not ProfileComponent.STUDIO:
            raise ValueError(
                "El perfil de subtitulos debe pertenecer a STUDIO."
            )
        if (
            subtitle_profile.key.platform is not profile_key.platform
        ):
            raise ValueError(
                "El perfil principal y el de subtitulos deben compartir plataforma."
            )
        if not Path(video_path).is_file():
            raise FileNotFoundError(f"No existe el MP4 STUDIO: {video_path}")
        if not Path(subtitle_path).is_file():
            raise FileNotFoundError(f"No existe el SRT STUDIO: {subtitle_path}")
        if not self.FONTS_DIRECTORY.is_dir():
            raise FileNotFoundError(
                f"No existe la carpeta de fuentes: {self.FONTS_DIRECTORY}"
            )

    @staticmethod
    def _escape_filter_path(path):
        return (
            Path(path)
            .resolve()
            .as_posix()
            .replace(":", r"\:")
            .replace("'", r"\'")
        )

    @staticmethod
    def _escape_style(style):
        return str(style).replace("'", r"\'")

    @staticmethod
    def _channel_layout(channels):
        if channels == 1:
            return "mono"
        if channels == 2:
            return "stereo"
        raise ValueError("STUDIO solo admite audio mono o estereo.")

    @staticmethod
    def _remove_temporary(path):
        path = Path(path)
        if path.exists():
            path.unlink()

    @staticmethod
    def _principal_path(output_path):
        output_path = Path(output_path)
        return output_path.with_name(
            f"{output_path.stem}.studio-principal{output_path.suffix}"
        )
