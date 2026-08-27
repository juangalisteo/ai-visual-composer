# Architecture

# AI Visual Composer

Professional AI Visual Generation Platform

This document describes the current V2.0 architecture of AI Visual Composer.

V2.0 is organized around three product entries:

```text
AI VISUAL COMPOSER

1. Guion
2. Imagen
3. Video
```

The architecture remains profile-driven and locally executed. It separates console selection, runtime orchestration, script preparation, storyboard construction, image generation, image-to-video generation, and final FFmpeg composition.

## High-Level Flow

```text
Console
  -> RunController
  -> Environment runtime options
  -> app.core.start.iniciar()
  -> Component orchestration
  -> Builders
  -> Manifests
  -> Output artifacts
```

The console does not generate media directly. It selects the product entry, mode, profile, voice, subtitles, music, overlays, project name, and output reset policy. Runtime execution is delegated to `app.core.start`.

## Product Entries

### Guion

Guion is the script-centered entry.

Responsibilities:

- read manual script input from `input/guion.txt`;
- support script-first routes toward Imagen or Video;
- support design routes toward Imagen or Video;
- preserve the selected destination and runtime mode.

Validated V2.0 route families:

```text
Guion -> Imagen
Guion -> Video
Guion -> Diseno -> Imagen
Guion -> Diseno -> Video
```

### Imagen

Imagen is the image-centered entry.

Responsibilities:

- execute script, voice, audio, subtitles, storyboard, image generation, and final video composition according to selected mode;
- build image manifests;
- preserve Visual Truth evidence for image generation;
- produce final video in complete mode through the established FFmpeg composition core.

### Video

Video is the video-centered entry.

Responsibilities:

- execute partial audio/subtitle/storyboard modes;
- execute complete Video mode with image generation, I2V clip generation, and final composition;
- generate `video_clips_manifest.json`;
- produce I2V clips through the video component backend;
- compose the final video through the FFmpeg video core with ping-pong I2V looping and Motion over generated clips.

## Modes

Validated modes for Imagen and Video:

```text
Proyecto completo
Solo audio
Audio + subtitulos
Audio + subtitulos + storyboard
```

Mode behavior:

```text
Solo audio:
Script -> Voice -> Audio -> stop

Audio + subtitulos:
Script -> Voice -> Audio -> Subtitles -> stop

Audio + subtitulos + storyboard:
Script -> Voice -> Audio -> Subtitles -> Storyboard -> stop

Proyecto completo, Imagen:
Script -> Voice -> Audio -> Subtitles -> Storyboard -> Images -> Video

Proyecto completo, Video:
Script -> Voice -> Audio -> Subtitles -> Storyboard -> Images -> I2V clips -> Video
```

## Inputs

Current input files:

```text
input/tema.txt
input/guion.txt
input/guion_imagen.txt
input/guion_video.txt
```

Input ownership:

- `input/tema.txt`: generated script topic.
- `input/guion.txt`: manual Guion source.
- `input/guion_imagen.txt`: design source for Diseno -> Imagen.
- `input/guion_video.txt`: design source for Diseno -> Video.

## Outputs

The current output layout is grouped by product entry:

```text
output/guion/
output/imagen/
output/video/
```

Project outputs may contain:

```text
scripts/
audio/
subtitles/
storyboard/
images/
images/evidence/
video_clips/
video/
```

Important manifests:

- `storyboard/storyboard.json`
- `images/images_manifest.json`
- `video_clips/video_clips_manifest.json`

## Script Layer

The script layer is implemented in `app/modules/script/`.

Responsibilities:

- prepare script input;
- generate or load script text according to runtime source;
- enforce script output contract validation;
- keep script handling independent from image and video rendering.

Key elements:

- `ScriptPreparationService`
- `ScriptOperation`
- `ScriptBuilder`
- `ScriptOutputValidator`

## Storyboard Layer

Storyboard generation is implemented in `app/modules/storyboard/`.

Responsibilities:

- parse script content into storyboard scenes;
- validate storyboard structure;
- preserve Visual Truth 2.0 fields;
- provide scene data to image and video generation.

The Image Pipeline uses Visual Truth as its operational visual contract.

## Image Runtime

The image runtime is implemented primarily through:

- `app/modules/images/`
- `app/domain/adapters/storyboard_scene_adapter.py`
- `app/visual_intelligence/`
- `app/prompt_translation/`
- `app/modules/images/backends/comfyui_backend.py`

Flow:

```text
StoryboardScene
  -> StoryboardSceneAdapter
  -> Visual Analysis
  -> Visual Reasoning
  -> Visual Synthesis
  -> EffectiveVisualBrief
  -> Cinematic Direction
  -> Prompt Translation
  -> BackendPrompt
  -> ComfyUI
  -> images_manifest.json
```

Evidence may be persisted under:

```text
images/evidence/
```

## Design Runtime

Design routes use manual design inputs and convert them into Visual Truth compatible scenes before invoking image or video generation.

Imagen design path:

```text
input/guion_imagen.txt
  -> ImageDesignPreparationService
  -> ImageDesignVisualTruthAdapter
  -> ImageBuilder
```

Video design path:

```text
input/guion_video.txt
  -> VideoDesignPreparationService
  -> VideoDesignVisualTruthAdapter
  -> ImageBuilder
  -> VideoComponentBuilder
```

## Video Component

The video component lives in:

```text
app/modules/video_component/
```

Responsibilities:

- analyze the source image;
- build motion intent;
- translate visual video intent into backend prompt data;
- adapt requests to ComfyUI I2V;
- persist clip manifests.

The component is used by complete Video mode and design-to-video routes.

## FFmpeg Video Composition Core

The final video composition core lives in:

```text
app/modules/video/
```

Composition order:

```text
Motion
  -> Transitions
  -> Overlays
  -> Visual Effects
  -> Fade
  -> Subtitles
```

Main responsibilities:

- load video profile configuration;
- select temporal assets;
- build FFmpeg filter graph stages;
- build command plans;
- serialize FFmpeg commands;
- execute rendering;
- validate final output.

Key components:

- `VideoBuildContextFactory`
- `VideoComponentFactory`
- `VideoFilterContextFactory`
- `VideoRenderService`
- `VideoBuilder`
- `CommandPlanBuilder`
- `CommandBuilder`
- `Runner`
- `VideoValidator`

## Motion

Motion is generated as part of the FFmpeg composition graph. It applies scene-level movement according to profile configuration and available media, including both still images and generated I2V clips.

## I2V

I2V generation is part of the Video product entry and design-to-video route.

Evidence is stored through:

```text
video_clips/video_clips_manifest.json
video_clips/scene_*.mp4
```

The current backend is ComfyUI using the configured Wan I2V workflow when available locally.

Generated I2V clips are reused by the FFmpeg composition layer. When a scene requires more time than the source clip duration, composition builds a forward/reverse ping-pong loop, avoids duplicated endpoint frames, applies Motion over the prepared clip stream, and trims the result to the exact scene duration.

## Music, Overlays, Transitions, Visual Effects

Music:

- selected when enabled by runtime options;
- sourced from `assets/music/`.

Overlays:

- discovered under `assets/videos/overlays/`;
- selected with semantic category resolution;
- use `Light Leaks` as neutral fallback when appropriate;
- apply weighted distribution and category cooldown.

Transitions and Visual Effects:

- configured through video profiles;
- applied by the FFmpeg composition layer;
- kept separate from overlays.

## Profiles And Configuration

Configuration is profile-driven.

Relevant profile families:

```text
config/profiles/guion/
config/profiles/instagram/
config/profiles/youtube/
config/profiles/diseno/imagen/
config/profiles/diseno/video/
config/profiles/video/
```

Runtime selection is propagated through environment variables prepared by `main.py` from `RunController` output.

## Baseline Validation

V2.0 is supported by three baselines:

```text
validation/v2_0/guion/
validation/v2_0/imagen/
validation/v2_0/video/
```

Validated execution count:

- Guion: 20
- Imagen: 8
- Video: 8
- Total: 36

Each baseline contains:

- `report.md`
- `metrics.json`
- `metrics.csv`
- `inventory.json`
- `samples_manifest.json`
- `samples/`
- `charts/`

## Known V2.x Work

The following items are known future optimization work, not V2.0 blockers:

- further Motion optimization;
- professional overlay refinement;
- transition improvement;
- deeper subtitle optimization;
- subtitle synchronization with real voice/silence timing;
- I2V quality vs VRAM evaluation;
- processing time optimization;
- PipelineSummary timing persistence.
