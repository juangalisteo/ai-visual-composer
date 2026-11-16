from app.domain import (
    StoryboardScene,
    VisualIntelligenceFinding,
    VisualReasoningResult,
)
from app.visual_intelligence import (
    VisualAnalysisOrchestrator,
    VisualReasoningOrchestrator,
)


def complete_scene():
    return StoryboardScene(
        scene_number=1,
        text="Una investigadora recibe una llave antigua.",
        visible_subject="investigadora con abrigo gris",
        visible_action="recibe una llave antigua",
        visible_environment="archivo subterraneo",
        time_context="noche lluviosa",
        key_objects=(
            "llave antigua",
            "sobre lacrado",
        ),
        spatial_relationships=(
            "la llave queda entre ambas manos",
        ),
        continuity_links=(
            "misma investigadora",
            "misma llave antigua",
        ),
        abstract_source="confianza entregada",
        filmable_interpretation="una llave antigua cambia de manos",
        visual_constraints=(
            "sin texto legible",
        ),
    )


def warning_scene():
    return StoryboardScene(
        scene_number=1,
        text="Retrato simple",
        visible_subject="arquitecta",
        visible_action="observa",
        visible_environment="azotea",
        filmable_interpretation="arquitecta observa",
    )


def error_scene():
    return StoryboardScene(
        scene_number=1,
        text="Accion sin sujeto",
        visible_action="abre una puerta",
        visible_environment="pasillo",
        filmable_interpretation="una puerta se abre",
    )


def blocking_scene():
    return StoryboardScene(
        scene_number=1,
        text=""
    )


def analysis_for(scene):
    return VisualAnalysisOrchestrator().analyze(
        scene
    )


def reasoning_for(scene) -> VisualReasoningResult:
    analysis = analysis_for(
        scene
    )
    return VisualReasoningOrchestrator().reason(
        analysis
    )


def analysis_and_reasoning(scene):
    analysis = analysis_for(
        scene
    )
    reasoning = VisualReasoningOrchestrator().reason(
        analysis
    )
    return analysis, reasoning


def severities(findings: tuple[VisualIntelligenceFinding, ...]):
    return tuple(
        finding.severity
        for finding in findings
    )
