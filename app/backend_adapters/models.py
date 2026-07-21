from dataclasses import dataclass, field


@dataclass(frozen=True)
class BackendAdapterTraceItem:
    payload_field: str
    instruction_ids: tuple[str, ...]
    source_fields: tuple[str, ...]
    transformation: str


@dataclass(frozen=True)
class BackendAdapterTrace:
    source_backend_prompt_fingerprint: str = ""
    items: tuple[BackendAdapterTraceItem, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ComfyUIPayload:
    provider: str
    prompt: str
    trace: BackendAdapterTrace
    source_id: str = ""
    source_version: str = ""
    fingerprint: str = ""
