# Roadmap

# AI Visual Composer

Professional AI Visual Generation Platform

This roadmap describes the official stable V.1 baseline and the future lines of work that may be opened only with explicit owner approval.

## Current Stable Baseline

General system version:

```text
V.1
```

State:

```text
STABLE
```

Current restoration point:

```text
PR1
```

`V.1` identifies the general system version. `PR1` identifies the first official restoration point inside `V.1`.

Official restoration structure:

```text
V.1
|
└── PR1 - STABLE
```

Future stable restoration points inside `V.1` may be named `PR2`, `PR3`, `PR4`, and so on. `V.2` must only be created after an explicit owner decision.

## Current Working Capabilities

Current console entry:

```text
python main.py
```

Current available product entry:

```text
Imagen
```

Current separate future product entry:

```text
Video
```

`Video` remains visible but unavailable as a standalone future product pipeline.

Current execution modes:

- Proyecto completo.
- Solo guion.
- Solo audio.
- Audio + subtitulos.
- Audio + subtitulos + storyboard.

Current full generation flow:

```text
Script
  -> Voice
  -> Audio
  -> Subtitles
  -> Storyboard
  -> Images
  -> Video
```

Current external runtime dependencies:

- Ollama with model `qwen3:14b`.
- ComfyUI using `config/comfyui_flux_workflow_api.json`.
- FFmpeg.
- Edge TTS.

## Current Video Composition Capabilities

The stabilized video composition core includes:

- Motion.
- Transitions.
- Smart thematic Overlays.
- Visual Effects.
- Fade.
- Subtitles.
- FFmpeg command planning.
- FFmpeg command execution.
- Output validation.

Smart overlays currently support:

- dynamic folder discovery under `assets/videos/overlays/`;
- semantic category resolution;
- primary and secondary thematic categories;
- `Light Leaks` as neutral fallback;
- weighted category distribution;
- per-video category cooldown;
- existing MP4 file selection with immediate-repeat avoidance.

## Current Image Runtime Capabilities

The image runtime includes:

- Visual Truth 2.0 storyboard input.
- StoryboardSceneAdapter.
- Visual Analysis.
- Visual Reasoning.
- Visual Synthesis.
- EffectiveVisualBrief.
- VisualIntelligenceTrace.
- Cinematic Direction.
- Prompt Translation.
- BackendPrompt.
- ComfyUIAdapter.
- ComfyUIBackend.
- Visual Quality validation infrastructure.
- Image manifest writing.

## Completed Architectural Work

Completed historical lines:

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
- `IP3.0-3 - Visual Reasoning Layer`
- `IP3.0-4 - Visual Synthesis Layer`
- `IP3.0-5 - Visual Intelligence Runtime Integration`
- `IP3.0-6 - Visual Intelligence Certification`
- `IP3.0-7 - Visual Intelligence Performance Certification`
- `IP3.0-8 - Transitional Component Retirement`
- `IP3.0-9 - Architecture Finalization`
- `IP3.1 - Prompt Translation Correction and Runtime Input Governance`
- `IP3.2 - Script Generation Output Contract and LLM Response Sanitization`
- Post-PR1 development stabilization.
- Current console, script length, music, overlay, visual effects, and documentation refinements.

## Stable Baseline Policy

`PR1` is the current restoration reference for V.1.

If a future change introduces a regression, the system may be restored to `PR1`.

Future stable points may extend the V.1 restoration chain as `PR2`, `PR3`, and later points. Those points must be created only after validation and owner approval.

## Future Product Lines

Future lines remain open and must not start without explicit owner approval:

- Standalone Video Pipeline.
- Thumbnail Generator.
- AI Assistant.
- Multi-layer Rendering.
- New Effects.
- Automation.
- Plugins.
- Additional visual products.

## Deferred Investigations

Potential future investigations must be opened explicitly by the owner and must not modify the stable V.1 baseline without a dedicated task:

- Dedicated handling for subtitles generated from manual scripts.
- Additional semantic music selection.
- Additional overlay distribution strategies.
- Further PromptTranslator optimization based on benchmark evidence.
