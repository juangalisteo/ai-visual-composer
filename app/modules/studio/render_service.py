from dataclasses import dataclass
from pathlib import Path
import re

from app.modules.video.config.loaders.subtitle_loader import (
    SubtitleConfigLoader,
)
from app.modules.video.ffmpeg.runner import Runner
from app.modules.video.ffmpeg.graphs.layer_compositor import (
    LayerCompositor,
)
from app.modules.video.subtitles.subtitle_style_builder import (
    SubtitleStyleBuilder,
)
from app.modules.video.video_validator import VideoValidator
from app.shared.media_probe import MediaProbe
from app.shared.profile_identity import ProfileComponent, ProfileKey
from app.shared.subtitle_profile_identity import ResolvedSubtitleProfile
from app.modules.studio.light_leaks import (
    StudioLightLeakSelector,
    StudioLightLeaksPlanBuilder,
    StudioLightLeaksPlanner,
)


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
    light_leaks_enabled: bool
    light_leaks_operations: tuple


class StudioOutputPathResolver:

    def __init__(self, output_root=Path("output/studio")):
        self.output_root = Path(output_root)

    def resolve(
        self,
        video_path,
        profile_key,
        subtitle_profile,
        light_leaks_enabled=False,
    ):
        if not isinstance(profile_key, ProfileKey):
            raise TypeError("STUDIO requiere un ProfileKey explicito.")
        if profile_key.component is not ProfileComponent.STUDIO:
            raise ValueError("El output STUDIO requiere component=studio.")

        source_stem = re.sub(
            r"[^A-Za-z0-9._-]+",
            "_",
            Path(video_path).stem,
        ).strip("._") or "studio"
        style = subtitle_profile.key.style
        style = style.value if hasattr(style, "value") else str(style)
        suffix = "_light_leaks" if light_leaks_enabled else ""
        filename = (
            f"{source_stem}_studio_{profile_key.platform.value}_{style}"
            f"{suffix}.mp4"
        )
        return self.output_root / profile_key.platform.value / filename


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
        if abs(info.fps - profile.fps) > 0.01:
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
        light_leaks_selector=None,
        layer_compositor=None,
    ):
        self.runner = runner or Runner()
        self.probe = probe or MediaProbe()
        self.output_validator = output_validator or StudioOutputValidator()
        self.style_builder = style_builder or SubtitleStyleBuilder()
        self.light_leaks_selector = light_leaks_selector
        self.layer_compositor = layer_compositor or LayerCompositor()

    def render(
        self,
        video_path,
        subtitle_path,
        profile_key,
        profile,
        subtitle_profile,
        output_path,
        light_leaks_enabled=False,
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
        if output_path.exists():
            raise FileExistsError(
                f"Ya existe el output STUDIO determinista: {output_path}"
            )

        source_info = self.probe.inspect(video_path)
        render_style = SubtitleConfigLoader().load_render_style(
            subtitle_profile.render_style
        )
        if abs(render_style.offset) > 0.000001:
            raise ValueError(
                "STUDIO requiere offset=0 para preservar los timings SRT."
            )
        if bool(subtitle_profile.cue_policy.get("uppercase", False)):
            raise ValueError(
                "STUDIO Fase 2 no altera el texto SRT para aplicar uppercase."
            )
        subtitle_style = self.style_builder.build(
            subtitle_profile.render_style
        )
        light_leaks_operations = self._light_leaks_operations(
            source_info.duration,
            profile,
            light_leaks_enabled,
        )
        temporary_path = output_path.with_name(
            f"{output_path.stem}.rendering{output_path.suffix}"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._remove_temporary(temporary_path)
        command = self.build_command(
            video_path=video_path,
            subtitle_path=subtitle_path,
            output_path=temporary_path,
            source_info=source_info,
            profile=profile,
            subtitle_style=subtitle_style,
            light_leaks_operations=light_leaks_operations,
        )

        try:
            self.runner.run(command)
            generated_duration = self.output_validator.validate(
                output_path=temporary_path,
                expected_duration=source_info.duration,
                profile=profile,
            )
            self.promote(temporary_path, output_path)
        except Exception:
            self._remove_temporary(temporary_path)
            raise

        return StudioRenderResult(
            source_video_path=video_path,
            source_subtitle_path=subtitle_path,
            output_path=output_path,
            command=tuple(command),
            expected_duration=source_info.duration,
            generated_duration=generated_duration,
            source_had_audio=source_info.has_audio,
            silence_added=not source_info.has_audio,
            light_leaks_enabled=light_leaks_enabled,
            light_leaks_operations=light_leaks_operations,
        )

    def build_command(
        self,
        video_path,
        subtitle_path,
        output_path,
        source_info,
        profile,
        subtitle_style,
        light_leaks_operations=(),
    ):
        command = ["ffmpeg", "-y", "-i", str(Path(video_path))]
        for operation in light_leaks_operations:
            command.extend([
                "-stream_loop",
                "-1",
                "-i",
                str(operation.asset_path),
            ])
        if source_info.has_audio:
            audio_source = "[0:a:0]"
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
            audio_source = f"[{len(light_leaks_operations) + 1}:a:0]"

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
            "[0:v:0]" + ",".join(video_filters) + "[studio_base]"
        ]
        current_stream = "[studio_base]"
        for operation_index, operation in enumerate(light_leaks_operations):
            current_stream, _ = self.layer_compositor.apply_operation(
                filter_parts=filter_parts,
                current_stream=current_stream,
                operation={
                    "start_time": operation.start_time,
                    "end_time": operation.end_time,
                    "blend_mode": operation.blend_mode,
                    "opacity": operation.opacity,
                },
                input_index=operation.input_position + 1,
                operation_index=operation_index,
                source_prefix="studio_leak_source",
                output_prefix="studio_leak",
                width=profile.width,
                height=profile.height,
                fps=profile.fps,
            )
        filter_parts.append(
            f"{current_stream}subtitles='{escaped_subtitle}':"
            f"fontsdir='{escaped_fonts}':"
            f"force_style='{self._escape_style(subtitle_style)}'[vout]"
        )

        duration = f"{source_info.duration:.6f}"
        filter_complex = (
            ";".join(filter_parts)
            + ";"
            + audio_source
            + f"aresample={profile.audio_sample_rate},"
            + (
                "aformat="
                f"sample_rates={profile.audio_sample_rate}:"
                f"channel_layouts={self._channel_layout(profile.audio_channels)},"
            )
            + "apad,"
            + f"atrim=duration={duration},"
            + "asetpts=PTS-STARTPTS[aout]"
        )
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

    def _light_leaks_operations(self, duration, profile, enabled):
        if not enabled:
            return ()
        selector = self.light_leaks_selector or StudioLightLeakSelector()
        return StudioLightLeaksPlanBuilder(
            planner=StudioLightLeaksPlanner(profile.light_leaks),
            selector=selector,
        ).build(duration)

    def promote(self, temporary_path, output_path):
        Path(temporary_path).replace(output_path)

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
