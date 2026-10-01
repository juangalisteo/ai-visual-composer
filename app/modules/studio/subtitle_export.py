from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import shutil
import time

from app.modules.studio.input_preparation import (
    StudioInputPreparationService,
)
from app.modules.subtitles.io.external_media_subtitles import (
    ExternalMediaSubtitlePreparationService,
)
from app.modules.subtitles.modes.registry import CueModelRegistry
from app.modules.subtitles.pipeline.cue_transformer import SubtitleCueTransformer
from app.shared.progress_logger import ProgressLogger


class StudioSubtitleExportMode(str, Enum):
    TRANSCRIBIR = "transcribir"
    CONVERTIR = "convertir"


class StudioSubtitleExportInputError(ValueError):
    """Expected user-facing error while selecting an EXPORTAR SRT source."""


def coerce_studio_subtitle_export_mode(value):
    if isinstance(value, StudioSubtitleExportMode):
        return value
    try:
        return StudioSubtitleExportMode(str(value).strip().lower())
    except ValueError as error:
        raise ValueError(
            "Modo EXPORTAR SRT no soportado: "
            f"{value}."
        ) from error


@dataclass(frozen=True)
class StudioSubtitleExportCandidates:
    directory: Path
    sources: tuple[Path, ...]
    mode: StudioSubtitleExportMode


@dataclass(frozen=True)
class StudioSubtitleExportPlan:
    mode: StudioSubtitleExportMode
    source_path: Path


@dataclass(frozen=True)
class StudioSubtitleExportResult:
    mode: StudioSubtitleExportMode
    source_path: Path
    output_path: Path
    subtitle_style: str | None
    operation_duration: float


class StudioSubtitleExportInputService:

    TRANSCRIBIR_EXTENSIONS = (".mp4", ".mp3")
    CONVERTIR_EXTENSIONS = (".srt",)

    def __init__(self, input_directory=Path("input/studio")):
        self.input_directory = Path(input_directory)

    def discover(self, export_mode):
        export_mode = coerce_studio_subtitle_export_mode(export_mode)
        directory = self._require_directory(export_mode)
        extensions = (
            self.TRANSCRIBIR_EXTENSIONS
            if export_mode is StudioSubtitleExportMode.TRANSCRIBIR
            else self.CONVERTIR_EXTENSIONS
        )
        sources = StudioInputPreparationService._candidates(
            directory,
            extensions,
        )
        if export_mode is StudioSubtitleExportMode.CONVERTIR:
            sources = self._valid_subtitle_candidates(sources)
        self._require_candidates(sources, export_mode, directory)
        return StudioSubtitleExportCandidates(
            directory=directory,
            sources=sources,
            mode=export_mode,
        )

    def prepare(self, export_mode, source_path=None):
        candidates = self.discover(export_mode)
        source_path = self._selected_candidate(
            candidates.sources,
            source_path,
            candidates.mode,
        )
        return StudioSubtitleExportPlan(
            mode=candidates.mode,
            source_path=source_path,
        )

    def _require_directory(self, export_mode):
        directory = (
            self.input_directory
            / "exportar_srt"
            / export_mode.value
        )
        if not directory.exists():
            raise StudioSubtitleExportInputError(
                "No existe la carpeta de entrada EXPORTAR SRT: "
                f"{directory}"
            )
        if not directory.is_dir():
            raise StudioSubtitleExportInputError(
                "La entrada EXPORTAR SRT debe ser una carpeta: "
                f"{directory}"
            )
        return directory

    @staticmethod
    def _valid_subtitle_candidates(candidates):
        valid = []
        errors = []
        for candidate in candidates:
            try:
                StudioInputPreparationService._validate_subtitle(candidate)
            except ValueError as error:
                errors.append(str(error))
            else:
                valid.append(candidate)
        if candidates and not valid:
            raise StudioSubtitleExportInputError(errors[0])
        return tuple(valid)

    @staticmethod
    def _require_candidates(candidates, export_mode, directory):
        if candidates:
            return
        label = (
            "MP4 o MP3"
            if export_mode is StudioSubtitleExportMode.TRANSCRIBIR
            else "SRT"
        )
        raise StudioSubtitleExportInputError(
            f"No se encontro ningun archivo {label} en:\n"
            f"{directory}\n\n"
            "Anade un archivo valido e intentalo de nuevo."
        )

    @staticmethod
    def _selected_candidate(candidates, selected_path, export_mode):
        if selected_path is not None:
            selected_path = Path(selected_path)
            if selected_path not in candidates:
                raise StudioSubtitleExportInputError(
                    "La seleccion EXPORTAR SRT no es valida: "
                    f"{selected_path}."
                )
            return selected_path
        if len(candidates) > 1:
            names = ", ".join(path.name for path in candidates)
            raise StudioSubtitleExportInputError(
                "Entrada EXPORTAR SRT ambigua para "
                f"{export_mode.value}: {names}."
            )
        return candidates[0]


class StudioSubtitleExportService:

    def __init__(self, subtitle_preparation_service=None):
        self.subtitle_preparation_service = (
            subtitle_preparation_service
            or ExternalMediaSubtitlePreparationService()
        )

    def export(
        self,
        plan,
        project,
        profile=None,
        subtitle_profile=None,
    ):
        if not isinstance(plan, StudioSubtitleExportPlan):
            raise TypeError(
                "EXPORTAR SRT requiere un plan STUDIO estructurado."
            )
        if plan.mode is StudioSubtitleExportMode.TRANSCRIBIR:
            return self._transcribe(plan, project)
        return self._convert(plan, project, profile, subtitle_profile)

    def _transcribe(self, plan, project):
        output_path = self._canonical_output_path(project)
        start = time.perf_counter()
        ProgressLogger.start("TRANSCRIBIENDO")
        from tempfile import TemporaryDirectory
        with TemporaryDirectory(
            prefix="ai_visual_composer_studio_exportar_srt_"
        ) as directory:
            prepared = self.subtitle_preparation_service.prepare(
                media_path=plan.source_path,
                working_directory=directory,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(prepared.subtitle_path, output_path)
        elapsed = time.perf_counter() - start
        ProgressLogger.finish("SRT GENERADO", elapsed)
        return StudioSubtitleExportResult(
            mode=plan.mode,
            source_path=plan.source_path,
            output_path=output_path,
            subtitle_style=None,
            operation_duration=elapsed,
        )

    def _convert(self, plan, project, profile, subtitle_profile):
        if profile is None or subtitle_profile is None:
            raise ValueError(
                "CONVERTIR requiere perfil STUDIO y perfil de subtitulos."
            )
        mode = CueModelRegistry.mode_from(subtitle_profile.cue_policy)
        output_path = project.subtitles_dir() / (
            f"{project.project_name}_{mode}.srt"
        )
        start = time.perf_counter()
        ProgressLogger.start("CONVIRTIENDO SRT")
        source_content = plan.source_path.read_text(encoding="utf-8")
        transformed = SubtitleCueTransformer(
            subtitle_profile=subtitle_profile,
            render_fps=profile.fps,
        ).transform(source_content)
        if not transformed.strip():
            raise ValueError("La conversion no produjo cues utilizables.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = output_path.with_suffix(".srt.tmp")
        temporary_path.write_text(transformed, encoding="utf-8")
        temporary_path.replace(output_path)
        elapsed = time.perf_counter() - start
        ProgressLogger.finish("SRT CONVERTIDO", elapsed)
        return StudioSubtitleExportResult(
            mode=plan.mode,
            source_path=plan.source_path,
            output_path=output_path,
            subtitle_style=mode,
            operation_duration=elapsed,
        )

    @staticmethod
    def _canonical_output_path(project):
        return project.subtitles_dir() / f"{project.project_name}.srt"
