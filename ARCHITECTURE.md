# Architecture

# AI Video Composer

A profile-driven AI video composition engine.

This document describes the current architecture of the video composition core.

## Overview

AI Video Composer builds a video through a profile-driven FFmpeg pipeline. The system separates configuration, asset selection, temporal operation building, FFmpeg graph generation, command planning, command execution, and output validation.

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

## Image Prompt Direction

Visual Director is part of the image generation path, not the video render core.

Current image prompt flow:

```text
Storyboard scene
  -> visual_idea and scene text
  -> VisualDirectionContext
  -> VisualDirector
  -> DirectedPrompt
  -> SafeVisualPolicy
  -> ImageBuilder
  -> image backend prompt injection
  -> image manifest
```

Responsibilities:

- enrich scene prompts with composition, camera, lighting, color, orientation, realism, detail, and negative prompt guidance;
- preserve scene meaning and the original `visual_idea`;
- enforce safe-for-work visual policy before backend prompt injection;
- produce inspectable prompt metadata in the image manifest;
- remain backend-neutral and avoid any direct ComfyUI dependency;
- fall back to the legacy prompt if prompt direction fails.

`SafeVisualPolicy` is applied globally inside `ImageBuilder`, after Visual Director or legacy prompt construction and before the image backend receives the prompt. It appends safe clothing guidance for human subjects, merges the global negative prompt, rewrites unsafe positive prompt terms into fully clothed equivalents, validates the safe positive prompt, and records policy metadata in the image manifest.

Visual Director does not modify Motion, Transitions, Overlays, Visual Effects, Fade, Subtitles, FilterPipeline, CommandPlanBuilder, CommandBuilder, VideoBuilder, Runner, or VideoValidator.

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

## Current Core Status

The current core is completed and validated as `v1.0.0`.

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
