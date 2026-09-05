import os

from app.controllers.run_controller import RunController
from app.core.start import iniciar
from app.managers.output_manager import OutputManager
from app.modules.visual_design import VisualDesignInterpretationError


def main():

    controller = RunController()
    options = controller.run()

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
    os.environ["MC_VOICE_CONFIG"] = options["voice_config"]
    os.environ["MC_MUSIC_CATEGORY"] = options["music_category"] or ""
    os.environ["MC_OVERLAYS_MODE"] = options["overlays_mode"]
    os.environ["MC_PROJECT_NAME"] = options["project_name"]
    os.environ["MC_VISUAL_PIPELINE"] = options["visual_pipeline"]
    os.environ["MC_SCRIPT_SOURCE"] = options["script_source"]
    os.environ["MC_DESIGN_TARGET"] = options.get("design_target", "")
    os.environ["MC_PIPELINE_MODE"] = options["pipeline_mode"]

    if options["clear_output"]:
        OutputManager().reset()

    start_options = {
        "subtitle_style": (
            options["subtitle_config"]
            or None
        )
    }
    intro_outro_selection = options.get(
        "intro_outro_selection"
    )
    if intro_outro_selection is not None:
        start_options["intro_outro_selection"] = (
            intro_outro_selection
        )
    if options.get("pipeline_mode") == "studio":
        start_options["studio_light_leaks_enabled"] = bool(
            options.get("studio_light_leaks_enabled", False)
        )

    try:
        iniciar(**start_options)
    except VisualDesignInterpretationError as error:
        print(
            f"ERROR: {error}"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
