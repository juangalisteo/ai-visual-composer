from app.modules.script.preparation import ScriptPreparationService


class ScriptOperation:

    def __init__(
        self,
        preparation_service=None
    ):
        self.preparation_service = (
            preparation_service
            or ScriptPreparationService()
        )

    def execute(
        self,
        *,
        builders,
        ai_config,
        profile,
        input_script_path,
        input_topic_path,
        output_script_path,
        source_mode="generated",
        voice_pacing=None,
    ):
        return self.preparation_service.prepare(
            builders=builders,
            ai_config=ai_config,
            profile=profile,
            input_script_path=input_script_path,
            input_topic_path=input_topic_path,
            output_script_path=output_script_path,
            source_mode=source_mode,
            voice_pacing=voice_pacing,
        )
