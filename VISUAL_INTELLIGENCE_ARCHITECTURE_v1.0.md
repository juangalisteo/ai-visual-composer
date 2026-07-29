# Visual Intelligence Architecture v1.0

Status: Frozen

Project: AI Visual Composer

This document is the official specification of Visual Intelligence Architecture v1.0 for the Image Runtime. It consolidates the canonical contracts, flow, responsibilities, invariants, and architectural decisions accepted through IP3.0.

## Objectives

Visual Intelligence v1.0 provides a deterministic intelligence layer for the Image Pipeline. Its purpose is to preserve Visual Truth 2.0, analyze it, reason over it, synthesize a canonical effective brief, preserve traceability, and pass resolved visual information to cinematic direction, prompt translation, backend adaptation, and image generation without reintroducing legacy or transitional runtime contracts.

The architecture is designed to:

- keep Visual Truth 2.0 as the only operational storyboard visual contract;
- keep runtime execution separate from visual reasoning;
- keep Prompt Translation as deterministic translation, not intelligence;
- keep backend adapters as technical adaptation, not interpretation;
- keep Visual Quality as result validation, not creative correction;
- preserve deterministic fingerprints and traceability across the full owned path.

## Principles

- Visual Intelligence owns visual analysis, reasoning, synthesis, conflict reporting, and trace construction.
- Runtime coordinates already resolved information and does not create visual intelligence.
- Cinematic Direction consumes `EffectiveVisualBrief` and produces passive direction contracts.
- Prompt Translator consumes resolved semantic and cinematic information and produces `BackendPrompt`.
- Backend Adapter consumes `BackendPrompt` and produces backend-specific payloads.
- ComfyUI backend executes the payload and does not interpret narrative, visual truth, or cinematic intent.
- Visual Quality validates generated assets and does not modify prompts, runtime, backend payloads, or creative decisions.

## Canonical Runtime Flow

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
  -> ImagePromptSystem cinematic operational identity
  -> ComfyUIBackend
  -> Visual Quality, when enabled
  -> GenerationResultAdapter
  -> ImageManifestWriter
```

## Canonical Contracts

The authorized Image Runtime contracts after IP3.0 are:

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

`VisualSynthesisResult` is the certified runtime visual entry point. It contains the effective brief, conflict report, trace, findings, status, schema version, version, and deterministic fingerprint.

## Contract Ownership

`StoryboardScene` belongs to the visual generation domain and represents Visual Truth 2.0 at storyboard scene level.

`VisualAnalysisResult`, `VisualReasoningResult`, `VisualConflictReport`, `EffectiveVisualBrief`, `VisualIntelligenceTrace`, and `VisualSynthesisResult` belong to Visual Intelligence.

`CinematicDirectionSet` belongs to Cinematic Direction and aggregates the six specialized direction contracts.

`BackendPrompt` belongs to Prompt Translation and remains backend-neutral.

Backend payload contracts belong to backend adapters.

## Responsibilities

### StoryboardSceneAdapter

The adapter converts raw storyboard scene dictionaries into `StoryboardScene` without interpretation, creative enrichment, or prompt generation.

### Visual Analysis

Visual Analysis inspects Visual Truth, resolves visual semantics, resolves visual priority, records findings, and produces `VisualAnalysisResult`.

### Visual Reasoning

Visual Reasoning consumes `VisualAnalysisResult`, resolves scene intent, visual strategy, and sequence continuity, then produces `VisualReasoningResult`.

### Visual Synthesis

Visual Synthesis consumes analysis and reasoning, resolves conflicts, synthesizes `EffectiveVisualBrief`, builds `VisualIntelligenceTrace`, and produces `VisualSynthesisResult`.

### Cinematic Direction

Cinematic Direction consumes `EffectiveVisualBrief` and produces `CinematicDirectionSet` by resolving photography, lighting, composition, color, movement, and continuity directions. It does not generate prompts, payloads, images, or backend-specific information.

### Prompt Translation

Prompt Translation consumes `VisualSynthesisResult` or canonical `EffectiveVisualBrief`, optionally with `CinematicDirectionSet`, and produces `BackendPrompt`. It translates and normalizes existing resolved information; it does not improve, invent, reinterpret, or recalculate visual intelligence.

### Backend Adaptation

Backend adapters consume `BackendPrompt` and produce backend-specific payload contracts. They do not consume Visual Truth, Visual Intelligence, Cinematic Direction internals, runtime, workflows, or manifests directly.

### Image Runtime

`ImageBuilder` coordinates the image path as the public runtime facade. It builds `VisualSynthesisResult`, resolves cinematic direction, translates prompts, adapts backend payloads, invokes the backend, applies Visual Quality when enabled, adapts generation results, and writes the image manifest.

### Visual Quality

Visual Quality validates generated assets and controls optional retry policy. It does not modify prompts, backend payloads, Visual Truth, Visual Intelligence, cinematic direction, or runtime decisions.

## Invariants

- Visual Truth 2.0 is the only operational storyboard visual source.
- `subject`, `action`, `setting`, `visual_idea`, and `legacy_visual_idea` are not operational Image Runtime contracts.
- `RuntimeCognitiveAdapter` is retired.
- `app.visual_direction` is retired.
- `VisualBriefTrace` is retired.
- `VisualDirectionConflict` is retired.
- Runtime `source_id` and `source_version` bridge fields are retired from `EffectiveVisualBrief`, `BackendPrompt`, and backend payloads.
- `EffectiveVisualBrief` has exactly one canonical class definition.
- `VisualSynthesisResult` is the certified runtime visual entry point.
- Prompt Translation, Backend Adapter, and Visual Quality must not run Visual Analysis, Visual Reasoning, or Visual Synthesis.
- The same deterministic input must produce stable fingerprints across Visual Intelligence, Cinematic Direction, Prompt Translation, and Backend Adapter payload construction.

## Traceability

Traceability is preserved through:

- `SourceReference`
- `VisualIntelligenceEvidence`
- `VisualIntelligenceFinding`
- `ResolutionTraceEntry`
- `SpecializedTrace`
- `VisualIntelligenceTrace`
- `BackendPromptTrace`
- `BackendAdapterTrace`
- deterministic fingerprints on canonical contracts

Traceability must identify source fields, transformations, responsible components, and output paths where applicable.

## Fingerprints

Fingerprints are deterministic SHA-256 hashes over canonical contract representations. They must exclude volatile runtime state, local paths where inappropriate, timestamps, logs, backend execution side effects, and generated media bytes unless a contract explicitly owns that data.

## ADR Consolidation

The following architectural decisions are consolidated into Visual Intelligence Architecture v1.0:

- ADR-001: Canonical `EffectiveVisualBrief`
- ADR-002: Canonical vs Transitional Components
- ADR-003: Visual Intelligence Governs Runtime
- ADR-004: Certified Visual Intelligence Pipeline
- ADR-005: Performance Certification Baseline
- ADR-006: Transitional Components Retirement

ADR-006 is the final IP3.x decision that retires transitional runtime components and confirms the canonical runtime path.

## Retired Components

The following components are retired from the Image Runtime:

- `RuntimeCognitiveAdapter`
- `app.visual_direction`
- `VisualBriefTrace`
- `VisualDirectionConflict`
- embedded historical `visual_brief` runtime bridge fields
- runtime `source_id` and `source_version` bridge fields in `EffectiveVisualBrief`, `BackendPrompt`, and backend payloads

Passive source provenance metadata in Visual Bible, Narrative Reading, or Intention representation systems is outside this retirement unless used as an Image Runtime compatibility bridge.

## Boundary Rules

- Visual Intelligence may analyze, reason, synthesize, report conflicts, and build traces.
- Cinematic Direction may resolve cinematic direction from `EffectiveVisualBrief`.
- Prompt Translator may translate resolved information into backend-neutral prompt instructions.
- Backend Adapter may adapt backend-neutral instructions to provider payloads.
- Runtime may coordinate the pipeline and record metadata.
- Visual Quality may validate generated assets and apply controlled retry policy.

No layer may perform the responsibility of a downstream or upstream layer.

## Evolution Rules

Visual Intelligence Architecture v1.0 is frozen. Future work may extend capabilities around the frozen architecture, but canonical contract changes require an explicit IP4.x architectural cycle.

Any future compatibility bridge must have:

- a documented owner;
- a removal condition;
- explicit isolation tests;
- an ADR or roadmap entry explaining why it is necessary.

## Certification Status

Visual Intelligence v1.0 is certified by:

- runtime certification tests;
- performance certification tests;
- full unit test suite;
- Python compilation;
- `git diff --check`;
- dependency and obsolete-reference audit;
- ADR consolidation;
- public architecture documentation.

## Official Status

Visual Intelligence Architecture v1.0 is frozen.

ARCHITECTURE FROZEN
