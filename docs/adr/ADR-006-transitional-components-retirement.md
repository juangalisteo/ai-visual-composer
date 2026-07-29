# ADR-006 - Transitional Components Retirement

## Status

Accepted

## Context

IP3.0-6 certified `VisualSynthesisResult` as the Image Runtime visual source of truth.
IP3.0-7 certified the Visual Intelligence performance baseline.

The transitional compatibility layer existed to bridge earlier runtime contracts while Visual Intelligence reached certification. After certification, those transitional contracts no longer owned runtime behavior and increased the risk of duplicate visual paths.

## Decision

The Image Runtime SHALL use the canonical Visual Intelligence path:

```text
StoryboardScene
  -> StoryboardSceneAdapter
  -> VisualAnalysisResult
  -> VisualReasoningResult
  -> VisualConflictReport
  -> EffectiveVisualBrief
  -> VisualIntelligenceTrace
  -> VisualSynthesisResult
  -> CinematicDirectionSet
  -> PromptTranslator
  -> BackendPrompt
  -> ComfyUIAdapter
  -> ComfyUIPayload
```

The following transitional runtime components are retired:

- `RuntimeCognitiveAdapter`
- `app.visual_direction`
- `VisualBriefTrace`
- `VisualDirectionConflict`
- embedded historical `visual_brief` runtime bridge fields
- runtime `source_id` and `source_version` bridge fields in `EffectiveVisualBrief`, `BackendPrompt`, and backend payloads

The following contracts are the authorized Image Runtime contracts after this ADR:

- `StoryboardScene`
- `VisualAnalysisResult`
- `VisualReasoningResult`
- `VisualConflictReport`
- `EffectiveVisualBrief`
- `VisualIntelligenceTrace`
- `VisualSynthesisResult`
- `CinematicDirectionSet`
- `BackendPrompt`
- backend-specific payload contracts produced by backend adapters

## Consequences

- Runtime no longer builds or consumes transitional visual direction contracts.
- Cinematic direction consumes canonical `EffectiveVisualBrief` directly.
- Prompt translation consumes canonical `EffectiveVisualBrief` or `VisualSynthesisResult`.
- Backend adaptation consumes `BackendPrompt` without historical source bridge fields.
- Traceability remains available through Visual Intelligence traces, prompt traces, backend prompt fingerprints, and backend payload fingerprints.
- Passive source provenance fields in non-runtime representation systems remain outside this retirement unless they are used as Image Runtime compatibility bridges.

## Compliance

New Image Runtime development MUST NOT depend on retired transitional contracts.

Any future compatibility bridge MUST have:

- a documented owner;
- a removal condition;
- explicit tests proving isolation;
- an ADR or roadmap entry explaining why it is necessary.
