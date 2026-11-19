from pathlib import Path

from app.core.prompt_engine import PromptEngine
from app.modules.script.models import PreparedScript
from app.modules.script.script_builder import ScriptBuilder
from app.modules.script.validator import count_script_words
from app.shared.operational_error import create_operational_error
from app.shared.progress_logger import ProgressLogger


def _script_input_error(
    *,
    family,
    user_message,
    recommended_action
):
    """User input error: the input file is missing or empty."""
    return create_operational_error(
        family=family,
        user_message=user_message,
        recommended_action=recommended_action,
        operation="Preparar el guion"
    )


class ScriptPreparationService:

    def __init__(
        self,
        prompt_engine=None,
        script_builder_factory=ScriptBuilder
    ):
        self.prompt_engine = prompt_engine
        self.script_builder_factory = (
            script_builder_factory
        )

    def prepare(
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
    ) -> PreparedScript:
        """Prepare the script; ``voice_pacing`` sizes a script generated from a topic."""
        input_script_path = Path(
            input_script_path
        )
        input_topic_path = Path(
            input_topic_path
        )
        output_script_path = Path(
            output_script_path
        )
        source_mode = str(
            source_mode
        ).strip().lower()

        should_prepare_script = builders.get(
            "script",
            True
        )

        if should_prepare_script:
            prepared_script = self._prepare_from_input(
                ai_config=ai_config,
                profile=profile,
                input_script_path=input_script_path,
                input_topic_path=input_topic_path,
                output_script_path=output_script_path,
                source_mode=source_mode,
                voice_pacing=voice_pacing,
            )
        else:
            prepared_script = self._prepare_existing(
                output_script_path
            )

        if should_prepare_script:
            self._persist(
                prepared_script
            )

        return prepared_script

    def _prepare_from_input(
        self,
        *,
        ai_config,
        profile,
        input_script_path,
        input_topic_path,
        output_script_path,
        source_mode,
        voice_pacing
    ) -> PreparedScript:
        if source_mode == "manual":
            return self._prepare_manual(
                input_script_path=input_script_path,
                output_script_path=output_script_path
            )

        if source_mode == "generated":
            return self._prepare_generated(
                ai_config=ai_config,
                profile=profile,
                input_topic_path=input_topic_path,
                output_script_path=output_script_path,
                voice_pacing=voice_pacing,
            )

        raise ValueError(
            "Origen de guion no soportado: "
            f"{source_mode}"
        )

    def _prepare_manual(
        self,
        *,
        input_script_path,
        output_script_path
    ) -> PreparedScript:
        manual_script = ""

        if input_script_path.exists():
            manual_script = input_script_path.read_text(
                encoding="utf-8"
            ).strip()

        if manual_script:
            ProgressLogger.info(
                "Usando guion manual."
            )

            return self._build_prepared_script(
                text=str(
                    manual_script
                ).strip(),
                source="manual",
                path=output_script_path
            )

        if input_script_path.exists():
            raise _script_input_error(
                family="VALIDATION",
                user_message=(
                    f"El archivo {input_script_path.as_posix()} "
                    "está vacío."
                ),
                recommended_action=(
                    "Escribe el guion en "
                    f"{input_script_path.as_posix()} "
                    "y vuelve a intentarlo."
                )
            )

        raise _script_input_error(
            family="FILESYSTEM",
            user_message=(
                f"No existe {input_script_path.as_posix()}."
            ),
            recommended_action=(
                f"Crea {input_script_path.as_posix()} "
                "con el guion y vuelve a intentarlo."
            )
        )

    def _prepare_generated(
        self,
        *,
        ai_config,
        profile,
        input_topic_path,
        output_script_path,
        voice_pacing
    ) -> PreparedScript:
        if not input_topic_path.exists():
            raise _script_input_error(
                family="FILESYSTEM",
                user_message=(
                    f"No existe {input_topic_path.as_posix()}."
                ),
                recommended_action=(
                    f"Crea {input_topic_path.as_posix()} "
                    "con el tema del vídeo y vuelve a intentarlo."
                )
            )

        topic = input_topic_path.read_text(
            encoding="utf-8"
        ).strip()

        if not topic:
            raise _script_input_error(
                family="VALIDATION",
                user_message=(
                    f"El archivo {input_topic_path.as_posix()} "
                    "está vacío."
                ),
                recommended_action=(
                    "Escribe el tema del vídeo en "
                    f"{input_topic_path.as_posix()} "
                    "y vuelve a intentarlo."
                )
            )

        request = (
            self._prompt_engine()
            .build_script_request(
                topic,
                profile,
                voice_pacing,
            )
        )

        script = (
            self.script_builder_factory(
                ai_config
            )
            .build(
                request.prompt,
                length=request.length,
            )
            .strip()
        )

        return self._build_prepared_script(
            text=script,
            source="generated",
            path=output_script_path
        )

    def _prepare_existing(
        self,
        output_script_path
    ) -> PreparedScript:
        if not output_script_path.exists():
            raise FileNotFoundError(
                "ScriptBuilder está desactivado "
                "y no existe el guion esperado: "
                f"{output_script_path}"
            )

        script = output_script_path.read_text(
            encoding="utf-8"
        ).strip()

        if not script:
            raise ValueError(
                "ScriptBuilder está desactivado "
                "y el guion existente está vacío: "
                f"{output_script_path}"
            )

        ProgressLogger.info(
            "Usando guion existente."
        )

        return self._build_prepared_script(
            text=script,
            source="existing",
            path=output_script_path
        )

    def _prompt_engine(
        self
    ):
        if self.prompt_engine is None:
            self.prompt_engine = PromptEngine()

        return self.prompt_engine

    def _build_prepared_script(
        self,
        *,
        text,
        source,
        path
    ) -> PreparedScript:
        script = str(
            text
        ).strip()

        return PreparedScript(
            text=script,
            source=source,
            path=Path(
                path
            ),
            word_count=count_script_words(
                script
            )
        )

    def _persist(
        self,
        prepared_script
    ):
        prepared_script.path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        prepared_script.path.write_text(
            prepared_script.text,
            encoding="utf-8"
        )
