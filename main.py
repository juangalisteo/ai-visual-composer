import os
import time
import traceback
from pathlib import Path

from app.cli.error_presenter import ErrorPresenter
from app.controllers.run_controller import RunController
from app.core.start import iniciar
from app.managers.output_manager import (
    OutputManager,
    OutputResetBlockedError,
)
from app.managers.pipeline_summary import PipelineSummary
from app.modules.studio import (
    StudioMontageError,
    StudioMontageInputError,
    StudioSubtitleExportInputError,
    StudioSubtitleExportMode,
    StudioIntroOutroInputError,
    StudioVideoAudioSrtError,
    StudioVideoAudioSrtInputError,
    adapt_legacy_studio_error,
)
from app.shared.error_context import ErrorContext, ErrorSeverity, ExitKind
from app.shared.operational_error import OperationalError
from app.shared.profile_identity import ProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


def main():
    """Run the CLI with one final boundary for shared incident contracts."""
    try:
        return _run_main()
    except KeyboardInterrupt:
        _present_cancellation(
            "La operacion fue interrumpida por el usuario.",
            operation="Ejecucion principal",
        )
        return 130
    except EOFError:
        _present_cancellation(
            "La entrada de terminal finalizo antes de completar la seleccion.",
            operation="Seleccion de opciones",
        )
        return 0
    except OperationalError as error:
        _present_incident(ErrorPresenter().present_operational_error(error))
        if error.context.exit_kind is ExitKind.CANCELLATION:
            return 0
        return 1
    except Exception as error:
        _present_unexpected_error(error)
        return 1


def _run_main():

    controller = RunController()
    try:
        options = controller.run()
    except (
        StudioMontageInputError,
        StudioSubtitleExportInputError,
        StudioIntroOutroInputError,
        StudioVideoAudioSrtInputError,
    ) as error:
        print(f"ERROR: {error}")
        return 1

    os.environ["MC_PROFILE_COMPONENT"] = options.get(
        "profile_component",
        ""
    )
    os.environ["MC_PROFILE_PLATFORM"] = options.get(
        "profile_platform",
        ""
    )
    os.environ["MC_PROFILE_ID"] = options.get(
        "profile_id",
        ""
    )
    os.environ["MC_PROFILE_FAMILY"] = options.get(
        "profile_family",
        "system",
    )
    os.environ["MC_VOICE_CONFIG"] = options["voice_config"]
    os.environ["MC_MUSIC_CATEGORY"] = options["music_category"] or ""
    if "overlays_mode" in options:
        os.environ["MC_OVERLAYS_MODE"] = options["overlays_mode"]
    else:
        os.environ.pop("MC_OVERLAYS_MODE", None)
    os.environ["MC_PROJECT_NAME"] = options["project_name"]
    os.environ["MC_VISUAL_PIPELINE"] = options["visual_pipeline"]
    os.environ["MC_SCRIPT_SOURCE"] = options["script_source"]
    os.environ["MC_DESIGN_TARGET"] = options.get("design_target", "")
    os.environ["MC_PIPELINE_MODE"] = options["pipeline_mode"]

    is_studio_montage = (
        options.get("pipeline_mode") == "studio"
        and options.get("studio_input_mode") == "montaje_videos"
    )
    is_studio_intro_outro = (
        options.get("pipeline_mode") == "studio"
        and options.get("studio_input_mode") == "intro_outro"
    )
    is_studio_subtitle_export = (
        options.get("pipeline_mode") == "studio"
        and options.get("studio_input_mode") == "exportar_srt"
    )
    if options["clear_output"]:
        try:
            OutputManager().reset()
        except OutputResetBlockedError as error:
            print(f"ERROR: {error}")
            return 1

    start_options = {}
    if options.get("subtitle_profile_key") is not None:
        start_options["subtitle_profile_key"] = options[
            "subtitle_profile_key"
        ]
    elif options["subtitle_config"]:
        start_options["subtitle_style"] = options["subtitle_config"]
    intro_outro_selection = options.get(
        "intro_outro_selection"
    )
    if intro_outro_selection is not None:
        start_options["intro_outro_selection"] = (
            intro_outro_selection
        )
    if options.get("pipeline_mode") == "studio":
        start_options["studio_music_path"] = options.get(
            "studio_music_path"
        )
        start_options["studio_input_mode"] = options.get(
            "studio_input_mode"
        )
        if options.get("studio_video_path") is not None:
            start_options["studio_video_path"] = options[
                "studio_video_path"
            ]
        if options.get("studio_subtitle_path") is not None:
            start_options["studio_subtitle_path"] = options[
                "studio_subtitle_path"
            ]
        if options.get("studio_montage_plan") is not None:
            start_options["studio_montage_plan"] = options[
                "studio_montage_plan"
            ]
        if options.get("studio_video_audio_srt_plan") is not None:
            start_options["studio_video_audio_srt_plan"] = options["studio_video_audio_srt_plan"]
        if options.get("studio_intro_outro_plan") is not None:
            start_options["studio_intro_outro_plan"] = options[
                "studio_intro_outro_plan"
            ]
        if options.get("studio_subtitle_export_plan") is not None:
            start_options["studio_subtitle_export_plan"] = options[
                "studio_subtitle_export_plan"
            ]
        if options.get("studio_subtitle_original"):
            start_options["studio_subtitle_original"] = True

    studio_start = time.perf_counter()
    try:
        result = iniciar(**start_options)
    except (
        StudioMontageError,
        StudioVideoAudioSrtError,
        ValueError,
    ) as error:
        if (
            isinstance(error, ValueError)
            and options.get("pipeline_mode") != "studio"
        ):
            raise
        raise adapt_legacy_studio_error(
            error,
            mode=options.get("studio_input_mode"),
        ) from error

    if options.get("pipeline_mode") == "studio":
        if is_studio_intro_outro:
            _print_studio_intro_outro_summary(
                options, result, time.perf_counter() - studio_start,
            )
        elif is_studio_montage:
            _print_studio_montage_summary(
                options,
                result,
                time.perf_counter() - studio_start,
            )
        elif is_studio_subtitle_export:
            _print_studio_subtitle_export_summary(
                options,
                result,
                time.perf_counter() - studio_start,
            )
        else:
            _print_studio_summary(
                options,
                result,
                time.perf_counter() - studio_start,
            )

    return 0


def _present_unexpected_error(error):
    """Present an INTERNAL incident while retaining evidence in its context."""
    context = ErrorContext(
        family="INTERNAL",
        severity=ErrorSeverity.FATAL_INTERNAL,
        user_message="Se produjo un error interno inesperado.",
        exit_kind=ExitKind.INTERNAL_ERROR,
        operation="Ejecución principal",
        technical_metadata={
            "exception_type": type(error).__name__,
            "traceback": "".join(
                traceback.format_exception(error)
            ),
        },
    )
    _present_incident(ErrorPresenter().present_context(context))


def _present_cancellation(user_message, *, operation):
    """Present a terminal cancellation without treating it as INTERNAL."""
    _present_incident(
        ErrorPresenter().present_context(
            ErrorContext(
                family="CANCELLATION",
                severity=ErrorSeverity.RECOVERABLE,
                user_message=user_message,
                exit_kind=ExitKind.CANCELLATION,
                operation=operation,
            )
        )
    )


def _present_incident(presentation):
    """Write already-resolved presentation content at the terminal boundary."""
    print(presentation.text)


def _subtitle_display_name(options):
    selection = options.get("subtitle_config")
    if not selection:
        return ""

    labels = {
        "single_line": "Línea única",
        "word_by_word": "Palabra por palabra",
    }
    try:
        selected_key = options.get("subtitle_profile_key")
        if selected_key is not None:
            return SubtitleProfileResolver().load(selected_key).display_name
        profile_key = ProfileKey(
            component=options["profile_component"],
            platform=options["profile_platform"],
            profile_id=options["profile_id"],
            family=options.get("profile_family", "system"),
        )
        resolver = SubtitleProfileResolver()
        return resolver.load(
            resolver.adapt_legacy_selection(profile_key, selection)
        ).display_name
    except (KeyError, FileNotFoundError, TypeError, ValueError):
        return labels.get(selection, selection)


def _print_studio_summary(options, result, elapsed_seconds):
    summary = PipelineSummary(
        options["project_name"],
        include_visual_metrics=False,
    )
    input_labels = {
        "srt_video": "SRT + VIDEO",
        "video": "VIDEO",
        "video_audio_srt": "VIDEO + AUDIO SRT",
    }
    plan = options.get("intro_outro_selection")
    generated_subtitle_path = getattr(
        result,
        "generated_subtitle_path",
        None,
    )
    base_subtitle_path = getattr(
        result,
        "base_subtitle_path",
        None,
    )

    summary.add_detail(
        "Perfil / plataforma",
        (
            f"{options['profile_id']} / "
            f"{options['profile_platform'].title()}"
        ),
    )
    summary.add_detail(
        "Entrada",
        input_labels[options["studio_input_mode"]],
    )
    if options["studio_input_mode"] == "video_audio_srt":
        video_audio_plan = options["studio_video_audio_srt_plan"]
        subtitles_enabled = options["subtitle_config"] is not None
        summary.add_detail("Proyecto", options["project_name"])
        summary.add_detail("Video fuente", video_audio_plan.video_path)
        summary.add_detail("Audio nuevo", video_audio_plan.audio_path)
        summary.add_detail("Subtítulos", "Sí" if subtitles_enabled else "No")
        if subtitles_enabled:
            summary.add_detail(
                "Perfil de subtítulos",
                _subtitle_display_name(options),
            )
        video_duration = getattr(video_audio_plan, "video_duration", None)
        audio_duration = getattr(video_audio_plan, "audio_duration", None)
        final_duration = getattr(result, "generated_duration", None)
        if video_duration is not None:
            summary.add_detail("Duración vídeo", f"{video_duration:.3f} s")
        if audio_duration is not None:
            summary.add_detail(
                "Duración audio original",
                f"{audio_duration:.3f} s",
            )
        if final_duration is not None:
            summary.add_detail("Duración final", f"{final_duration:.3f} s")
        if (
            video_duration is not None
            and audio_duration is not None
            and audio_duration > video_duration
        ):
            summary.add_detail("Tratamiento audio", "Recortado al vídeo")
        elif audio_duration is not None and video_duration is not None and audio_duration < video_duration:
            summary.add_detail(
                "Tratamiento audio",
                (
                    "Audio + música final"
                    if video_audio_plan.audio_tail_mode == "music"
                    else "Audio + silencio final"
                ),
            )
    else:
        summary.add_detail(
            "Estilo de subtítulos",
            (
                "ORIGINAL"
                if options.get("studio_subtitle_original")
                else _subtitle_display_name(options)
            ),
        )
        summary.add_detail(
            "Música",
            "Sí" if options.get("studio_music_path") else "No",
        )
        summary.add_detail(
            "Intro",
            "Sí" if plan is not None and plan.intro is not None else "No",
        )
        summary.add_detail(
            "Outro",
            "Sí" if plan is not None and plan.outro is not None else "No",
        )
    if isinstance(base_subtitle_path, (str, Path)):
        summary.add_detail("SRT base", base_subtitle_path)
    if isinstance(generated_subtitle_path, (str, Path)):
        summary.add_detail("SRT generado", generated_subtitle_path)
    summary.add_detail("Video final", result.output_path)
    summary.add_detail(
        "Estado final",
        (
            "VIDEO + AUDIO SRT COMPLETADO"
            if options["studio_input_mode"] == "video_audio_srt"
            else "STUDIO COMPLETADO"
        ),
    )
    summary.set_media_duration(
        getattr(result, "generated_duration", None)
    )
    subtitle_preparation_duration = _recorded_stage_duration(
        result,
        "subtitle_preparation_duration",
    )
    render_duration = _recorded_stage_duration(
        result,
        "render_duration",
    )
    intro_outro_duration = _recorded_stage_duration(
        result,
        "intro_outro_duration",
    )
    if subtitle_preparation_duration is not None:
        summary.add_stage(
            "Preparación subtítulos",
            subtitle_preparation_duration,
        )
    if render_duration is not None:
        summary.add_stage("Render STUDIO", render_duration)
    if intro_outro_duration is not None:
        summary.add_stage("Intro / Outro", intro_outro_duration)
    summary.set_total_time(elapsed_seconds)
    summary.print()


def _print_studio_intro_outro_summary(options, result, elapsed_seconds):
    summary = PipelineSummary(options["project_name"], include_visual_metrics=False)
    plan = options["studio_intro_outro_plan"]
    summary.add_detail(
        "Perfil / plataforma",
        f"{options['profile_id']} / {options['profile_platform'].title()}",
    )
    summary.add_detail("Entrada", "INTRO / OUTRO")
    summary.add_detail("Video fuente", plan.source_path)
    summary.add_detail("Intro", "Si" if plan.intro_outro_plan.intro else "No")
    summary.add_detail("Outro", "Si" if plan.intro_outro_plan.outro else "No")
    summary.add_detail("Video final", result.output_path)
    summary.add_detail("Estado final", "INTRO / OUTRO COMPLETADO")
    summary.set_media_duration(result.generated_duration)
    for label, attribute in (("Preparacion video", "render_duration"), ("Intro / Outro", "intro_outro_duration")):
        duration = _recorded_stage_duration(result, attribute)
        if duration is not None:
            summary.add_stage(label, duration)
    summary.set_total_time(elapsed_seconds)
    summary.print()

def _print_studio_subtitle_export_summary(
    options,
    result,
    elapsed_seconds,
):
    summary = PipelineSummary(
        options["project_name"],
        include_visual_metrics=False,
    )
    plan = options["studio_subtitle_export_plan"]
    mode_labels = {
        StudioSubtitleExportMode.TRANSCRIBIR: "TRANSCRIBIR",
        StudioSubtitleExportMode.CONVERTIR: "CONVERTIR",
    }
    profile_id = options.get("profile_id")
    profile_platform = options.get("profile_platform")
    if profile_id and profile_platform:
        summary.add_detail(
            "Perfil / plataforma",
            f"{profile_id} / {profile_platform.title()}",
        )
    summary.add_detail("Entrada", "EXPORTAR SRT")
    summary.add_detail("Modo", mode_labels[plan.mode])
    summary.add_detail("Fuente", plan.source_path)
    if plan.mode is StudioSubtitleExportMode.CONVERTIR:
        summary.add_detail(
            "Formato",
            _subtitle_display_name(options),
        )
    summary.add_detail("SRT generado", result.output_path)
    summary.add_detail("Estado final", "EXPORTAR SRT COMPLETADO")
    summary.add_stage(
        (
            "Transcripcion"
            if plan.mode is StudioSubtitleExportMode.TRANSCRIBIR
            else "Conversion SRT"
        ),
        result.operation_duration,
    )
    summary.set_total_time(elapsed_seconds)
    summary.print()


def _print_studio_montage_summary(options, result, elapsed_seconds):
    plan = options["studio_montage_plan"]
    montage_result = getattr(result, "montage_result", result)
    render_result = getattr(result, "render_result", None)
    summary = PipelineSummary(
        options["project_name"],
        include_visual_metrics=False,
    )
    summary.add_detail(
        "Perfil / plataforma",
        (
            f"{options['profile_id']} / "
            f"{options['profile_platform'].title()}"
        ),
    )
    summary.add_detail("Entrada", "MONTAJE DE VIDEOS")
    summary.add_detail("Clips", montage_result.clip_count)
    if montage_result.normalized_clip_count:
        summary.add_detail("Normalizados", montage_result.normalized_clip_count)
    summary.add_detail(
        "Transiciones",
        "Si" if plan.transitions_enabled else "No",
    )
    if render_result is not None:
        summary.add_detail(
            "Música",
            "Sí" if options.get("studio_music_path") else "No",
        )
        intro_outro = options.get("intro_outro_selection")
        summary.add_detail(
            "Intro / Outro",
            _intro_outro_label(intro_outro),
        )
    summary.add_detail("Video final", result.output_path)
    summary.add_detail("Estado final", "STUDIO COMPLETADO")
    summary.set_media_duration(result.generated_duration)
    summary.add_stage("Preparacion clips", montage_result.preparation_duration)
    normalization_duration = _recorded_stage_duration(
        montage_result,
        "normalization_duration",
    )
    if normalization_duration is not None:
        summary.add_stage("Normalizacion clips", normalization_duration)
    summary.add_stage("Montaje de videos", montage_result.montage_duration)
    if render_result is not None:
        render_duration = _recorded_stage_duration(
            render_result,
            "render_duration",
        )
        intro_outro_duration = _recorded_stage_duration(
            render_result,
            "intro_outro_duration",
        )
        if render_duration is not None:
            summary.add_stage("Render STUDIO", render_duration)
        if intro_outro_duration is not None:
            summary.add_stage("Intro / Outro", intro_outro_duration)
    summary.set_total_time(elapsed_seconds)
    summary.print()


def _intro_outro_label(plan):
    if plan is None:
        return "No"
    if plan.intro is not None and plan.outro is not None:
        return "Intro + Outro"
    if plan.intro is not None:
        return "Solo intro"
    return "Solo outro"


def _recorded_stage_duration(result, attribute):
    value = getattr(result, attribute, None)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return max(0.0, float(value))


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
