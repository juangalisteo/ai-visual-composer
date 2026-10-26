import json
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from app.modules.video.ffmpeg.runner import Runner
from app.modules.video.video_validator import VideoValidator


INTRO_OUTRO_DIRECTORY = Path(
    "assets/videos/intro_outro"
)
INTRO_OUTRO_POSITIONS = ("intro", "outro")


@dataclass(frozen=True)
class IntroOutroSelection:
    asset_path: Path
    position: str

    def __post_init__(self):
        asset_path = Path(self.asset_path)
        position = str(self.position).strip().lower()

        if asset_path.suffix.lower() != ".mp4":
            raise ValueError(
                "El recurso INTRO / OUTRO debe ser un archivo MP4."
            )

        if position not in {"intro", "outro"}:
            raise ValueError(
                "La posicion INTRO / OUTRO debe ser intro u outro."
            )

        object.__setattr__(self, "asset_path", asset_path)
        object.__setattr__(self, "position", position)


@dataclass(frozen=True)
class IntroOutroPlan:
    intro: IntroOutroSelection | None = None
    outro: IntroOutroSelection | None = None

    def __post_init__(self):
        if self.intro is None and self.outro is None:
            raise ValueError(
                "El plan INTRO / OUTRO debe incluir al menos un recurso."
            )
        if (
            self.intro is not None
            and (
                not isinstance(self.intro, IntroOutroSelection)
                or self.intro.position != "intro"
            )
        ):
            raise ValueError("El recurso INTRO debe ocupar la posicion intro.")
        if (
            self.outro is not None
            and (
                not isinstance(self.outro, IntroOutroSelection)
                or self.outro.position != "outro"
            )
        ):
            raise ValueError("El recurso OUTRO debe ocupar la posicion outro.")

    @property
    def selections(self):
        return tuple(
            selection
            for selection in (self.intro, self.outro)
            if selection is not None
        )


class IntroOutroCatalog:

    def __init__(
        self,
        directory=INTRO_OUTRO_DIRECTORY,
    ):
        self.directory = Path(directory)

    def discover(self, profile_format, position):
        profile_format = str(profile_format).strip()
        if (
            not profile_format
            or profile_format in {".", ".."}
            or Path(profile_format).name != profile_format
        ):
            raise ValueError(
                "El formato INTRO / OUTRO debe ser una identidad válida."
            )
        position = str(position).strip().lower()
        if position not in INTRO_OUTRO_POSITIONS:
            raise ValueError(
                "La posicion del catalogo INTRO / OUTRO debe ser intro u outro."
            )

        directory = self.directory / profile_format / position
        if not directory.is_dir():
            return ()

        return tuple(sorted(
            (
                path
                for path in directory.iterdir()
                if path.is_file()
                and path.suffix.lower() == ".mp4"
            ),
            key=lambda path: path.name.casefold(),
        ))


@dataclass(frozen=True)
class IntroOutroMediaInfo:
    duration: float
    width: int
    height: int
    fps: float
    time_base: str
    sample_aspect_ratio: str
    pixel_format: str
    video_codec: str
    audio_codec: str | None
    audio_sample_rate: int | None
    audio_channels: int | None

    @property
    def has_audio(self):
        return self.audio_codec is not None


class IntroOutroMediaProbe:

    def inspect(self, media_path):
        media_path = Path(media_path)
        if not media_path.is_file():
            raise FileNotFoundError(
                f"No existe el recurso INTRO / OUTRO: {media_path}"
            )

        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            (
                "format=duration:"
                "stream=codec_type,codec_name,width,height,"
                "avg_frame_rate,time_base,sample_aspect_ratio,"
                "pix_fmt,sample_rate,channels"
            ),
            "-of",
            "json",
            str(media_path),
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        video = next(
            (
                stream
                for stream in streams
                if stream.get("codec_type") == "video"
            ),
            None,
        )
        audio = next(
            (
                stream
                for stream in streams
                if stream.get("codec_type") == "audio"
            ),
            None,
        )

        if video is None:
            raise RuntimeError(
                "El recurso INTRO / OUTRO no contiene video."
            )

        try:
            duration = float(data["format"]["duration"])
            width = int(video["width"])
            height = int(video["height"])
            fps = float(Fraction(video["avg_frame_rate"]))
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
            raise RuntimeError(
                "FFprobe devolvio metadata incompleta para INTRO / OUTRO."
            ) from error

        if duration <= 0 or width <= 0 or height <= 0 or fps <= 0:
            raise RuntimeError(
                "El recurso INTRO / OUTRO tiene metadata no valida."
            )

        return IntroOutroMediaInfo(
            duration=duration,
            width=width,
            height=height,
            fps=fps,
            time_base=str(video.get("time_base", "")),
            sample_aspect_ratio=str(
                video.get("sample_aspect_ratio", "")
            ),
            pixel_format=str(video.get("pix_fmt", "")),
            video_codec=str(video.get("codec_name", "")),
            audio_codec=(
                str(audio.get("codec_name", ""))
                if audio is not None
                else None
            ),
            audio_sample_rate=(
                int(audio["sample_rate"])
                if audio is not None
                and audio.get("sample_rate")
                else None
            ),
            audio_channels=(
                int(audio["channels"])
                if audio is not None
                and audio.get("channels")
                else None
            ),
        )


@dataclass(frozen=True)
class IntroOutroComposition:
    output_path: Path
    command: tuple[str, ...]
    stderr: str
    expected_duration: float
    asset_was_normalized: bool
    normalized_positions: tuple[str, ...] = ()


class IntroOutroComposer:

    def __init__(
        self,
        probe=None,
        runner=None,
        validator=None,
    ):
        self.probe = probe or IntroOutroMediaProbe()
        self.runner = runner or Runner()
        self.validator = validator or VideoValidator()

    def compose(
        self,
        main_path,
        final_path,
        selection,
        config,
        expected_main_duration,
    ):
        main_path = Path(main_path)
        final_path = Path(final_path)
        selections = self._require_selections(selection)

        main_info = self.probe.inspect(main_path)
        self._require_main_audio(main_info)
        asset_infos = tuple(
            (item, self.probe.inspect(item.asset_path))
            for item in selections
        )

        normalized_paths = {
            item.position: self._normalized_path(
                final_path,
                item.position if len(selections) > 1 else None,
            )
            for item in selections
        }
        composition_path = self._composition_path(final_path)
        concat_list_path = self._concat_list_path(final_path)
        for normalized_path in normalized_paths.values():
            self._remove_temporary(normalized_path)
        self._remove_temporary(composition_path)
        self._remove_temporary(concat_list_path)

        prepared_assets = {}
        normalized_positions = []

        try:
            for item, asset_info in asset_infos:
                prepared_asset_path = item.asset_path
                if self.requires_normalization(
                    asset_info=asset_info,
                    main_info=main_info,
                    config=config,
                ):
                    normalized_path = normalized_paths[item.position]
                    normalize_command = self.build_normalize_command(
                        source_path=item.asset_path,
                        output_path=normalized_path,
                        source_info=asset_info,
                        target_info=main_info,
                        config=config,
                    )
                    self.runner.run(normalize_command)
                    self.validator.validate(
                        output_path=normalized_path,
                        expected_duration=asset_info.duration,
                        max_duration_difference=(
                            self._max_duration_difference(config)
                        ),
                    )
                    normalized_info = self.probe.inspect(normalized_path)
                    if self.requires_normalization(
                        asset_info=normalized_info,
                        main_info=main_info,
                        config=config,
                    ):
                        raise RuntimeError(
                            "El recurso INTRO / OUTRO normalizado no cumple "
                            "el contrato tecnico del video final."
                        )
                    prepared_asset_path = normalized_path
                    normalized_positions.append(item.position)
                prepared_assets[item.position] = prepared_asset_path

            sources = self.ordered_plan_sources(
                main_path=main_path,
                prepared_assets=prepared_assets,
                selections=selections,
            )
            self.write_concat_list(
                concat_list_path,
                sources,
            )
            concat_command = self.build_concat_command(
                concat_list_path=concat_list_path,
                output_path=composition_path,
                config=config,
            )
            result = self.runner.run(concat_command)
            expected_duration = float(expected_main_duration) + sum(
                asset_info.duration
                for _, asset_info in asset_infos
            )
            self.validator.validate(
                output_path=composition_path,
                expected_duration=expected_duration,
                max_duration_difference=(
                    self._max_duration_difference(config)
                ),
            )
        except Exception:
            self._remove_temporary(composition_path)
            raise
        finally:
            for normalized_path in normalized_paths.values():
                self._remove_temporary(normalized_path)
            self._remove_temporary(concat_list_path)

        return IntroOutroComposition(
            output_path=composition_path,
            command=tuple(concat_command),
            stderr=str(getattr(result, "stderr", "") or ""),
            expected_duration=expected_duration,
            asset_was_normalized=bool(normalized_positions),
            normalized_positions=tuple(normalized_positions),
        )

    def requires_normalization(
        self,
        asset_info,
        main_info,
        config,
    ):
        expected_video_codec = self._codec_name(config.codec)
        return any((
            asset_info.width != main_info.width,
            asset_info.height != main_info.height,
            abs(asset_info.fps - main_info.fps) > 0.01,
            asset_info.time_base != main_info.time_base,
            asset_info.sample_aspect_ratio != main_info.sample_aspect_ratio,
            asset_info.pixel_format != config.pixel_format,
            asset_info.video_codec != expected_video_codec,
            not asset_info.has_audio,
            asset_info.audio_codec != main_info.audio_codec,
            asset_info.audio_sample_rate != main_info.audio_sample_rate,
            asset_info.audio_channels != main_info.audio_channels,
        ))

    def build_normalize_command(
        self,
        source_path,
        output_path,
        source_info,
        target_info,
        config,
    ):
        source_path = Path(source_path)
        output_path = Path(output_path)
        audio_sample_rate = target_info.audio_sample_rate
        audio_channels = target_info.audio_channels
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(source_path),
        ]

        if source_info.has_audio:
            audio_source = "[0:a:0]"
        else:
            command.extend([
                "-f",
                "lavfi",
                "-i",
                (
                    "anullsrc="
                    f"r={audio_sample_rate}:"
                    f"cl={self._channel_layout(audio_channels)}"
                ),
            ])
            audio_source = "[1:a:0]"

        filter_complex = (
            "[0:v:0]"
            f"scale={target_info.width}:{target_info.height}:"
            "force_original_aspect_ratio=decrease,"
            f"pad={target_info.width}:{target_info.height}:"
            "(ow-iw)/2:(oh-ih)/2,"
            "setsar=1,"
            f"fps={config.fps},"
            f"format={config.pixel_format},"
            "settb=AVTB,setpts=PTS-STARTPTS[vout];"
            f"{audio_source}"
            f"aresample={audio_sample_rate},"
            f"aformat=channel_layouts={self._channel_layout(audio_channels)},"
            "apad,"
            f"atrim=duration={source_info.duration:.6f},"
            "asetpts=PTS-STARTPTS[aout]"
        )
        command.extend([
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-t",
            f"{source_info.duration:.6f}",
            "-c:v",
            config.codec,
            "-preset",
            config.preset,
            "-crf",
            str(config.crf),
            "-r",
            str(config.fps),
            "-pix_fmt",
            config.pixel_format,
            "-c:a",
            config.audio_codec,
            "-b:a",
            config.audio_bitrate,
            "-ar",
            str(audio_sample_rate),
            "-ac",
            str(audio_channels),
            "-movflags",
            config.movflags,
            str(output_path),
        ])
        return command

    def build_concat_command(
        self,
        concat_list_path,
        output_path,
        config,
    ):
        return [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(Path(concat_list_path)),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-c",
            "copy",
            "-movflags",
            config.movflags,
            str(Path(output_path)),
        ]

    def ordered_sources(
        self,
        main_path,
        asset_path,
        selection,
    ):
        main_path = Path(main_path)
        asset_path = Path(asset_path)
        if selection.position == "intro":
            return (asset_path, main_path)
        return (main_path, asset_path)

    def ordered_plan_sources(
        self,
        main_path,
        prepared_assets,
        selections,
    ):
        sources = []
        if any(item.position == "intro" for item in selections):
            sources.append(Path(prepared_assets["intro"]))
        sources.append(Path(main_path))
        if any(item.position == "outro" for item in selections):
            sources.append(Path(prepared_assets["outro"]))
        return tuple(sources)

    def write_concat_list(
        self,
        concat_list_path,
        sources,
    ):
        lines = ["ffconcat version 1.0"]
        lines.extend(
            f"file '{self._escape_concat_path(path)}'"
            for path in sources
        )
        Path(concat_list_path).write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )

    def _require_selection(self, selection):
        if not isinstance(selection, IntroOutroSelection):
            raise TypeError(
                "La seleccion INTRO / OUTRO no es valida."
            )
        if not selection.asset_path.is_file():
            raise FileNotFoundError(
                "No existe el recurso INTRO / OUTRO seleccionado: "
                f"{selection.asset_path}"
            )
        return selection

    def _require_selections(self, selection):
        if isinstance(selection, IntroOutroSelection):
            return (self._require_selection(selection),)
        if not isinstance(selection, IntroOutroPlan):
            raise TypeError("La seleccion INTRO / OUTRO no es valida.")
        return tuple(
            self._require_selection(item)
            for item in selection.selections
        )

    def _require_main_audio(self, main_info):
        if (
            not main_info.has_audio
            or main_info.audio_sample_rate is None
            or main_info.audio_channels is None
        ):
            raise RuntimeError(
                "El video principal no contiene audio compatible."
            )

    def _codec_name(self, encoder):
        aliases = {
            "libx264": "h264",
            "libx265": "hevc",
        }
        return aliases.get(encoder, encoder)

    def _channel_layout(self, channels):
        if channels == 1:
            return "mono"
        if channels == 2:
            return "stereo"
        raise RuntimeError(
            "El audio principal debe ser mono o estereo para INTRO / OUTRO."
        )

    def _normalized_path(self, final_path, position=None):
        position_suffix = f".{position}" if position else ""
        return final_path.with_name(
            f"{final_path.stem}.intro-outro{position_suffix}.normalized.mp4"
        )

    @staticmethod
    def _max_duration_difference(config):
        validation = getattr(config, "validation", None)
        if validation is not None:
            return validation.max_duration_difference
        return config.max_duration_difference

    def _composition_path(self, final_path):
        return final_path.with_name(
            f"{final_path.stem}.intro-outro.rendering.mp4"
        )

    def _concat_list_path(self, final_path):
        return final_path.with_name(
            f"{final_path.stem}.intro-outro.concat.txt"
        )

    def _escape_concat_path(self, path):
        normalized_path = Path(path).resolve().as_posix()
        return normalized_path.replace("'", "'\\''")

    def _remove_temporary(self, path):
        path = Path(path)
        if path.exists():
            path.unlink()
