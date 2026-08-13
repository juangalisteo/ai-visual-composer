# Architecture

# AI Visual Composer

Professional AI Visual Generation Platform

This document describes the official stable V.1 architecture of AI Visual Composer: the Visual Intelligence image runtime and the stabilized video composition core.

The frozen Visual Intelligence specification is published in `docs/architecture/VISUAL_INTELLIGENCE_ARCHITECTURE_v1.0.md`.

## Overview

AI Visual Composer exposes the image-oriented product entry through `python main.py`. The console also shows `Vídeo` as a future product pipeline, but that separate product pipeline is not available yet. The repository includes a stabilized profile-driven FFmpeg video composition core used by the current full project generation mode. The system separates configuration, asset selection, temporal operation building, FFmpeg graph generation, command planning, command execution, and output validation.

The architecture follows this flow:

```text
Configs
  -> Loaders
  -> Selectors
  -> Builders
  -> Graph Builders
  -> FilterPipeline
  -> CommandPlanBuilder
  -> CommandBuilder
  -> VideoBuilder
  -> Runner
  -> VideoValidator
```

## Configs

Configs are typed configuration objects that represent the video profile after parsing and validation.

Current video config areas include:

- Motion
- Transitions
- Overlays
- Visual Effects
- Fade
- Subtitles
- Validation
- Video encoding
- Audio encoding

Configs define what is enabled and which values are valid. They are the contract between the external profile and the engine.

## Loaders

Loaders read raw profile dictionaries and create config objects.

Responsibilities:

- read sections from the selected profile;
- apply default values;
- normalize primitive values;
- create typed config objects;
- let config validation reject invalid values.

Examples:

- `MotionConfigLoader`
- `TransitionConfigLoader`
- `OverlayConfigLoader`
- `VisualEffectConfigLoader`
- `FadeConfigLoader`
- `SubtitleConfigLoader`
- `ValidationConfigLoader`

## Selectors

Selectors choose profile-defined assets or behaviors.

Responsibilities:

- implement sequence or random selection modes;
- respect profile weights;
- optionally avoid repeats;
- return only values available in the active config.

Examples:

- `MotionSelector`
- `TransitionSelector`
- `OverlaySelector`
- `VisualEffectSelector`

The shared asset selector infrastructure is used by temporal audiovisual layers while preserving semantic wrappers for overlays and visual effects.

`OverlaySelector` has overlay-specific category distribution state. It applies per-video category cooldown only to overlay category selection. The shared `AssetSelector` remains unchanged and `VisualEffectSelector` does not inherit overlay category cooldown behavior.

## Builders

Builders convert selected configuration into render operations.

Responsibilities:

- validate operation-level inputs;
- apply probability when configured;
- select assets;
- calculate durations;
- register auxiliary FFmpeg inputs;
- preserve input positions for repeated assets;
- build operation dictionaries consumed by graph builders.

Examples:

- `MotionBuilder`
- `TransitionBuilder`
- `OverlayBuilder`
- `VisualEffectBuilder`

Overlay and visual effect builders share temporal asset infrastructure, but remain separate public components.

`OverlayBuilder.reset()` also resets overlay category distribution state when the selector supports it. This keeps overlay category cooldown scoped to the current video build and prevents persistence between projects.

## Graph Builders

Graph builders produce FFmpeg filter graph fragments for one stage of the pipeline.

Responsibilities:

- receive a graph context;
- append filter graph parts;
- update the current video stream;
- preserve stream metadata required by later stages;
- return a graph result.

Current graph stages:

- `MotionGraphBuilder`
- `TransitionGraphBuilder`
- `OverlayGraphBuilder`
- `VisualEffectGraphBuilder`
- `FadeGraphBuilder`
- `SubtitleGraphBuilder`

Overlay and visual effect graph builders share layer composition infrastructure through `LayerCompositor`.

`OverlayGraphBuilder` keeps the existing `repeat_mode="interval"` behavior. Each interval can request a new overlay selection, so weighted thematic overlay categories and cooldown can operate without changing FFmpeg graph construction.

## FilterPipeline

`FilterPipeline` executes graph builders in the explicit pipeline order:

```text
Motion
  -> Transitions
  -> Overlays
  -> Visual Effects
  -> Fade
  -> Subtitles
```

Responsibilities:

- run each graph stage;
- carry forward the graph state;
- refresh layer input indexes when overlay or visual effect builders register new inputs;
- produce the final filter parts, current stream, layer streams, and context.

The order is fixed in the current core and is not profile-configurable.

## CommandPlanBuilder

`CommandPlanBuilder` creates the structured FFmpeg command plan.

Responsibilities:

- assemble image inputs;
- include audio input;
- include overlay inputs;
- include visual effect inputs;
- apply loop behavior for auxiliary video inputs;
- attach `filter_complex`;
- define output maps;
- define codec and container options;
- preserve render duration.

This layer keeps planning separate from command serialization.

## CommandBuilder

`CommandBuilder` serializes the command plan into the final FFmpeg command list.

Responsibilities:

- convert planned inputs into FFmpeg arguments;
- add `-filter_complex`;
- map `[vout]`;
- map audio;
- add video and audio codec settings;
- add output options;
- return the command consumed by the runner.

## VideoBuilder

`VideoBuilder` is the public facade for video rendering.

Public API:

```python
VideoBuilder().build(
    audio_path=None,
    subtitle_path=None,
    images_manifest_path=None,
    output_path=None,
)
```

Responsibilities:

- prepare build context;
- create pipeline components;
- create `FilterContext`;
- build render artifacts;
- run FFmpeg;
- validate output;
- return the generated output path.

Supporting components:

- `VideoBuildContextFactory`
- `VideoComponentFactory`
- `VideoFilterContextFactory`
- `VideoRenderService`

## Runner

`Runner` executes the final FFmpeg command.

Responsibilities:

- receive a fully built command list;
- execute FFmpeg through the process layer;
- surface execution errors to the caller.

The runner is intentionally small in the current core.

## VideoValidator

`VideoValidator` checks the generated output after rendering.

Responsibilities:

- confirm that the output file exists;
- probe the rendered duration;
- compare generated duration with expected duration;
- enforce the configured validation tolerance.

## Data Flow

```text
Profile JSON
  -> VideoConfigLoader
  -> VideoConfig
  -> VideoBuildContext
  -> VideoBuildComponents
  -> FilterContext
  -> FilterPipeline
  -> filter_complex
  -> CommandPlan
  -> FFmpeg command
  -> Runner
  -> VideoValidator
  -> Output video
```

## Image Component Runtime

Script generation is guarded before runtime propagation. Raw LLM responses are parsed into a structured `ScriptGenerationResult`, validated, and only the `script` field may continue to voice, subtitles, storyboard, Visual Intelligence, Prompt Translation, images, or video. Invalid conversational output stops the pipeline with `INVALID_SCRIPT_OUTPUT`.

The Image Component uses a single cinematic runtime. It is part of the image generation path, not the video render core.

Current image flow:

```text
Visual Truth 2.0 storyboard scene
  -> StoryboardSceneAdapter
  -> VisualAnalysisResult
  -> VisualReasoningResult
  -> VisualConflictReport
  -> EffectiveVisualBrief
  -> VisualIntelligenceTrace
  -> VisualSynthesisResult
  -> CinematicDirectionOrchestrator
  -> CinematicDirectionSet
  -> PromptTranslator
  -> BackendPrompt
  -> ComfyUIAdapter
  -> ImagePromptSystem cinematic operational identity
  -> ComfyUIBackend
  -> Visual Quality, when enabled
  -> GenerationResultAdapter
  -> ImageManifestWriter
```

Responsibilities:

- produce storyboard scenes using Visual Truth 2.0 as the primary visual contract;
- analyze, reason, and synthesize Visual Truth through the canonical Visual Intelligence contracts;
- resolve cinematic direction deterministically;
- translate the effective brief and cinematic directions into compact `BackendPrompt` semantic compilation;
- adapt `BackendPrompt` to the configured backend payload;
- generate images through the backend;
- validate generated assets through Visual Quality when enabled;
- write the approved asset into the image manifest.

`ImageBuilder` coordinates the component as the public facade. It no longer selects between a legacy runtime and a cinematic runtime. The prompt sent to ComfyUI is produced from `BackendPrompt.compiled_prompt` through the backend adapter and then enriched only with the stable operational cinematic identity used by the Image Component. Prompt Translation keeps visual intent compact under the active backend/model budget while preserving traceability outside the prompt text. After generation, Visual Quality can validate the asset when enabled, the result is adapted into the current generation contract, and `ImageManifestWriter` persists the manifest consumed by downstream video assembly.

V.1 includes passive evidence persistence and OVB-001 benchmark infrastructure. These packages observe or benchmark the image path; they must not become a parallel runtime, must not modify Visual Intelligence decisions, and must not rewrite prompts, backend payloads, workflows, manifests, or generated creative intent.

Current Visual Quality checks are bounded validation contracts. Apart from artifact integrity checks over local asset files, named checks such as text, logo, face, anatomy, wardrobe, object, style, lighting, or continuity checks consume explicit validation signals supplied through asset metadata or validation context. They do not currently implement independent OCR, logo recognition, face analysis, anatomy analysis, object detection, or pixel-level visual inference.

The Image Component does not modify Motion, Transitions, Overlays, Visual Effects, Fade, Subtitles, FilterPipeline, CommandPlanBuilder, CommandBuilder, VideoBuilder, Runner, or VideoValidator.

## Console And Pipeline Modes

The current console entry is `python main.py`.

The first menu is:

```text
AI VISUAL COMPOSER

1. Imagen
2. Vídeo
```

`Imagen` is available. `Vídeo` remains visible but unavailable as a separate future product pipeline.

Current execution modes after selecting `Imagen`:

- `Proyecto completo`: Script -> Voice -> Audio -> Subtitles -> Storyboard -> Images -> Video.
- `Solo guion`: Script -> stop.
- `Solo audio`: Script -> Voice -> Audio -> stop.
- `Audio + subtítulos`: Script -> Voice -> Audio -> Subtitles -> stop.
- `Audio + subtítulos + storyboard`: Script -> Voice -> Audio -> Subtitles -> Storyboard -> stop.

`RunController` writes the selected profile, mode, subtitle config, voice config, music option, overlay option, project name, and clear-output option to environment variables consumed by the runtime.

## Profile Control

Profiles control the current visual behavior:

- module activation;
- resolution;
- FPS;
- subtitle styling;
- motion options;
- transition types;
- transition duration;
- overlay directory and behavior;
- visual effect directory and behavior;
- opacity;
- blend mode;
- repeat mode;
- probability;
- loop behavior;
- fade behavior;
- codecs and encoding options;
- validation tolerance.

The core does not introduce hidden visual defaults beyond documented loader defaults.

## Overlays

Smart overlays are controlled through the console only for `Proyecto completo`.

Current runtime flow:

```text
input/tema.txt
  -> OverlayFolderResolver.discover_valid_folders()
  -> OverlayFolderResolver.resolve_categories()
  -> OverlayCategoryResolution
  -> VideoBuildContextFactory
  -> OverlayConfig.folders + OverlayConfig.folder_weights
  -> OverlaySelector
  -> OverlayCategoryDistributionPolicy
  -> selected overlay folder for the interval
  -> existing MP4 file selection
```

The resolver returns:

- `primary`: one thematic category or `None`;
- `secondary`: zero or more additional thematic categories.

All category names are validated against real folders discovered from `assets/videos/overlays/`. The resolver does not receive `Light Leaks` as a thematic category. `VideoBuildContextFactory` adds `Light Leaks` as neutral fallback when available.

Current weighting policy:

- primary category: `3.0`;
- secondary categories: `2.0`;
- `Light Leaks`: `1.0`.

Cooldown policy:

- lives only in memory;
- belongs to `OverlaySelector`;
- remembers the previous overlay category;
- removes that category from the next weighted choice when alternatives exist;
- does not create round-robin or fixed alternation;
- resets through `OverlayBuilder.reset()`;
- does not affect `VisualEffectSelector`.

MP4 file selection remains the existing selector behavior: `avoid_repeats=True` prevents only immediate repetition of the same asset when alternatives exist.

If no thematic category is valid, `NONE -> Light Leaks` is used when the neutral folder exists. If there is no valid thematic category and no neutral fallback, overlays are disabled safely in memory.

## Music

Music is selected from `assets/music/` when the user enables random music. The current console option is:

```text
MÚSICA

1. Sin música
2. Aleatoria
```

The existing `MusicSelector` selects from available music categories and does not require the user to choose a category manually in the current console flow.

## External Runtimes

The current local LLM provider is Ollama:

```text
provider: ollama
model: qwen3:14b
API: http://localhost:11434/api/generate
```

Normal startup requires:

```bash
ollama serve
```

The current image backend expects ComfyUI to run as an external local runtime using:

```bat
cd ComfyUI
.\run_nvidia_gpu.bat
```

AI Visual Composer then starts from the project root:

```bash
python main.py
```

## Current Core Status

The current core is functional and stable as AI Visual Composer V.1.

Current restoration point:

```text
PR1
```

`PR1` is the first official restoration point inside `V.1`.

Validated areas:

- Motion
- Transitions
- Overlays
- Visual Effects
- Fade
- Subtitles
- FilterPipeline
- CommandPlanBuilder
- CommandBuilder
- VideoBuilder
- Runner
- VideoValidator
