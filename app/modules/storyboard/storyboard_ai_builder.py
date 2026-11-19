from dataclasses import dataclass, field

from app.providers.ollama_provider import (
    OllamaProvider,
    OllamaRequestPolicy,
)
from app.providers.ollama_settings import ollama_call_settings


# Section of config/ai.json with the storyboard's model, think and options
# (num_ctx: the storyboard prompt grows with the number of scenes).
STORYBOARD_AI_TASK = "storyboard"


@dataclass(frozen=True)
class StoryboardRequestPolicy:
    """Storyboard-owned, verified structured-output request intent."""

    ollama_policy: OllamaRequestPolicy = field(
        default_factory=lambda: OllamaRequestPolicy(
            format=storyboard_response_schema(),
            think=False,
        )
    )

    @classmethod
    def from_settings(cls, settings):
        """Structured output plus what ``config/ai.json`` declares."""
        return cls(
            OllamaRequestPolicy(
                format=storyboard_response_schema(),
                think=(
                    False
                    if settings.think is None
                    else settings.think
                ),
                options=settings.options,
            )
        )


def storyboard_response_schema():
    """Return the existing PromptEngine storyboard response shape."""
    text_fields = (
        "visible_subject",
        "visible_action",
        "visible_environment",
        "time_context",
        "abstract_source",
        "filmable_interpretation",
        "visual_truth_status",
    )
    sequence_fields = (
        "key_objects",
        "spatial_relationships",
        "continuity_links",
        "visual_constraints",
    )
    properties = {
        "scene": {
            "type": "integer",
        },
    }
    properties.update(
        {
            field_name: {
                "type": "string",
            }
            for field_name in text_fields
        }
    )
    properties.update(
        {
            field_name: {
                "type": "array",
                "items": {
                    "type": "string",
                },
            }
            for field_name in sequence_fields
        }
    )
    return {
        "type": "array",
        "items": {
            "type": "object",
            "properties": properties,
            "required": [
                "scene",
                *text_fields,
                *sequence_fields,
            ],
            "additionalProperties": False,
        },
    }


class StoryboardAIBuilder:

    def __init__(
        self,
        ai_config,
        provider=None,
        request_policy=None,
    ):
        settings = ollama_call_settings(
            ai_config,
            STORYBOARD_AI_TASK,
        )
        self.provider = provider or OllamaProvider.from_settings(
            settings
        )
        self.request_policy = (
            request_policy
            or StoryboardRequestPolicy.from_settings(settings)
        )
        if not isinstance(self.request_policy, StoryboardRequestPolicy):
            raise TypeError(
                "request_policy debe ser StoryboardRequestPolicy."
            )
        self.last_result = None

    def build(
        self,
        prompt
    ):
        result = self.provider.generate_result(
            prompt,
            policy=self.request_policy.ollama_policy,
        )
        self.last_result = result
        response = result.content.strip()

        if not response:
            raise ValueError(
                "Ollama devolvió una respuesta vacía "
                "para el storyboard."
            )

        return response
