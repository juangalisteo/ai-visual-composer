from app.core.prompt_engine import PromptEngine
from app.modules.storyboard.storyboard_ai_builder import (
    StoryboardAIBuilder,
)
from app.modules.storyboard.storyboard_response_parser import (
    StoryboardResponseParser,
)
from app.modules.storyboard.storyboard_validator import (
    StoryboardValidator,
)
from app.shared.config_manager import ConfigManager
from app.shared.operational_error import (
    OperationalError,
    create_operational_error,
)


class VisualDesignInterpretationError(RuntimeError):
    pass


class VisualDesignInterpreter:

    def __init__(
        self,
        ai_config=None,
        profile=None,
        prompt_engine=None,
        ai_builder_factory=None,
        response_parser=None,
        storyboard_validator=None
    ):
        self.ai_config = ai_config
        self.profile = profile
        self.prompt_engine = (
            prompt_engine
            or PromptEngine()
        )
        self.ai_builder_factory = ai_builder_factory
        self.response_parser = (
            response_parser
            or StoryboardResponseParser()
        )
        self.storyboard_validator = (
            storyboard_validator
            or StoryboardValidator()
        )

    def interpret(
        self,
        text
    ):
        text = str(
            text
        ).strip()

        if not text:
            raise ValueError(
                "El diseño visual está vacío."
            )

        try:
            return self._interpret(
                text
            )
        except OperationalError:
            raise
        except TimeoutError as error:
            raise self._external_service_error(
                "La interpretación visual no pudo completarse.",
                error,
            ) from error
        except VisualDesignInterpretationError as error:
            raise self._external_service_error(
                "La interpretación visual no pudo completarse.",
                error,
            ) from error
        except Exception as error:
            raise self._external_service_error(
                "La interpretación visual no pudo completarse.",
                error,
            ) from error

    @staticmethod
    def _external_service_error(user_message, error):
        return create_operational_error(
            family="EXTERNAL_SERVICE",
            user_message=user_message,
            recommended_action=(
                "Comprueba la disponibilidad del proveedor de diseño visual "
                "e inténtalo de nuevo."
            ),
            operation="Interpretar diseño visual",
            technical_metadata={
                "service": "visual_design",
                "provider_error": type(error).__name__,
            },
        )

    def _interpret(
        self,
        text
    ):
        base_scene = {
            "scene": 1,
            "text": text
        }

        prompt = self.prompt_engine.build_storyboard_prompt(
            scenes=[
                base_scene
            ],
            profile=self._profile()
        )

        raw_response = self._ai_builder().build(
            prompt
        )

        parsed_response = self.response_parser.parse(
            raw_response
        )

        validated_scenes = self.storyboard_validator.validate(
            visual_scenes=parsed_response,
            expected_scene_count=1
        )

        visual_truth = dict(
            validated_scenes[0]
        )
        visual_truth["abstract_source"] = text
        visual_truth["visual_truth_status"] = (
            "manual_design_interpreted"
        )

        self._validate_structural_quality(
            source_text=text,
            visual_truth=visual_truth
        )

        return visual_truth

    def _profile(
        self
    ):
        if self.profile is not None:
            return self.profile
        return ConfigManager().get_profile_config()

    def _ai_config(
        self
    ):
        if self.ai_config is not None:
            return self.ai_config
        return ConfigManager().get_ai_config()

    def _ai_builder(
        self
    ):
        if self.ai_builder_factory is not None:
            return self.ai_builder_factory(
                self._ai_config()
            )
        return StoryboardAIBuilder(
            self._ai_config()
        )

    def _validate_structural_quality(
        self,
        source_text,
        visual_truth
    ):
        source = self._normalize(
            source_text
        )
        field_values = [
            self._normalize(
                visual_truth.get(
                    field,
                    ""
                )
            )
            for field in (
                "visible_subject",
                "visible_action",
                "visible_environment",
                "filmable_interpretation",
            )
        ]

        if all(
            value == source
            for value in field_values
        ):
            raise VisualDesignInterpretationError(
                "La interpretación visual no puede copiar "
                "el texto de entrada en todos los campos "
                "Visual Truth."
            )

    def _normalize(
        self,
        value
    ):
        return " ".join(
            str(
                value
            ).strip().lower().split()
        )
