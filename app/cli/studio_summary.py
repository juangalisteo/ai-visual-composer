"""Terminal summaries of the STUDIO routes, read from the typed request.

Every mode prints the same block, in the same order, and leaves out only the
lines that do not apply to it:

1. ``Formato`` (and ``Perfil``, only if the operational profile declares a
   ``display_name``: a technical ID is never shown) and ``Entrada``.
2. The inputs of the mode (``Video fuente``, ``Audio nuevo``, ``SRT fuente``,
   ``Clips``, ``Fuente``…).
3. ``Subtítulos`` and the chosen subtitle profile by its name, ``Música`` and
   ``Intro / Outro`` where the mode offers them.
4. The durations, the output files and ``Estado final``.
5. The block of times, always.
"""

from pathlib import Path

from app.managers.pipeline_summary import PipelineSummary
from app.modules.studio import StudioInputMode, StudioSubtitleExportMode
from app.shared.format_catalog import FormatCatalog
from app.shared.operational_error import OperationalError
from app.shared.profile_resolver import ProfileResolver
from app.shared.screen_number import screen_decimal
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
    return FormatCatalog().label(profile_format)


def _declared_profile_name(profile_key):
    """The ``display_name`` of the operational profile, or None if absent."""
    try:
        document = ProfileResolver().load_operational(profile_key)
    except (FileNotFoundError, OperationalError, TypeError, ValueError):
        return None
    name = document.get("display_name") if isinstance(document, dict) else None
    if isinstance(name, str) and name.strip():
        return name.strip()
    return None


def _seconds(value):
    return f"{screen_decimal(value, 2)} s"


def _new_summary(request):
    return PipelineSummary(request.project_name, include_visual_metrics=False)


def _add_profile_lines(summary, request):
    """``Formato`` (and ``Perfil`` if declared) and ``Entrada``."""
    profile_key = request.operational_profile_key
    if profile_key is not None:
        summary.add_detail("Formato", _format_label(profile_key.format))
        profile_name = _declared_profile_name(profile_key)
        if profile_name is not None:
            summary.add_detail("Perfil", profile_name)
    summary.add_detail("Entrada", request.route.input_mode.label)


def _add_subtitle_lines(summary, request, enabled):
    summary.add_detail("Subtítulos", "Sí" if enabled else "No")
    if enabled:
        summary.add_detail(
            "Perfil de subtítulos",
            _subtitle_display_name(request),
        )


def _add_output_lines(summary, result, *, base_subtitle_path=None):
    generated_subtitle_path = getattr(result, "generated_subtitle_path", None)
    has_base = isinstance(base_subtitle_path, (str, Path))
    has_generated = isinstance(generated_subtitle_path, (str, Path))
    if (
        has_base
        and has_generated
        and Path(base_subtitle_path) == Path(generated_subtitle_path)
    ):
        summary.add_detail("SRT", base_subtitle_path)
    else:
        if has_base:
            summary.add_detail("SRT base", base_subtitle_path)
        if has_generated:
            summary.add_detail("SRT generado", generated_subtitle_path)
    summary.add_detail("Video final", result.output_path)


def _add_final_lines(summary, request, result, elapsed_seconds, stages):
    """``Estado final``, the block of times and the summary itself."""
    summary.add_detail(
        "Estado final",
        f"{request.route.input_mode.label} COMPLETADO",
    )
    summary.set_media_duration(getattr(result, "generated_duration", None))
    for label, source, attribute in stages:
        duration = _recorded_stage_duration(source, attribute)
        if duration is not None:
            summary.add_stage(label, duration)
    summary.set_total_time(elapsed_seconds)
    summary.print()


def _add_final_duration(summary, result):
    final_duration = _recorded_stage_duration(result, "generated_duration")
    if final_duration is not None:
        summary.add_detail("Duración final", _seconds(final_duration))


def _print_render_summary(request, result, elapsed_seconds):
    """Summary of SRT + VIDEO, SOLO VIDEO and VIDEO + AUDIO | SRT."""
    route = request.route
    summary = _new_summary(request)
    _add_profile_lines(summary, request)
    if route.input_mode is StudioInputMode.VIDEO_AUDIO_SRT:
        _add_video_audio_lines(summary, request, result)
    else:
        if route.video_path is not None:
            summary.add_detail("Video fuente", route.video_path)
        if route.subtitle_path is not None:
            summary.add_detail("SRT fuente", route.subtitle_path)
        _add_subtitle_lines(
            summary,
            request,
            request.subtitle_profile_key is not None,
        )
        summary.add_detail(
            "Música",
            "Sí" if route.music_path is not None else "No",
        )
        summary.add_detail(
            "Intro / Outro",
            _intro_outro_label(route.intro_outro_plan),
        )
        _add_final_duration(summary, result)
    _add_output_lines(
        summary,
        result,
        base_subtitle_path=getattr(result, "base_subtitle_path", None),
    )
    _add_final_lines(
        summary,
        request,
        result,
        elapsed_seconds,
        (
            ("Preparación subtítulos", result, "subtitle_preparation_duration"),
            ("Render STUDIO", result, "render_duration"),
            ("Intro / Outro", result, "intro_outro_duration"),
        ),
    )


def _add_video_audio_lines(summary, request, result):
    """Inputs, subtitles and durations of VIDEO + AUDIO | SRT."""
    plan = request.route.plan
    summary.add_detail("Video fuente", plan.video_path)
    summary.add_detail("Audio nuevo", plan.audio_path)
    if plan.subtitle_path is not None:
        summary.add_detail("SRT fuente", plan.subtitle_path)
    _add_subtitle_lines(
        summary,
        request,
        request.subtitle_profile_key is not None,
    )
    video_duration = getattr(plan, "video_duration", None)
    audio_duration = getattr(plan, "audio_duration", None)
    if video_duration is not None:
        summary.add_detail("Duración vídeo", _seconds(video_duration))
    if audio_duration is not None:
        summary.add_detail("Duración audio nuevo", _seconds(audio_duration))
    _add_final_duration(summary, result)
    if (
        video_duration is not None
        and audio_duration is not None
        and audio_duration > video_duration
    ):
        summary.add_detail("Tratamiento audio", "Recortado al vídeo")
    elif (
        video_duration is not None
        and audio_duration is not None
        and audio_duration < video_duration
    ):
        summary.add_detail(
            "Tratamiento audio",
            _audio_tail_label(
                plan.audio_tail_mode,
                video_duration - audio_duration,
            ),
        )


def _print_intro_outro_summary(request, result, elapsed_seconds):
    summary = _new_summary(request)
    plan = request.route.plan
    _add_profile_lines(summary, request)
    summary.add_detail("Video fuente", plan.source_path)
    summary.add_detail(
        "Intro / Outro",
        _intro_outro_label(plan.intro_outro_plan),
    )
    _add_final_duration(summary, result)
    _add_output_lines(summary, result)
    _add_final_lines(
        summary,
        request,
        result,
        elapsed_seconds,
        (
            ("Preparación video", result, "render_duration"),
            ("Intro / Outro", result, "intro_outro_duration"),
        ),
    )


def _print_subtitle_export_summary(
    request,
    result,
    elapsed_seconds,
):
    summary = _new_summary(request)
    plan = request.route.plan
    mode_labels = {
        StudioSubtitleExportMode.TRANSCRIBIR: "TRANSCRIBIR",
        StudioSubtitleExportMode.CONVERTIR: "CONVERTIR",
    }
    _add_profile_lines(summary, request)
    summary.add_detail("Modo", mode_labels[plan.mode])
    summary.add_detail("Fuente", plan.source_path)
    if plan.mode is StudioSubtitleExportMode.CONVERTIR:
        summary.add_detail(
            "Perfil de subtítulos",
            _subtitle_display_name(request),
        )
        summary.add_detail(
            "Tiempos",
            "Estimados: el tiempo de cada bloque del SRT se reparte entre sus "
            "palabras por letras. Para tiempos exactos, TRANSCRIBIR o SOLO VIDEO.",
        )
    else:
        # PRUEBA-GS, fallo 18: lines of up to ~80 characters.
        summary.add_detail(
            "Frases",
            "Largas, las de Whisper. Para pintarlo, pásalo antes por CONVERTIR.",
        )
    summary.add_detail("SRT generado", result.output_path)
    stage_label = (
        "Transcripción"
        if plan.mode is StudioSubtitleExportMode.TRANSCRIBIR
        else "Conversión SRT"
    )
    summary.add_detail(
        "Estado final",
        f"{request.route.input_mode.label} COMPLETADO",
    )
    summary.add_stage(stage_label, result.operation_duration)
    summary.set_total_time(elapsed_seconds)
    summary.print()


def _print_montage_summary(request, result, elapsed_seconds):
    route = request.route
    plan = route.plan
    montage_result = getattr(result, "montage_result", result)
    render_result = getattr(result, "render_result", None)
    summary = _new_summary(request)
    _add_profile_lines(summary, request)
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
    _add_final_duration(summary, result)
    _add_output_lines(summary, result)
    _add_final_lines(
        summary,
        request,
        result,
        elapsed_seconds,
        (
            ("Preparación clips", montage_result, "preparation_duration"),
            ("Normalización clips", montage_result, "normalization_duration"),
            ("Montaje de videos", montage_result, "montage_duration"),
            ("Render STUDIO", render_result, "render_duration"),
            ("Intro / Outro", render_result, "intro_outro_duration"),
        ),
    )


def _audio_tail_label(mode, shortfall_seconds):
    """How VIDEO + AUDIO | SRT treated a new audio shorter than the video."""
    if mode == "music":
        return "Audio + música final"
    if mode == "cut_video":
        return "Vídeo cortado donde acaba el audio"
    if mode == "none":
        return (
            f"Sin cambios (el audio dura {screen_decimal(shortfall_seconds, 3)} s menos, "
            "dentro del margen)"
        )
    return "Audio + silencio final"


def _intro_outro_label(plan):
    if plan is None or (plan.intro is None and plan.outro is None):
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
