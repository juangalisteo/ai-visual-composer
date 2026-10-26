from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
import time

from app.modules.studio.input_preparation import (
    StudioInputMode,
    StudioInputPreparationService,
)
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
from app.shared.media_probe import MediaInfo, MediaProbe
from app.shared.progress_logger import ProgressLogger
from app.modules.video.ffmpeg.runner import Runner
from app.modules.video.video_validator import VideoValidator
from app.shared.operational_error import (
    OperationalError,
    create_operational_error,
    summarize_technical_text,
)


class StudioMontageInputError(ValueError):
    """Expected user-facing error while preparing a STUDIO montage plan."""


class StudioMontageError(RuntimeError):
    """Expected user-facing error while assembling a STUDIO montage."""


@dataclass(frozen=True)
class StudioMontageClip:
    temporary_id: int
    path: Path
    original_name: str

    def __post_init__(self):
        temporary_id = int(self.temporary_id)
        path = Path(self.path)
        if temporary_id <= 0:
            raise ValueError("El ID temporal del clip debe ser positivo.")
        if not path.name:
            raise ValueError("El clip de MONTAJE DE VIDEOS debe tener nombre.")
        if self.original_name != path.name:
            raise ValueError(
                "El nombre original del clip debe coincidir con su ruta."
            )
        object.__setattr__(self, "temporary_id", temporary_id)
        object.__setattr__(self, "path", path)


@dataclass(frozen=True)
class StudioMontageCandidates:
    directory: Path
    clips: tuple[StudioMontageClip, ...]

    def __post_init__(self):
        if not self.clips:
            raise ValueError("MONTAJE DE VIDEOS requiere al menos un clip.")
        ids = tuple(clip.temporary_id for clip in self.clips)
        if ids != tuple(range(1, len(ids) + 1)):
            raise ValueError(
                "Los IDs temporales de MONTAJE DE VIDEOS deben ser consecutivos."
            )


@dataclass(frozen=True)
class StudioMontagePlan:
    profile_key: OperationalProfileKey
    transitions_enabled: bool
    clips: tuple[StudioMontageClip, ...]

    def __post_init__(self):
        if not isinstance(self.profile_key, OperationalProfileKey):
            raise TypeError("MONTAJE DE VIDEOS requiere identidad operacional explicita.")
        if self.profile_key.component is not ProfileComponent.STUDIO:
            raise ValueError("MONTAJE DE VIDEOS requiere component=studio.")
        if not isinstance(self.transitions_enabled, bool):
            raise TypeError("transitions_enabled debe ser booleano.")
        if len(self.clips) < 2:
            raise StudioMontageInputError(
                "El plan de MONTAJE DE VIDEOS requiere al menos dos clips."
            )
        if any(not isinstance(clip, StudioMontageClip) for clip in self.clips):
            raise TypeError("El plan contiene un clip de montaje no valido.")
        ids = tuple(clip.temporary_id for clip in self.clips)
        if len(set(ids)) != len(ids):
            raise StudioMontageInputError(
                "El plan de MONTAJE DE VIDEOS contiene IDs duplicados."
            )
        paths = tuple(clip.path for clip in self.clips)
        if len(set(paths)) != len(paths):
            raise StudioMontageInputError(
                "El plan de MONTAJE DE VIDEOS contiene clips duplicados."
            )
        missing = next((path for path in paths if not path.is_file()), None)
        if missing is not None:
            raise StudioMontageInputError(
                "El clip seleccionado ya no existe: "
                f"{missing}."
            )
        object.__setattr__(self, "clips", tuple(self.clips))

    @property
    def format(self):
        return self.profile_key.format

    @property
    def profile_id(self):
        return self.profile_key.profile_id


@dataclass(frozen=True)
class StudioMontagePreparedClip:
    clip: StudioMontageClip
    media_info: MediaInfo
    prepared_path: Path | None = None
    was_normalized: bool = False

    @property
    def path(self):
        return self.prepared_path or self.clip.path


@dataclass(frozen=True)
class StudioMontageContract:
    width: int
    height: int
    fps: float
    nominal_fps: float
    video_codec: str
    pixel_format: str
    sample_aspect_ratio: str
    time_base: str
    audio_codec: str
    audio_sample_rate: int
    audio_channels: int
    audio_channel_layout: str


@dataclass(frozen=True)
class StudioMontageResult:
    output_path: Path
    command: tuple[str, ...]
    expected_duration: float
    generated_duration: float
    clip_count: int
    preparation_duration: float
    montage_duration: float
    normalization_duration: float | None = None
    normalized_clip_count: int = 0
    transition_count: int = 0


@dataclass(frozen=True)
class StudioMontageRenderResult:
    montage_result: StudioMontageResult
    render_result: object

    @property
    def output_path(self):
        return self.render_result.output_path

    @property
    def generated_duration(self):
        return self.render_result.generated_duration


class StudioMontagePlanningService:

    _ORDER_TOKEN = re.compile(r"[1-9][0-9]*\Z")

    def __init__(self, input_preparation_service=None):
        self.input_preparation_service = (
            input_preparation_service
            or StudioInputPreparationService()
        )

    def discover(self, profile):
        try:
            candidates = self.input_preparation_service.discover(
                profile,
                StudioInputMode.MONTAJE_VIDEOS,
            )
        except (FileNotFoundError, NotADirectoryError, ValueError) as error:
            raise StudioMontageInputError(str(error)) from error

        clips = tuple(
            StudioMontageClip(
                temporary_id=index,
                path=path,
                original_name=path.name,
            )
            for index, path in enumerate(candidates.videos, start=1)
        )
        return StudioMontageCandidates(
            directory=candidates.directory,
            clips=clips,
        )

    def parse_order(self, value, candidates):
        if not isinstance(candidates, StudioMontageCandidates):
            raise TypeError("Los candidatos de MONTAJE DE VIDEOS no son validos.")
        text = "" if value is None else str(value).strip()
        if not text:
            raise StudioMontageInputError(
                "Introduce uno o mas IDs de clip separados por espacios."
            )

        tokens = text.split()
        if any(self._ORDER_TOKEN.fullmatch(token) is None for token in tokens):
            raise StudioMontageInputError(
                "El orden debe contener solo enteros positivos separados por espacios."
            )

        available = {
            clip.temporary_id: clip
            for clip in candidates.clips
        }
        selected = []
        seen = set()
        for token in tokens:
            temporary_id = int(token)
            clip = available.get(temporary_id)
            if clip is None:
                raise StudioMontageInputError(
                    "El ID de clip no existe en esta ejecucion: "
                    f"{temporary_id}."
                )
            if temporary_id in seen:
                raise StudioMontageInputError(
                    "No se permiten clips duplicados en MONTAJE DE VIDEOS: "
                    f"{temporary_id}."
                )
            if not clip.path.is_file():
                raise StudioMontageInputError(
                    "El clip seleccionado ya no existe: "
                    f"{clip.path}."
                )
            seen.add(temporary_id)
            selected.append(clip)
        if len(selected) < 2:
            raise StudioMontageInputError(
                "Selecciona al menos dos clips para MONTAJE DE VIDEOS."
            )
        return tuple(selected)

    def create_plan(
        self,
        profile_key,
        transitions_enabled,
        clips,
    ):
        return StudioMontagePlan(
            profile_key=profile_key,
            transitions_enabled=transitions_enabled,
            clips=tuple(clips),
        )


class StudioMontageService:
    """Build one validated principal from a fixed STUDIO montage plan."""

    _COMPATIBILITY_FIELDS = (
        ("resolucion", "width"),
        ("resolucion", "height"),
        ("FPS", "fps"),
        ("FPS nominal", "nominal_fps"),
        ("codec de video", "video_codec"),
        ("pixel format", "pixel_format"),
        ("SAR", "sample_aspect_ratio"),
        ("time_base", "time_base"),
        ("codec de audio", "audio_codec"),
        ("sample rate de audio", "audio_sample_rate"),
        ("canales de audio", "audio_channels"),
        ("layout de audio", "audio_channel_layout"),
    )
    _OUTPUT_COMPATIBILITY_FIELDS = tuple(
        field
        for field in _COMPATIBILITY_FIELDS
        if field[1] not in {"time_base", "fps"}
    )
    _PREPARED_COMPATIBILITY_FIELDS = tuple(
        field
        for field in _COMPATIBILITY_FIELDS
        if field[1] != "fps"
    )

    def __init__(self, probe=None, runner=None, validator=None):
        self.probe = probe or MediaProbe()
        self.runner = runner or Runner()
        self.validator = validator or VideoValidator()

    def compose(self, plan, output_path, profile):
        plan = self._require_executable_plan(plan)
        output_path = Path(output_path)
        if output_path.exists():
            raise FileExistsError(
                f"Ya existe el output STUDIO determinista: {output_path}"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with TemporaryDirectory(
                prefix="ai_visual_composer_studio_montage_"
            ) as directory:
                temporary_directory = Path(directory)
                (
                    prepared_clips,
                    preparation_duration,
                    normalization_duration,
                ) = self.prepare(
                    plan,
                    profile,
                    temporary_directory,
                )
                transition_count = 0
                if plan.transitions_enabled:
                    transition_count = len(prepared_clips) - 1
                    expected_duration = self._expected_transition_duration(
                        prepared_clips,
                        profile,
                    )
                    expected_info = self._profile_output_info(profile)
                else:
                    expected_duration = sum(
                        prepared.media_info.duration
                        for prepared in prepared_clips
                    )
                    expected_info = prepared_clips[0].media_info

                ProgressLogger.start(
                    "MONTANDO VIDEOS CON TRANSICIONES"
                    if plan.transitions_enabled
                    else "MONTANDO VIDEOS"
                )
                montage_start = time.perf_counter()
                temporary_path = temporary_directory / (
                    f"{output_path.stem}.montage.rendering{output_path.suffix}"
                )
                if plan.transitions_enabled:
                    filter_path = temporary_directory / "montage_transitions.ffscript"
                    try:
                        self.write_transition_filter_script(
                            filter_path,
                            prepared_clips,
                            profile,
                        )
                    except OSError as error:
                        raise StudioMontageError(
                            "No se pudo crear el graph temporal de transiciones."
                        ) from error
                    command = self.build_transition_command(
                        sources=tuple(prepared.path for prepared in prepared_clips),
                        filter_path=filter_path,
                        output_path=temporary_path,
                        profile=profile,
                    )
                else:
                    manifest_path = temporary_directory / "montage.ffconcat"
                    try:
                        self.write_concat_manifest(
                            manifest_path,
                            tuple(
                                prepared.path
                                for prepared in prepared_clips
                            ),
                        )
                    except OSError as error:
                        raise StudioMontageError(
                            "No se pudo crear el manifest temporal del montaje."
                        ) from error
                    command = self.build_concat_command(
                        manifest_path=manifest_path,
                        output_path=temporary_path,
                        movflags=profile.movflags,
                    )
                try:
                    self.runner.run(command)
                except subprocess.CalledProcessError as error:
                    metadata = {
                        "command": tuple(map(str, error.cmd or command)),
                        "returncode": error.returncode,
                        "phase": "montage_transitions" if plan.transitions_enabled else "montage_concat",
                    }
                    stderr = summarize_technical_text(error.stderr)
                    if stderr:
                        metadata["stderr_summary"] = stderr
                    raise create_operational_error(
                        family="FFMPEG",
                        user_message=(
                            "FFmpeg no pudo aplicar las transiciones del montaje."
                            if plan.transitions_enabled
                            else "FFmpeg no pudo concatenar los clips compatibles."
                        ),
                        recommended_action="Revisa los clips seleccionados y el diagnóstico del proceso.",
                        operation="STUDIO/montaje_videos",
                        resource=str(output_path),
                        technical_metadata=metadata,
                    ) from error

                try:
                    generated_duration = self._validate_output(
                        output_path=temporary_path,
                        expected_duration=expected_duration,
                        max_duration_difference=(
                            profile.max_duration_difference
                        ),
                        expected_info=expected_info,
                    )
                except OperationalError:
                    raise
                except (
                    FileNotFoundError,
                    RuntimeError,
                    subprocess.CalledProcessError,
                ) as error:
                    raise StudioMontageError(
                        "El video montado no supero la validacion. "
                        f"Comprobacion: {error}"
                    ) from error
                temporary_path.replace(output_path)
                montage_duration = time.perf_counter() - montage_start
        except StudioMontageError:
            raise
        finally:
            if output_path.exists() and output_path.stat().st_size <= 0:
                output_path.unlink()

        ProgressLogger.finish(
            "MONTAJE DE VIDEOS COMPLETADO",
            montage_duration,
        )
        return StudioMontageResult(
            output_path=output_path,
            command=tuple(command),
            expected_duration=expected_duration,
            generated_duration=generated_duration,
            clip_count=len(prepared_clips),
            preparation_duration=preparation_duration,
            montage_duration=montage_duration,
            normalization_duration=normalization_duration,
            normalized_clip_count=sum(
                prepared.was_normalized
                for prepared in prepared_clips
            ),
            transition_count=transition_count,
        )

    def prepare(self, plan, profile, temporary_directory):
        if not isinstance(plan, StudioMontagePlan):
            raise TypeError("MONTAJE DE VIDEOS requiere StudioMontagePlan.")
        if plan.transitions_enabled and len(plan.clips) < 2:
            raise StudioMontageError(
                "Se necesitan al menos 2 clips para aplicar transiciones."
            )

        ProgressLogger.start("PREPARANDO CLIPS")
        started = time.perf_counter()
        inspected = tuple(
            (clip, self._inspect_clip(clip))
            for clip in plan.clips
        )
        for clip, info in inspected:
            self._require_video_metadata(clip, info)
        if plan.transitions_enabled:
            self._require_transition_durations(inspected, profile)

        if self._can_stream_copy(inspected):
            prepared = tuple(
                StudioMontagePreparedClip(clip, info)
                for clip, info in inspected
            )
            elapsed = time.perf_counter() - started
            ProgressLogger.finish("CLIPS PREPARADOS", elapsed)
            return prepared, elapsed, None

        contract = self._build_contract(inspected, profile)
        normalizations = tuple(
            (clip, info)
            for clip, info in inspected
            if self._requires_normalization(info, contract)
        )
        preparation_duration = time.perf_counter() - started
        prepared_by_clip = {
            clip: StudioMontagePreparedClip(clip, info)
            for clip, info in inspected
            if (clip, info) not in normalizations
        }

        ProgressLogger.start("NORMALIZANDO CLIPS")
        normalization_start = time.perf_counter()
        for index, (clip, info) in enumerate(inspected, start=1):
            if (clip, info) not in normalizations:
                continue
            prepared_path = temporary_directory / (
                f"{index:04d}_{clip.path.stem}.normalized.mp4"
            )
            self._normalize_clip(
                clip=clip,
                source_info=info,
                contract=contract,
                profile=profile,
                output_path=prepared_path,
            )
            normalized_info = self._inspect_prepared_clip(clip, prepared_path)
            self._require_contract(clip, contract, normalized_info)
            prepared_by_clip[clip] = StudioMontagePreparedClip(
                clip=clip,
                media_info=normalized_info,
                prepared_path=prepared_path,
                was_normalized=True,
            )

        prepared = tuple(prepared_by_clip[clip] for clip in plan.clips)
        for prepared_clip in prepared:
            self._require_contract(
                prepared_clip.clip,
                contract,
                prepared_clip.media_info,
            )

        normalization_duration = time.perf_counter() - normalization_start
        ProgressLogger.finish("CLIPS NORMALIZADOS", normalization_duration)
        ProgressLogger.finish("CLIPS PREPARADOS", preparation_duration)
        return prepared, preparation_duration, normalization_duration

    def build_concat_command(self, manifest_path, output_path, movflags):
        return [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(Path(manifest_path)),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-c",
            "copy",
            "-movflags",
            str(movflags),
            str(Path(output_path)),
        ]

    def write_transition_filter_script(self, filter_path, prepared_clips, profile):
        script = self.build_transition_filter_script(prepared_clips, profile)
        Path(filter_path).write_text(script, encoding="utf-8")

    def build_transition_filter_script(self, prepared_clips, profile):
        prepared_clips = tuple(prepared_clips)
        if len(prepared_clips) < 2:
            raise StudioMontageError(
                "Se necesitan al menos 2 clips para aplicar transiciones."
            )

        durations = tuple(
            prepared.media_info.duration
            for prepared in prepared_clips
        )
        self._require_transition_durations(
            tuple(
                (prepared.clip, prepared.media_info)
                for prepared in prepared_clips
            ),
            profile,
        )
        transition_duration = profile.transition_duration
        video_filters = (
            f"scale={profile.width}:{profile.height}:"
            "force_original_aspect_ratio=decrease,"
            f"pad={profile.width}:{profile.height}:(ow-iw)/2:(oh-ih),"
            "setsar=1,"
            f"fps={profile.fps},"
            f"format={profile.pixel_format},"
            "setpts=PTS-STARTPTS"
        )
        audio_filters = (
            f"aresample={profile.audio_sample_rate},"
            "aformat="
            f"sample_rates={profile.audio_sample_rate}:"
            f"channel_layouts={self._channel_layout(profile.audio_channels)},"
        )
        filter_parts = []
        for index, prepared in enumerate(prepared_clips):
            interval_duration = durations[index]
            video_duration = (
                prepared.media_info.video_duration or interval_duration
            )
            visual_padding = max(0.0, interval_duration - video_duration)
            if index < len(prepared_clips) - 1:
                visual_padding += transition_duration
            padding_filter = (
                f",tpad=stop_mode=clone:stop_duration={visual_padding:.3f}"
                if visual_padding > 0
                else ""
            )
            filter_parts.append(
                f"[{index}:v:0]{video_filters}{padding_filter}[sv{index}]"
            )
            filter_parts.append(
                f"[{index}:a:0]{audio_filters}"
                f"asetpts=PTS-STARTPTS[sa{index}]"
            )

        current_video = "[sv0]"
        accumulated_duration = durations[0]
        for index, duration in enumerate(durations[1:], start=1):
            offset = accumulated_duration
            next_video = f"[sv{index}]"
            output_video = (
                "[vout]"
                if index == len(durations) - 1
                else f"[stx{index}]"
            )
            filter_parts.append(
                f"{current_video}{next_video}"
                "xfade=transition=fade:"
                f"duration={transition_duration:.3f}:"
                f"offset={offset:.6f}{output_video}"
            )
            current_video = output_video
            accumulated_duration += duration

        filter_parts.append(
            "".join(
                f"[sa{index}]"
                for index in range(len(prepared_clips))
            )
            +
            f"concat=n={len(prepared_clips)}:v=0:a=1[aout]"
        )

        return ";\n".join(filter_parts) + "\n"

    def build_transition_command(
        self,
        sources,
        filter_path,
        output_path,
        profile,
    ):
        command = ["ffmpeg", "-y"]
        for source in sources:
            command.extend(["-i", str(Path(source))])
        command.extend([
            "-filter_complex_script",
            str(Path(filter_path)),
            "-map",
            "[vout]",
            "-map",
            "[aout]",
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

    def write_concat_manifest(self, manifest_path, sources):
        lines = ["ffconcat version 1.0"]
        lines.extend(
            f"file '{self._escape_concat_path(path)}'"
            for path in sources
        )
        Path(manifest_path).write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )

    def _require_executable_plan(self, plan):
        if not isinstance(plan, StudioMontagePlan):
            raise TypeError("MONTAJE DE VIDEOS requiere StudioMontagePlan.")
        return plan

    def _require_transition_durations(self, inspected, profile):
        transition_duration = profile.transition_duration
        for clip, info in inspected:
            duration = getattr(info, "duration", None)
            if duration is None or duration <= transition_duration:
                raise StudioMontageError(
                    "El clip no tiene duracion suficiente para una "
                    f"transicion de {transition_duration:.2f} s: "
                    f"{clip.original_name}."
                )

    def _expected_transition_duration(self, prepared_clips, profile):
        return sum(
            prepared.media_info.duration
            for prepared in prepared_clips
        )

    def _profile_output_info(self, profile):
        return MediaInfo(
            duration=1.0,
            width=profile.width,
            height=profile.height,
            fps=float(profile.fps),
            nominal_fps=float(profile.fps),
            pixel_format=profile.pixel_format,
            video_codec=self._codec_name(profile.codec),
            audio_codec=self._codec_name(profile.audio_codec),
            audio_sample_rate=profile.audio_sample_rate,
            audio_channels=profile.audio_channels,
            audio_channel_layout=self._channel_layout(profile.audio_channels),
            time_base=f"1/{profile.fps}",
            sample_aspect_ratio="1:1",
        )

    def _inspect_clip(self, clip):
        try:
            return self.probe.inspect(clip.path)
        except OperationalError:
            raise
        except FileNotFoundError as error:
            raise StudioMontageError(
                f"El clip seleccionado ya no existe: {clip.path}."
            ) from error
        except (
            RuntimeError,
            OSError,
            subprocess.CalledProcessError,
            json.JSONDecodeError,
        ) as error:
            raise StudioMontageError(
                f"No se pudo inspeccionar el clip: {clip.original_name}."
            ) from error

    def _require_video_metadata(self, clip, info):
        required = (
            "duration",
            "width",
            "height",
            "fps",
            "nominal_fps",
            "video_codec",
            "pixel_format",
        )
        missing = next(
            (field for field in required if not getattr(info, field, None)),
            None,
        )
        if missing is not None:
            raise StudioMontageError(
                "Metadata de video insuficiente para montaje. "
                f"Archivo: {clip.original_name}. Campo: {missing}."
            )

    def _has_complete_audio_metadata(self, info):
        return info.has_audio and all(
            getattr(info, field, None)
            for field in (
                "audio_codec",
                "audio_sample_rate",
                "audio_channels",
                "audio_channel_layout",
            )
        )

    def _can_stream_copy(self, inspected):
        reference_clip, reference_info = inspected[0]
        try:
            self._require_complete_metadata(reference_clip, reference_info)
            for clip, info in inspected[1:]:
                self._require_complete_metadata(clip, info)
                self._require_compatible(clip, reference_info, info)
        except StudioMontageError:
            return False
        return True

    def _require_complete_metadata(self, clip, info):
        self._require_video_metadata(clip, info)
        if not self._has_complete_video_metadata(info):
            missing = next(
                field
                for field in ("sample_aspect_ratio", "time_base")
                if not getattr(info, field, None)
            )
            raise StudioMontageError(
                "Metadata de video insuficiente para montaje directo. "
                f"Archivo: {clip.original_name}. Campo: {missing}."
            )
        if not info.has_audio:
            raise StudioMontageError(
                "El clip no contiene audio para montaje directo: "
                f"{clip.original_name}."
            )
        if not self._has_complete_audio_metadata(info):
            missing = next(
                field
                for field in (
                    "audio_codec",
                    "audio_sample_rate",
                    "audio_channels",
                    "audio_channel_layout",
                )
                if not getattr(info, field, None)
            )
            raise StudioMontageError(
                "Metadata de audio insuficiente para montaje directo. "
                f"Archivo: {clip.original_name}. Campo: {missing}."
            )

    def _build_contract(self, inspected, profile):
        video_reference = next(
            (
                info
                for _, info in inspected
                if self._has_complete_video_metadata(info)
            ),
            None,
        )
        audio_reference = next(
            (
                info
                for _, info in inspected
                if self._has_complete_audio_metadata(info)
            ),
            None,
        )
        if video_reference is None:
            video_reference = self._profile_video_contract(profile)
        if audio_reference is None:
            audio_reference = self._profile_audio_contract(profile)

        return StudioMontageContract(
            width=video_reference.width,
            height=video_reference.height,
            fps=video_reference.nominal_fps,
            nominal_fps=video_reference.nominal_fps,
            video_codec=video_reference.video_codec,
            pixel_format=video_reference.pixel_format,
            sample_aspect_ratio=video_reference.sample_aspect_ratio,
            time_base=video_reference.time_base,
            audio_codec=audio_reference.audio_codec,
            audio_sample_rate=audio_reference.audio_sample_rate,
            audio_channels=audio_reference.audio_channels,
            audio_channel_layout=audio_reference.audio_channel_layout,
        )

    @staticmethod
    def _has_complete_video_metadata(info):
        return all(
            getattr(info, field, None)
            for field in (
                "width",
                "height",
                "fps",
                "nominal_fps",
                "video_codec",
                "pixel_format",
                "sample_aspect_ratio",
                "time_base",
            )
        )

    def _profile_video_contract(self, profile):
        return MediaInfo(
            duration=1.0,
            width=profile.width,
            height=profile.height,
            fps=float(profile.fps),
            nominal_fps=float(profile.fps),
            pixel_format=profile.pixel_format,
            video_codec=self._codec_name(profile.codec),
            audio_codec=None,
            audio_sample_rate=None,
            audio_channels=None,
            time_base=f"1/{profile.fps}",
            sample_aspect_ratio="1:1",
        )

    def _profile_audio_contract(self, profile):
        return MediaInfo(
            duration=1.0,
            width=1,
            height=1,
            fps=1.0,
            nominal_fps=1.0,
            pixel_format="unused",
            video_codec="unused",
            audio_codec=self._codec_name(profile.audio_codec),
            audio_sample_rate=profile.audio_sample_rate,
            audio_channels=profile.audio_channels,
            audio_channel_layout=self._channel_layout(profile.audio_channels),
        )

    def _requires_normalization(self, info, contract):
        if not self._has_complete_video_metadata(info):
            return True
        if not self._has_complete_audio_metadata(info):
            return True
        return any(
            not self._same_field(attribute, getattr(contract, attribute), getattr(info, attribute))
            for _, attribute in self._PREPARED_COMPATIBILITY_FIELDS
        )

    def _require_contract(self, clip, contract, actual):
        self._require_video_metadata(clip, actual)
        if not self._has_complete_audio_metadata(actual):
            raise StudioMontageError(
                "El clip normalizado no contiene audio completo: "
                f"{clip.original_name}."
            )
        for label, attribute in self._PREPARED_COMPATIBILITY_FIELDS:
            expected_value = getattr(contract, attribute)
            actual_value = getattr(actual, attribute)
            if not self._same_field(attribute, expected_value, actual_value):
                raise StudioMontageError(
                    "El clip preparado no cumple el contrato comun. "
                    f"Archivo: {clip.original_name}. Campo: {label}. "
                    f"Esperado: {expected_value}. Encontrado: {actual_value}."
                )

    def _normalize_clip(self, clip, source_info, contract, profile, output_path):
        command = self.build_normalize_command(
            source_path=clip.path,
            output_path=output_path,
            source_info=source_info,
            contract=contract,
            profile=profile,
        )
        try:
            self.runner.run(command)
            self.validator.validate(
                output_path=output_path,
                expected_duration=source_info.duration,
                max_duration_difference=profile.max_duration_difference,
            )
        except OperationalError:
            raise
        except subprocess.CalledProcessError as error:
            metadata = {
                "command": tuple(map(str, error.cmd or command)),
                "returncode": error.returncode,
                "phase": "montage_normalization",
            }
            stderr = summarize_technical_text(error.stderr)
            if stderr:
                metadata["stderr_summary"] = stderr
            raise create_operational_error(
                family="FFMPEG",
                user_message="FFmpeg no pudo normalizar un clip del montaje.",
                recommended_action="Revisa el clip seleccionado y el diagnóstico del proceso.",
                operation="STUDIO/montaje_videos",
                resource=str(output_path),
                technical_metadata=metadata,
            ) from error
        except (FileNotFoundError, RuntimeError) as error:
            raise StudioMontageError(
                "No se pudo normalizar el clip: "
                f"{clip.original_name}. Comprobacion: {error}"
            ) from error

    def _inspect_prepared_clip(self, clip, path):
        prepared_clip = StudioMontageClip(
            clip.temporary_id,
            Path(path),
            Path(path).name,
        )
        return self._inspect_clip(prepared_clip)

    def build_normalize_command(
        self,
        source_path,
        output_path,
        source_info,
        contract,
        profile,
    ):
        command = ["ffmpeg", "-y", "-i", str(Path(source_path))]
        if source_info.has_audio:
            audio_source = "[0:a:0]"
        else:
            command.extend([
                "-f", "lavfi", "-i",
                (
                    "anullsrc="
                    f"r={contract.audio_sample_rate}:"
                    f"cl={contract.audio_channel_layout}"
                ),
            ])
            audio_source = "[1:a:0]"

        video_time_base = self._time_base_expression(contract.time_base)
        filters = (
            "[0:v:0]"
            f"scale={contract.width}:{contract.height}:"
            "force_original_aspect_ratio=decrease,"
            f"pad={contract.width}:{contract.height}:(ow-iw)/2:(oh-ih),"
            f"setsar={contract.sample_aspect_ratio.replace(':', '/')},"
            f"fps={contract.fps:.6f},"
            f"format={contract.pixel_format},"
            f"settb={video_time_base},setpts=PTS-STARTPTS[vout];"
            f"{audio_source}"
            f"aresample={contract.audio_sample_rate},"
            "aformat="
            f"sample_rates={contract.audio_sample_rate}:"
            f"channel_layouts={contract.audio_channel_layout},"
            "apad,"
            f"atrim=duration={source_info.duration:.6f},"
            "asetpts=PTS-STARTPTS[aout]"
        )
        command.extend([
            "-filter_complex", filters,
            "-map", "[vout]", "-map", "[aout]",
            "-t", f"{source_info.duration:.6f}",
            "-c:v", self._video_encoder(contract.video_codec, profile),
            "-preset", profile.preset,
            "-crf", str(profile.crf),
            "-r", f"{contract.fps:.6f}",
            "-video_track_timescale", self._time_base_timescale(contract.time_base),
            "-pix_fmt", contract.pixel_format,
            "-c:a", self._audio_encoder(contract.audio_codec, profile),
            "-b:a", profile.audio_bitrate,
            "-ar", str(contract.audio_sample_rate),
            "-ac", str(contract.audio_channels),
            "-movflags", profile.movflags,
            str(Path(output_path)),
        ])
        return command

    def _require_compatible(
        self,
        clip,
        expected,
        actual,
        fields=None,
    ):
        for label, attribute in fields or self._COMPATIBILITY_FIELDS:
            expected_value = getattr(expected, attribute)
            actual_value = getattr(actual, attribute)
            if not self._same_field(attribute, expected_value, actual_value):
                raise StudioMontageError(
                    "Clip incompatible para montaje directo. "
                    f"Archivo: {clip.original_name}. Campo: {label}. "
                    f"Esperado: {expected_value}. Encontrado: {actual_value}."
                )

    def _validate_output(
        self,
        output_path,
        expected_duration,
        max_duration_difference,
        expected_info,
    ):
        generated_duration = self.validator.validate(
            output_path=output_path,
            expected_duration=expected_duration,
            max_duration_difference=max_duration_difference,
        )
        generated_info = self.probe.inspect(output_path)
        self._require_complete_metadata(
            StudioMontageClip(1, Path(output_path), Path(output_path).name),
            generated_info,
        )
        self._require_compatible(
            StudioMontageClip(1, Path(output_path), Path(output_path).name),
            expected_info,
            generated_info,
            fields=self._OUTPUT_COMPATIBILITY_FIELDS,
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

    @staticmethod
    def _same_field(attribute, expected_value, actual_value):
        if attribute in {"fps", "nominal_fps"}:
            return abs(float(expected_value) - float(actual_value)) <= 0.0001
        return expected_value == actual_value

    @staticmethod
    def _codec_name(encoder):
        return {
            "libx264": "h264",
            "libx265": "hevc",
        }.get(encoder, encoder)

    def _video_encoder(self, codec, profile):
        if self._codec_name(profile.codec) == codec:
            return profile.codec
        try:
            return {
                "h264": "libx264",
                "hevc": "libx265",
                "mpeg4": "mpeg4",
            }[codec]
        except KeyError as error:
            raise StudioMontageError(
                "No existe un encoder seguro para normalizar el codec "
                f"de video: {codec}."
            ) from error

    def _audio_encoder(self, codec, profile):
        if self._codec_name(profile.audio_codec) == codec:
            return profile.audio_codec
        try:
            return {
                "aac": "aac",
                "mp3": "libmp3lame",
                "opus": "libopus",
            }[codec]
        except KeyError as error:
            raise StudioMontageError(
                "No existe un encoder seguro para normalizar el codec "
                f"de audio: {codec}."
            ) from error

    @staticmethod
    def _channel_layout(channels):
        if channels == 1:
            return "mono"
        if channels == 2:
            return "stereo"
        raise StudioMontageError(
            "El contrato de audio de MONTAJE solo admite uno o dos canales."
        )

    @staticmethod
    def _time_base_expression(time_base):
        numerator, denominator = str(time_base).split("/", maxsplit=1)
        if numerator != "1" or not denominator.isdigit() or int(denominator) <= 0:
            raise StudioMontageError(
                "El time_base del contrato de montaje no es normalizable: "
                f"{time_base}."
            )
        return f"1/{denominator}"

    def _time_base_timescale(self, time_base):
        return self._time_base_expression(time_base).split("/", maxsplit=1)[1]

    @staticmethod
    def _escape_concat_path(path):
        normalized_path = Path(path).resolve().as_posix()
        return normalized_path.replace("'", "'\\''")
