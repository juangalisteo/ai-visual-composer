"""Terminal summaries of the STUDIO routes, read from the typed request."""

from pathlib import Path

from app.controllers.interaction import labels
from app.controllers.interaction.format_catalog import FormatCatalog
from app.managers.pipeline_summary import PipelineSummary
from app.modules.studio import StudioInputMode, StudioSubtitleExportMode
from app.shared.operational_error import OperationalError
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


def print_studio_summary(request, result, elapsed_seconds):
    """Print the summary of the STUDIO input mode that ``request`` ran."""
    input_mode = request.route.input_mode
    if input_mode is StudioInputMode.INTRO_OUTRO:
        _print_intro_outro_summary(request, result, elapsed_seconds)
    elif input_mode is StudioInputMode.MONTAJE_VIDEOS:
        _print_montage_summary(request, result, elapsed_seconds)
    elif input_mode is StudioInputMode.EXPORTAR_SRT:
        _print_subtitle_export_summary(request, result, elapsed_seconds)
    else:
        _print_render_summary(request, result, elapsed_seconds)


def _subtitle_display_name(request):
    selected_key = request.subtitle_profile_key
    if selected_key is None:
        return ""

    try:
        return SubtitleProfileResolver().load(selected_key).display_name
    except (FileNotFoundError, OperationalError, TypeError, ValueError):
        return selected_key.profile_id


def _format_label(profile_format):
    try:
        return FormatCatalog().label(profile_format)
    except OperationalError:
        return labels.label(profile_format)


def _print_render_summary(request, result, elapsed_seconds):
    """Summary of SRT + VIDEO, VIDEO and VIDEO + AUDIO SRT."""
    route = request.route
    profile_key = request.operational_profile_key
    summary = PipelineSummary(
        request.project_name,
        include_visual_metrics=False,
    )
    input_labels = {
        StudioInputMode.SRT_VIDEO: "SRT + VIDEO",
        StudioInputMode.VIDEO: "VIDEO",
        StudioInputMode.VIDEO_AUDIO_SRT: "VIDEO + AUDIO SRT",
    }
    plan = route.intro_outro_plan
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
        "Perfil / formato",
        (
            f"{profile_key.profile_id} / "
            f"{_format_label(profile_key.format)}"
        ),
    )
    summary.add_detail(
        "Entrada",
        input_labels[route.input_mode],
    )
    if route.input_mode is StudioInputMode.VIDEO_AUDIO_SRT:
        video_audio_plan = route.plan
        subtitles_enabled = request.subtitle_profile_key is not None
        summary.add_detail("Proyecto", request.project_name)
        summary.add_detail("Video fuente", video_audio_plan.video_path)
        summary.add_detail("Audio nuevo", video_audio_plan.audio_path)
        summary.add_detail("Subtítulos", "Sí" if subtitles_enabled else "No")
        if subtitles_enabled:
            summary.add_detail(
                "Perfil de subtítulos",
                _subtitle_display_name(request),
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
                if route.subtitle_original
                else _subtitle_display_name(request)
            ),
        )
        summary.add_detail(
            "Música",
            "Sí" if route.music_path is not None else "No",
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
            if route.input_mode is StudioInputMode.VIDEO_AUDIO_SRT
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


def _print_intro_outro_summary(request, result, elapsed_seconds):
    profile_key = request.operational_profile_key
    summary = PipelineSummary(request.project_name, include_visual_metrics=False)
    plan = request.route.plan
    summary.add_detail(
        "Perfil / formato",
        f"{profile_key.profile_id} / {_format_label(profile_key.format)}",
    )
    summary.add_detail("Entrada", "INTRO / OUTRO")
    summary.add_detail("Video fuente", plan.source_path)
    summary.add_detail("Intro", "Sí" if plan.intro_outro_plan.intro else "No")
    summary.add_detail("Outro", "Sí" if plan.intro_outro_plan.outro else "No")
    summary.add_detail("Video final", result.output_path)
    summary.add_detail("Estado final", "INTRO / OUTRO COMPLETADO")
    summary.set_media_duration(result.generated_duration)
    for label, attribute in (("Preparación video", "render_duration"), ("Intro / Outro", "intro_outro_duration")):
        duration = _recorded_stage_duration(result, attribute)
        if duration is not None:
            summary.add_stage(label, duration)
    summary.set_total_time(elapsed_seconds)
    summary.print()


def _print_subtitle_export_summary(
    request,
    result,
    elapsed_seconds,
):
    summary = PipelineSummary(
        request.project_name,
        include_visual_metrics=False,
    )
    plan = request.route.plan
    mode_labels = {
        StudioSubtitleExportMode.TRANSCRIBIR: "TRANSCRIBIR",
        StudioSubtitleExportMode.CONVERTIR: "CONVERTIR",
    }
    profile_key = request.operational_profile_key
    if profile_key is not None:
        summary.add_detail(
            "Perfil / formato",
            f"{profile_key.profile_id} / {_format_label(profile_key.format)}",
        )
    summary.add_detail("Entrada", "EXPORTAR SRT")
    summary.add_detail("Modo", mode_labels[plan.mode])
    summary.add_detail("Fuente", plan.source_path)
    if plan.mode is StudioSubtitleExportMode.CONVERTIR:
        summary.add_detail(
            "Perfil de subtítulos",
            _subtitle_display_name(request),
        )
    summary.add_detail("SRT generado", result.output_path)
    summary.add_detail("Estado final", "EXPORTAR SRT COMPLETADO")
    summary.add_stage(
        (
            "Transcripción"
            if plan.mode is StudioSubtitleExportMode.TRANSCRIBIR
            else "Conversión SRT"
        ),
        result.operation_duration,
    )
    summary.set_total_time(elapsed_seconds)
    summary.print()


def _print_montage_summary(request, result, elapsed_seconds):
    route = request.route
    profile_key = request.operational_profile_key
    plan = route.plan
    montage_result = getattr(result, "montage_result", result)
    render_result = getattr(result, "render_result", None)
    summary = PipelineSummary(
        request.project_name,
        include_visual_metrics=False,
    )
    summary.add_detail(
        "Perfil / formato",
        (
            f"{profile_key.profile_id} / "
            f"{_format_label(profile_key.format)}"
        ),
    )
    summary.add_detail("Entrada", "MONTAJE DE VIDEOS")
    summary.add_detail("Clips", montage_result.clip_count)
    if montage_result.normalized_clip_count:
        summary.add_detail("Normalizados", montage_result.normalized_clip_count)
    summary.add_detail(
        "Transiciones",
        "Sí" if plan.transitions_enabled else "No",
    )
    if render_result is not None:
        summary.add_detail(
            "Música",
            "Sí" if route.music_path is not None else "No",
        )
        summary.add_detail(
            "Intro / Outro",
            _intro_outro_label(route.intro_outro_plan),
        )
    summary.add_detail("Video final", result.output_path)
    summary.add_detail("Estado final", "STUDIO COMPLETADO")
    summary.set_media_duration(result.generated_duration)
    summary.add_stage("Preparación clips", montage_result.preparation_duration)
    normalization_duration = _recorded_stage_duration(
        montage_result,
        "normalization_duration",
    )
    if normalization_duration is not None:
        summary.add_stage("Normalización clips", normalization_duration)
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
