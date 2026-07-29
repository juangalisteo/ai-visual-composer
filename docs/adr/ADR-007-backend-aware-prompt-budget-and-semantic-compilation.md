# ADR-007 - Backend-Aware Prompt Budget and Semantic Compilation

## Status

Accepted.

## Context

After `IP3.0-9`, real ComfyUI execution with FLUX exposed a text encoder failure:

```text
Token indices sequence length is longer than the specified maximum sequence length for this model (4682 > 512)
```

The failure was followed by GPU memory exhaustion. The repository-owned pipeline was passing too much internal semantic material into the backend prompt path. `PromptTranslator` recursively translated rich contracts and cinematic direction data as a long list of prompt fragments, and `ComfyUIAdapter` joined those fragments into a prompt string. This preserved traceability but also leaked repetition, metadata-like content, and low-priority internal detail into the backend text encoder.

## Decision

`PromptTranslator` is a deterministic semantic compiler.

It MUST:

- consume `EffectiveVisualBrief` and optional `CinematicDirectionSet`;
- preserve visible subject, action, environment, composition, photography, lighting, color, atmosphere, continuity, and critical constraints;
- emit a compact backend-neutral `BackendPrompt.compiled_prompt`;
- apply an explicit backend/model prompt budget policy;
- remove exact duplicates, semantic duplicates, non-visual metadata, traces, fingerprints, class names, empty fields, and internal technical text from the compiled prompt;
- retain traceability through source fields without copying trace metadata into the prompt text;
- produce deterministic fingerprints from canonical prompt, trace, policy, and metrics.

`ComfyUIAdapter` MUST prefer `BackendPrompt.compiled_prompt` when present and preserve legacy instruction joining only as a compatibility fallback for older `BackendPrompt` instances.

`ComfyUIBackend` MUST surface backend failures with useful error categories while preserving its existing runtime API.

## Consequences

- FLUX receives compact operational prompts instead of serialized semantic contract material.
- Traceability remains available through `BackendPrompt.trace`, not through visible prompt text.
- Prompt budget policy becomes explicit and testable.
- Backend adapters remain non-cognitive and do not decide visual meaning.
- ComfyUI execution errors such as prompt length, OOM, missing models, invalid workflows, and node errors become diagnosable by callers.

## Validation

- Unit suite: `python -m unittest discover`.
- Compilation: `python -m compileall app tests certification`.
- Whitespace validation: `git diff --check`.
- Real ComfyUI validation at 1080x1920 using the official vertical profile completed successfully with one generated image.

