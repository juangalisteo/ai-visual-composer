import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from app.backend_adapters.models import (
    BackendAdapterTrace,
    BackendAdapterTraceItem,
    ComfyUIPayload,
)
from app.prompt_translation import BackendPrompt


class ComfyUIAdapter:
    provider = "comfyui"

    def adapt(
        self,
        backend_prompt: BackendPrompt
    ) -> ComfyUIPayload:
        prompt_parts = tuple(
            instruction.value
            for instruction in backend_prompt.instructions
            if instruction.value
        )
        prompt = ", ".join(
            _dedupe(
                prompt_parts
            )
        )
        trace = BackendAdapterTrace(
            source_backend_prompt_fingerprint=backend_prompt.fingerprint,
            items=(
                BackendAdapterTraceItem(
                    payload_field="prompt",
                    instruction_ids=tuple(
                        instruction.id
                        for instruction in backend_prompt.instructions
                    ),
                    source_fields=tuple(
                        source_field
                        for item in backend_prompt.trace.items
                        for source_field in item.source_fields
                    ),
                    transformation="join_instructions_for_comfyui_text_prompt",
                ),
            ),
        )
        payload = ComfyUIPayload(
            provider=self.provider,
            prompt=prompt,
            trace=trace,
        )
        return ComfyUIPayload(
            provider=payload.provider,
            prompt=payload.prompt,
            trace=payload.trace,
            fingerprint=self._fingerprint(
                payload
            ),
        )

    def _fingerprint(
        self,
        payload: ComfyUIPayload
    ) -> str:
        canonical = {
            "provider": payload.provider,
            "prompt": payload.prompt,
            "trace": _canonical_mapping(
                payload.trace
            ),
        }
        return hashlib.sha256(
            json.dumps(
                canonical,
                sort_keys=True,
                separators=(
                    ",",
                    ":"
                )
            ).encode(
                "utf-8"
            )
        ).hexdigest()


def _dedupe(
    values: tuple[str, ...]
) -> tuple[str, ...]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(
                value
            )
            result.append(
                value
            )
    return tuple(
        result
    )


def _canonical_mapping(
    value: Any
) -> Any:
    if isinstance(
        value,
        Enum
    ):
        return value.value
    if is_dataclass(
        value
    ):
        return {
            key: _canonical_mapping(
                item
            )
            for key, item in asdict(
                value
            ).items()
        }
    if isinstance(
        value,
        dict
    ):
        return {
            key: _canonical_mapping(
                item
            )
            for key, item in sorted(
                value.items()
            )
        }
    if isinstance(
        value,
        (
            tuple,
            list,
        )
    ):
        return [
            _canonical_mapping(
                item
            )
            for item in value
        ]
    return value
