# IP3.1 Prompt Translation Correction Report

## Phase

`IP3.1 - Prompt Translation Correction and Runtime Input Governance`

## Objective

Correct the real FLUX text encoder failure caused by oversized prompts while preserving the frozen Visual Intelligence architecture and the existing Image Runtime pipeline.

## Root Cause

The failure was caused before ComfyUI execution.

`PromptTranslator` translated too much internal semantic richness directly into backend prompt instructions. Rich nested contracts and cinematic direction fields were recursively expanded, then `ComfyUIAdapter` joined all instruction values into a single operational prompt. This allowed metadata-like material, repeated fragments, low-priority internal details, traces, fingerprints, and contract-shaped text to accumulate.

Observed pre-correction reproduction with a rich scene:

- Backend payload prompt: `49,555` characters.
- Estimated payload tokens: `12,389`.
- Final prompt after operational identity: `50,696` characters.
- Estimated final tokens: `12,674`.
- Backend instructions: `170`.
- FLUX text encoder limit involved in the real error: `512` tokens.

## Correction

`PromptTranslator` now acts as a deterministic semantic compiler.

Implemented behavior:

- extracts only operational visual fields;
- preserves critical visual meaning;
- normalizes scalar and sequence content;
- filters non-visual metadata;
- removes exact duplicates;
- removes semantic duplicates;
- applies priority-based semantic compaction;
- enforces an explicit backend/model prompt budget policy;
- emits `BackendPrompt.compiled_prompt`;
- keeps source traceability in `BackendPrompt.trace`;
- records deterministic compilation metrics;
- generates a stable SHA-256 fingerprint from canonical prompt, trace, policy, and metrics.

`ComfyUIAdapter` now uses `BackendPrompt.compiled_prompt` when available. It retains old instruction joining only as compatibility behavior for older prompts.

`ComfyUIBackend` now raises `ComfyUIBackendError` with structured categories for backend failures, including `PROMPT_TOO_LONG` and `OUT_OF_MEMORY`, while preserving `RuntimeError` compatibility.

## Prompt Budget Policy

Default policy:

- policy: `flux-safe-v1`;
- model: `flux`;
- encoder: `flux-text-encoder`;
- encoder token limit: `512`;
- target prompt tokens: `220`;
- warning prompt tokens: `320`;
- hard prompt tokens: `384`;
- token count method: `conservative_estimate`;
- overflow behavior: `semantic_compaction`.

The hard prompt budget applies to `BackendPrompt.compiled_prompt`. The final prompt sent to ComfyUI also includes the stable `ImagePromptSystem` operational identity and must remain below the FLUX encoder limit.

## Real ComfyUI Validation

Real local ComfyUI was available at `http://127.0.0.1:8188`.

Environment evidence:

- ComfyUI version: `0.26.0`;
- Python: `3.13.12`;
- PyTorch: `2.12.0+cu130`;
- GPU: `NVIDIA GeForce RTX 5070 Laptop GPU`;
- detected VRAM: `8,546,484,224` bytes.

Executed scenario:

- campaign: `ip3_1_prompt_budget_real`;
- scenario: `ip3_1_prompt_budget_1080x1920`;
- profile: `config/profiles/instagram/modo_conciencia.json`;
- resolution: `1080x1920`;
- workflow: `config/comfyui_flux_workflow_api.json`;
- Visual Quality: disabled for prompt-path isolation;
- result: generated successfully in one attempt;
- generation time: `1 min 36.25 s`;
- generated asset: `output/ip3_1_prompt_budget_real_ip3_1_prompt_budget_1080x1920/images/scene_001.png`;
- asset size: `2,096,554` bytes;
- asset fingerprint: `038d3d7251e3d2a260e64180c9308d6fab00bd0c84381f320eec1589a271af41`.

Prompt evidence from the generated manifest:

- compiled positive prompt: `470` characters, `63` words, `117` estimated tokens;
- final prompt sent to ComfyUI after operational identity: `1,611` characters, `221` words, `402` estimated tokens.

The final prompt remained below the FLUX 512-token encoder limit and did not trigger the previous `4682 > 512` failure.

## Validation Results

- `python -m unittest discover`: `589` tests, OK.
- `python -m compileall app tests certification`: OK.
- `git diff --check`: OK.
- Real ComfyUI 1080x1920 validation: OK.

## Architectural Guarantees

- Visual Intelligence contracts remain frozen.
- Prompt Translation does not introduce new visual decisions.
- Prompt Translation does not reinterpret Visual Truth.
- Backend Adapter remains non-cognitive.
- ComfyUIBackend remains runtime infrastructure.
- ImagePromptSystem remains the stable operational identity layer.
- Runtime, workflow, ComfyUI model configuration, Visual Quality, and Video Pipeline were not redesigned.

## Final Status

`IP3_1_PROMPT_TRANSLATION_CORRECTION_FULLY_CLOSED`

