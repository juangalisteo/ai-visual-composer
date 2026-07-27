import os

from app.controllers.run_controller import RunController
from app.core.start import iniciar
from app.managers.output_manager import OutputManager


def main():

    controller = RunController()
    options = controller.run()

    os.environ["MC_PROFILE_PATH"] = options["profile_path"]
    os.environ["MC_SUBTITLE_CONFIG"] = options["subtitle_config"]
    os.environ["MC_VOICE_CONFIG"] = options["voice_config"]
    os.environ["MC_MUSIC_CATEGORY"] = options["music_category"] or ""
    os.environ["MC_PROJECT_NAME"] = options["project_name"]
    os.environ["MC_VISUAL_PIPELINE"] = options["visual_pipeline"]
    os.environ["MC_PIPELINE_MODE"] = options["pipeline_mode"]

    if options["clear_output"]:
        OutputManager().reset()

    iniciar()


if __name__ == "__main__":
    main()
