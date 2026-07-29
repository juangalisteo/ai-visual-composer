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

Next planned phase:

```text
IP3.0-6 - Visual Intelligence Certification
```

`IP3.0-1` established Visual Intelligence contracts. `IP3.0-2` established isolated Visual Analysis over Visual Truth 2.0. `IP3.0-3` established isolated Visual Reasoning over `VisualAnalysisResult`. `IP3.0-4` established Visual Synthesis and `VisualSynthesisResult` as the passive boundary contract. `IP3.0-5` integrates `VisualSynthesisResult` into the Image Runtime as the visual source of truth before prompt translation.

Planned IP3.x sequence:

- `IP3.0-6 - Visual Intelligence Certification`

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

### Legacy Compatibility Audit

Status:

- Completed after `ADR-001 - Canonical EffectiveVisualBrief`.
- No audited element was proven completely dead.
- No compatibility field was removed in this consolidation.

Architectural Classification:

- `EffectiveVisualBrief`: `CANONICAL`.
- `visual_brief`: `TRANSITIONAL` compatibility field consumed by Visual Direction, Cinematic Direction, Prompt Translator, ImageBuilder, and tests until `IP3.0-5`.
- `source_id`: `TRANSITIONAL` compatibility field consumed by trace, direction, prompt, backend adapter, ImageBuilder, and tests until `IP3.0-5`.
- `source_version`: `TRANSITIONAL` compatibility field consumed by trace, direction, prompt, backend adapter, ImageBuilder, and tests until `IP3.0-5`.
- `VisualBriefTrace`: `TRANSITIONAL` compatibility model consumed by Visual Direction, Prompt Translator, ImageBuilder, cinematic specialization tests, and trace assertions until `IP3.0-5`.
- `VisualDirectionConflict`: `TRANSITIONAL` compatibility model produced by Visual Direction conflict detection and carried by `EffectiveVisualBrief.conflicts` until `IP3.0-5`.

Rule:

- These elements MUST remain available until `IP3.0-5 - Visual Intelligence Runtime Integration` migrates active runtime consumers to the canonical Visual Intelligence trace and conflict model.
- Any removal before `IP3.0-5` is prohibited unless a new audit proves there are no active consumers.
- New development MUST use `CANONICAL` components and MUST NOT introduce new dependencies on `TRANSITIONAL` components.

### Architectural Classification

`CANONICAL`:

- Represents components that are part of the definitive project design.
- Has no planned removal.
- Future evolution MUST build on canonical components.

`TRANSITIONAL`:

- Represents components that remain only to preserve compatibility with consumers not yet migrated.
- Has a temporary lifecycle.
- Has an explicit removal or reevaluation plan.
- MUST NOT be used by new development.
- MUST be reevaluated after `IP3.0-5 - Visual Intelligence Runtime Integration`.

Current classification:

- `EffectiveVisualBrief`: `CANONICAL`.
- `visual_brief`: `TRANSITIONAL`.
- `source_id`: `TRANSITIONAL`.
- `source_version`: `TRANSITIONAL`.
- `VisualBriefTrace`: `TRANSITIONAL`.
- `VisualDirectionConflict`: `TRANSITIONAL`.

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

Previous architecture:

```text
RuntimeCognitiveAdapter
        -> EffectiveVisualBrief compatibility bridge
        -> CinematicDirectionSet
        -> PromptTranslator
        -> Backend Adapter
```

Current architecture:

```text
VisualAnalysisResult
        -> VisualReasoningResult
        -> VisualSynthesisResult
        -> EffectiveVisualBrief
        -> Runtime
        -> PromptTranslator
        -> Backend Adapter
```

Migrated points:

- `ImageBuilder` builds `VisualSynthesisResult` through Visual Analysis, Visual Reasoning, and Visual Synthesis before prompt translation.
- `ImageBuilder` records `VisualSynthesisResult`, `VisualIntelligenceTrace`, and `VisualConflictReport` fingerprints in runtime metadata.
- `PromptTranslator` exposes `translate_visual_synthesis_result` as the runtime entry point for canonical synthesis output.
- Manual runtime construction of `VisualBriefTrace` and manual runtime `EffectiveVisualBrief` fingerprinting were removed from `ImageBuilder`.

Remaining transitional bridges:

- `visual_brief` remains embedded in the canonical `EffectiveVisualBrief` while Cinematic Direction still consumes the historical Visual Direction shape.
- `source_id` and `source_version` remain as runtime trace compatibility fields.
- `VisualBriefTrace` and `VisualDirectionConflict` remain available for Visual Direction consumers until the next migration proves they can be removed.

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
