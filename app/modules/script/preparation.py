from pathlib import Path

from app.core.prompt_engine import PromptEngine
from app.modules.script.models import PreparedScript
from app.modules.script.script_builder import ScriptBuilder
from app.modules.script.validator import count_script_words
from app.shared.progress_logger import ProgressLogger


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
        source_mode="generated"
    ) -> PreparedScript:
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
                source_mode=source_mode
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
        source_mode
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
                output_script_path=output_script_path
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
            raise ValueError(
                "El archivo input/guion.txt "
                "está vacío."
            )

        raise FileNotFoundError(
            "No existe input/guion.txt."
        )

    def _prepare_generated(
        self,
        *,
        ai_config,
        profile,
        input_topic_path,
        output_script_path
    ) -> PreparedScript:
        if not input_topic_path.exists():
            raise FileNotFoundError(
                "No existe input/tema.txt."
            )

        topic = input_topic_path.read_text(
            encoding="utf-8"
        ).strip()

        if not topic:
            raise ValueError(
                "El archivo input/tema.txt "
                "está vacío."
            )

        prompt = (
            self._prompt_engine()
            .build_script_prompt(
                topic,
                profile
            )
        )

        script = (
            self.script_builder_factory(
                ai_config
            )
            .build(
                prompt
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
