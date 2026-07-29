# Roadmap

# AI Visual Composer

Professional AI Visual Generation Platform

This roadmap lists future lines of work after `AI Visual Composer v1.0.0`. It does not define dates, commitments, or implementation order.

AI Visual Composer is a modular system where users choose products and the platform selects the appropriate profile, pipeline, registry entry, and visual components. Version 1.0.0 ships the certified Image Pipeline as the first official product pipeline.

## Current Active Development

Current line:

```text
Image Pipeline 3.0
```

Completed:

- `IP2.0-1 - StoryboardScene 2.0`
- `IP2.0-2 - StoryboardSceneAdapter 2.0`
- `QF-0 - Quality Foundation`
- `IP2.0-3 - RuntimeCognitiveAdapter 2.0`
- `IP2.0-4 - Storyboard Visual Truth Source Migration`
- `IP2.0-5 - ImageBuilder Visual Truth Consumer Migration`
- `IP2.0-6 - Narrative Runtime Visual Truth Migration`
- `IP2.0-7 - Generated Storyboard Legacy Field Removal`
- `IP2.0-8 - Legacy Contract Retirement`
- `IP3.0-0 - Visual Intelligence Architecture`
- `IP3.0-1A - Visual Intelligence Core Contracts`
- `IP3.0-1B - Visual Intelligence Specialized Contracts`
- `IP3.0-2 - Visual Analysis Layer`
  - Visual Truth Inspector
  - Visual Semantics Resolver
  - Visual Priority Resolver
  - Visual Analysis Orchestrator
- `IP3.0-3 - Visual Reasoning Layer`
  - Scene Intent Resolver
  - Visual Strategy Resolver
  - Sequence Continuity Resolver
  - Visual Reasoning Orchestrator
- `IP3.0-4 - Visual Synthesis Layer`
  - Visual Conflict Resolver
  - Effective Visual Brief Synthesizer
  - Visual Intelligence Trace Builder
  - Visual Synthesis Orchestrator
- `IP3.0-5 - Visual Intelligence Runtime Integration`
- `IP3.0-6 - Visual Intelligence Certification`
- `IP3.0-7 - Visual Intelligence Performance Certification`
- `IP3.0-8 - Transitional Component Retirement`

Next planned phase:

```text
IP3.0-9 - Final architectural closure
```

`IP3.0-1` established Visual Intelligence contracts. `IP3.0-2` established isolated Visual Analysis over Visual Truth 2.0. `IP3.0-3` established isolated Visual Reasoning over `VisualAnalysisResult`. `IP3.0-4` established Visual Synthesis and `VisualSynthesisResult` as the passive boundary contract. `IP3.0-5` integrates `VisualSynthesisResult` into the Image Runtime as the visual source of truth before prompt translation.

Planned IP3.x sequence:

- Final architectural closure after transitional retirement verification

Do not open Video Pipeline or future visual products until the current Image Pipeline phase is explicitly requested.

## Architectural Decision Record

### ADR-001 - Canonical EffectiveVisualBrief

Decision:

- There is exactly one official `EffectiveVisualBrief` contract.
- Its official location is `app/domain/visual_intelligence.py`.
- Future components MUST consume only the canonical contract.
- Legacy compatibility MAY reexport the canonical contract temporarily.
- Parallel `EffectiveVisualBrief` contract evolution is prohibited.

Rationale:

- `EffectiveVisualBrief` is the semantic boundary between Visual Intelligence and Runtime.
- A single canonical definition preserves Single Source of Truth.
- Runtime Integration must not depend on parallel Visual Direction and Visual Intelligence variants.

### Transitional Runtime Compatibility Status

Status:

- Transitional runtime compatibility has been retired by `ADR-006 - Transitional Components Retirement`.
- `EffectiveVisualBrief` remains the canonical semantic brief contract.
- The Image Runtime no longer depends on the historical Visual Direction package, runtime cognitive adapter, or runtime bridge fields.

Retired runtime compatibility elements:

- `RuntimeCognitiveAdapter`.
- `app.visual_direction`.
- Runtime `VisualBriefTrace`.
- Runtime `VisualDirectionConflict`.
- Embedded historical `visual_brief` bridge data.
- Runtime `source_id` and `source_version` bridge fields in `EffectiveVisualBrief`, `BackendPrompt`, and backend payloads.

Canonical note:

- Passive source provenance metadata with similar field names may still exist in Visual Bible, Narrative Reading, and Intention representation systems. Those fields are not Image Runtime compatibility bridges.

### ADR-002 - Canonical vs Transitional Components

Decision:

- The architecture explicitly distinguishes definitive components from temporary compatibility components.
- `CANONICAL` components represent the final intended design.
- `TRANSITIONAL` components exist only to preserve compatibility during migration.
- `TRANSITIONAL` components MUST NOT be used in new development.
- After `IP3.0-5`, all `TRANSITIONAL` components MUST be reevaluated for removal.

Rationale:

- Active usage does not imply permanent architectural ownership.
- Runtime Integration requires a clear distinction between final contracts and migration bridges.
- Explicit classification prevents new dependencies from forming around temporary compatibility surfaces.

### Runtime Integration

Certified architecture:

```text
StoryboardScene
        -> StoryboardSceneAdapter
VisualAnalysisResult
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

Migrated points:

- `ImageBuilder` builds `VisualSynthesisResult` through Visual Analysis, Visual Reasoning, and Visual Synthesis before prompt translation.
- `ImageBuilder` records `VisualSynthesisResult`, `VisualIntelligenceTrace`, and `VisualConflictReport` fingerprints in runtime metadata.
- `PromptTranslator` exposes `translate_visual_synthesis_result` as the runtime entry point for canonical synthesis output.
- Cinematic Direction consumes canonical `EffectiveVisualBrief` directly.
- Prompt translation emits backend-neutral instructions from canonical `EffectiveVisualBrief` and optional `CinematicDirectionSet`.
- Backend adaptation no longer carries historical source bridge fields.

Rule:

- Runtime MUST treat `VisualSynthesisResult` as the visual source of truth.
- Runtime MUST NOT recalculate visual analysis, reasoning, synthesis, trace, or conflicts after `VisualSynthesisResult` has been produced.

### ADR-003 - Visual Intelligence Governs Runtime

Decision:

- Visual Intelligence is the only source of truth for Runtime visual decisions.
- Runtime consumes `VisualSynthesisResult` as the single visual entry point.
- Runtime executes and propagates resolved information; it does not make visual decisions.
- Prompt translation consumes information derived from `VisualSynthesisResult`.
- Backend adapters receive only resolved backend-neutral prompt information.
- Transitional components remain only while active consumers require them.

Rationale:

- Visual decisions must exist before runtime execution.
- Runtime must remain operational infrastructure, not an intelligence layer.
- `VisualSynthesisResult` already encapsulates analysis, reasoning, conflict resolution, effective brief, and trace.
- Keeping one entry point prevents new parallel contracts from appearing during IP3.x evolution.

### Visual Intelligence Certification

Status:

- `IP3.0-6 - Visual Intelligence Certification` completed.
- The certified runtime entry point is `VisualSynthesisResult`.
- The certified operational path is:

```text
StoryboardScene
        -> VisualAnalysisResult
        -> VisualReasoningResult
        -> VisualConflictReport
        -> EffectiveVisualBrief
        -> VisualIntelligenceTrace
        -> VisualSynthesisResult
        -> ImageBuilder Runtime
        -> PromptTranslator
        -> BackendPrompt
        -> ComfyUIAdapter
        -> ComfyUIPayload
```

Certified guarantees:

- `VisualSynthesisResult` governs the Image Runtime visual path.
- Backend prompt traceability preserves the `EffectiveVisualBrief` fingerprint.
- Backend adapter traceability preserves the `BackendPrompt` fingerprint.
- Repeated execution of the same scene produces stable synthesis, direction, prompt, and payload fingerprints.
- There is a single `EffectiveVisualBrief` class definition.
- No inverse Visual Intelligence runtime adapters exist.
- Prompt, backend, and Visual Quality layers do not run Visual Analysis, Reasoning, or Synthesis.

Remaining transitional components:

- None in the Image Runtime path.

Canonical note:

- `source_id` and `source_version` may still appear in passive Visual Bible, Narrative Reading, and Intention representation layers as source provenance metadata. Those occurrences are not Image Runtime transitional compatibility contracts.

### ADR-006 - Transitional Components Retirement

Decision:

- `RuntimeCognitiveAdapter` is retired from the Image Runtime.
- The temporary `app.visual_direction` compatibility package is retired.
- `VisualBriefTrace` and `VisualDirectionConflict` are retired as runtime compatibility contracts.
- `EffectiveVisualBrief` no longer carries embedded historical `visual_brief`, `source_id`, or `source_version` runtime bridge fields.
- `PromptTranslator`, `BackendPrompt`, `ComfyUIAdapter`, and cinematic direction now consume canonical Visual Intelligence and cinematic contracts directly.

Rationale:

- `IP3.0-6` certified `VisualSynthesisResult` as the runtime visual source of truth.
- `IP3.0-7` certified the performance baseline.
- The transitional bridge had no remaining architectural ownership after runtime certification.
- Removing the compatibility layer reduces duplicate contracts and prevents future dependencies on historical runtime shapes.

Canonical runtime flow:

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

### ADR-004 - Certified Visual Intelligence Pipeline

Decision:

- Visual Intelligence is certified as the source of truth for Image Runtime visual decisions.
- `VisualSynthesisResult` is the certified runtime visual entry point.
- The Image Runtime MUST execute from `VisualSynthesisResult` and MUST NOT introduce parallel visual contracts.
- Traceability MUST preserve the chain from Visual Intelligence to `BackendPrompt` and final backend payload.
- `TRANSITIONAL` components remain isolated until a controlled retirement phase removes or replaces their active consumers.

Rationale:

- Certification demonstrates that the architecture implemented in IP3.x works through the operational image path.
- Deterministic fingerprints make regressions observable.
- Boundary guards prevent Prompt Translation, Backend Adapter, and Visual Quality from becoming intelligence layers.
- Isolated transitional components can now be retired with lower risk.

### Performance Certification

Status:

- `IP3.0-7 - Visual Intelligence Performance Certification` completed.
- Baseline measured on Python `3.13.12`, platform `win32`, Microsoft Windows `10.0.26100`, architecture `X64`.
- Logical processors visible to Python: `24`.
- Processor identifier available to the runtime: `Intel64 Family 6 Model 183 Stepping 1, GenuineIntel`.
- WMI hardware inventory for detailed CPU/RAM names was blocked by local permissions, so the certified baseline records only accessible environment metadata.

Certified baseline:

| Metric | Value |
| --- | --- |
| Iterations | `20` |
| Pipeline mean | `0.0693469499994535` seconds |
| Pipeline min | `0.06658030000107829` seconds |
| Pipeline max | `0.07414040000003297` seconds |
| Pipeline p95 | `0.07070870000097784` seconds |
| Pipeline p99 | `0.07414040000003297` seconds |
| Peak memory max | `593790` bytes |
| Peak memory mean | `581020.4` bytes |
| Objects created mean | `489.2` |
| Fingerprints per medium pipeline | `118` |
| Contracts per medium pipeline | `331` |
| Deterministic payload fingerprints | `1` |

Stage baseline:

| Stage | Seconds | Peak Memory Bytes | Objects Created | Contracts | Fingerprints |
| --- | ---: | ---: | ---: | ---: | ---: |
| Visual Analysis | `0.018471299998054747` | `217036` | `112` | `80` | `62` |
| Visual Reasoning | `0.011861999999382533` | `146599` | `73` | `48` | `38` |
| Conflict Resolution | `0.00017169999773614109` | `4737` | `2` | `2` | `2` |
| Effective Visual Brief Synthesis | `0.0072289000017917715` | `158925` | `27` | `76` | `60` |
| Visual Intelligence Trace | `0.008260400001745438` | `242846` | `6` | `131` | `102` |
| Visual Synthesis Orchestrator | `0.02874850000080187` | `458823` | `36` | `146` | `109` |
| Cinematic Direction | `0.003751700001885183` | `40152` | `95` | `54` | `7` |
| Prompt Translation | `0.005344199998944532` | `146964` | `193` | `128` | `1` |
| Backend Adapter Payload | `0.0006382999999914318` | `26695` | `6` | `3` | `1` |
| Runtime Visual Synthesis Entry | `0.05936169999768026` | `575782` | `194` | `146` | `109` |

Scalability baseline:

| Load | Seconds | Peak Memory Bytes | Objects Created | Contracts | Fingerprints |
| --- | ---: | ---: | ---: | ---: | ---: |
| Small | `0.059425900002679555` | `569606` | `390` | `255` | `99` |
| Medium | `0.06981589999850257` | `575094` | `489` | `331` | `118` |
| Complex | `0.07189529999959632` | `595880` | `489` | `331` | `118` |

Certification scope:

- Performance certification measures Python-side deterministic contract construction, Visual Intelligence orchestration, cinematic direction, prompt translation, backend-neutral prompt generation, and ComfyUI payload adaptation.
- Performance certification does not execute external ComfyUI image generation, GPU inference, model loading, network access, file output, or Visual Quality image inspection.
- Performance certification is a regression baseline, not a hard real-time SLA.

### ADR-005 - Performance Certification Baseline

Decision:

- Visual Intelligence performance MUST be certified with deterministic local benchmark tests before transitional retirement continues.
- The certified baseline MUST include total pipeline time, per-stage timing, memory peak, object creation, contract count, fingerprint count, and determinism of generated payload fingerprints.
- Benchmarks MUST avoid external backend execution so certification remains reproducible without GPU, ComfyUI, model files, or network access.
- Future performance work MUST compare against this baseline before claiming regression or improvement.

Rationale:

- IP3.x introduced multiple deterministic intelligence layers before prompt translation.
- A quantitative baseline prevents performance regressions from being evaluated only by subjective impressions.
- Excluding external backend execution keeps the certification focused on repository-owned code.
- Deterministic fingerprints verify that the benchmarked path is stable across repeated executions.

## Image Enhancement

Future work line.

## Thumbnail Generator

Future work line.

## AI Assistant

Future work line.

## Multi-layer Rendering

Future work line.

## Performance

Future work line.

## New Effects

Future work line.

## Automation

Future work line.

## Plugins

Future work line.

## Testing

Future work line.

## Documentation

Future work line.

## AI Visual Composer Platform

Future platform line covering Product Catalog, Profile System integration, Visual Component Registry, component contracts, product-oriented orchestration, and future Video Pipeline work.
