# AI Visual Composer

**Professional AI Visual Generation Platform**

AI Visual Composer is a local audiovisual generation platform designed to transform scripts, ideas, and visual concepts into structured multimedia content through artificial intelligence.

The system integrates text processing, voice generation, audio, subtitles, storyboard construction, image generation, image-to-video generation, visual intelligence, motion, transitions, overlays, visual effects, and final video composition within a unified workflow.

AI Visual Composer is designed around a modular, profile-driven architecture that keeps each stage of the generation process structured, traceable, configurable, and independently evolvable.

**Current stable version:** `V2.0`

---

## Overview

AI Visual Composer brings the main stages of AI-assisted audiovisual production into a single local system.

Instead of treating image generation, video generation, subtitles, audio, and composition as isolated tools, the platform connects them through a structured production architecture.

The system can process existing scripts, develop content from an idea or topic, generate visual scenes, transform images into video, create synchronized subtitles, and assemble the resulting assets into complete audiovisual projects.

Its architecture is built around four main product components:

```text
AI VISUAL COMPOSER

1. GUION
2. IMAGEN
3. VIDEO
4. STUDIO
```

These components define the core product architecture.

---

## Guion

**Guion** is the script-centered component.

It allows an existing text or complete script supplied by the user to become the source of an audiovisual generation process.

From Guion, the system can process the supplied content toward different visual destinations while preserving the original textual source.

Its purpose is to provide a controlled workflow when the content already exists and the system's role is to transform that content into audiovisual material.

---

## Imagen

**Imagen** is the image-centered component.

It combines content preparation, storyboard generation, structured visual interpretation, prompt translation, and AI image generation.

The visual pipeline is designed to preserve narrative intent while progressively translating it into information suitable for the generation backend.

At a high level:

```text
CONTENT
   ↓
STORYBOARD
   ↓
VISUAL TRUTH
   ↓
VISUAL INTELLIGENCE
   ↓
CINEMATIC DIRECTION
   ↓
PROMPT TRANSLATION
   ↓
IMAGE GENERATION
```

This architecture separates narrative information from backend-specific generation instructions and provides greater control over the visual generation process.

---

## Video

**Video** extends the visual generation architecture into complete audiovisual production.

The system can generate source images, transform them into image-to-video clips, process temporal behavior, and integrate those assets into the final composition.

At a high level:

```text
CONTENT
   ↓
STORYBOARD
   ↓
IMAGE GENERATION
   ↓
IMAGE-TO-VIDEO
   ↓
MOTION
   ↓
COMPOSITION
   ↓
FINAL VIDEO
```

The video architecture supports both generated I2V material and still-image based audiovisual composition.

---

## Studio

**Studio** is the finishing component for externally supplied media.

It accepts either an external MP4 with an authoritative SRT or an MP4 for canonical subtitle preparation, applies the selected Instagram or YouTube profile, and renders the subtitles. Music and INTRO/OUTRO assets can be selected independently.

```text
MP4 + SRT OR MP4
   ↓
PLATFORM + SUBTITLE STYLE
   ↓
OPTIONAL MUSIC
   ↓
OPTIONAL INTRO / OUTRO
   ↓
VALIDATED STUDIO OUTPUT
```

Studio uses FFmpeg locally and does not invoke script generation, Whisper, Flux, Wan, or ComfyUI.

INTRO and OUTRO assets use the shared position-specific catalog:
`assets/videos/intro_outro/intro/` and `assets/videos/intro_outro/outro/`.
Their directory, not their filename, defines their position for every final-video flow.

---

## Integrated Design Capability

AI Visual Composer also includes **Diseño** as an integrated visual generation capability.

Diseño is not a fifth main product component.

Instead, it provides a direct path for transforming visual descriptions or design intentions into:

- standalone images;
- standalone video clips.

This capability reuses the existing image and video generation infrastructure while preserving the four-component architecture:

```text
GUION
IMAGEN
VIDEO
STUDIO
```

Diseño therefore acts as an additional input and scalability path rather than an independent product pipeline.

---

## Visual Truth

Visual Truth is the structured visual contract used by the image generation architecture.

Its purpose is to preserve the information that must survive between narrative interpretation and visual generation, including elements such as:

- visible subjects;
- actions;
- environments;
- objects;
- spatial relationships;
- continuity;
- visual constraints;
- filmable interpretation.

Visual Truth remains independent from the specific generation backend.

---

## Visual Intelligence

Visual Intelligence is the reasoning layer responsible for interpreting structured visual information before prompt translation.

Its architecture follows three principal stages:

```text
VISUAL ANALYSIS
      ↓
VISUAL REASONING
      ↓
VISUAL SYNTHESIS
```

The resulting information is consolidated into an `EffectiveVisualBrief`.

This allows the system to reason about visual intent, priorities, continuity, conflicts, composition, and generation strategy before communicating with the image backend.

---

## Prompt Translation

Prompt Translation converts the structured visual representation into generation instructions suitable for the selected backend.

Its responsibilities include:

- selecting relevant visual information;
- prioritizing prompt content;
- removing unnecessary duplication;
- respecting backend prompt budgets;
- preserving visual intent;
- maintaining generation traceability.

This keeps narrative interpretation separated from backend-specific prompt construction.

---

## Image Generation

AI Visual Composer uses a local ComfyUI-based image generation runtime.

The current image architecture supports:

- structured storyboard interpretation;
- Visual Truth;
- Visual Intelligence;
- cinematic direction;
- backend-neutral prompt translation;
- generation manifests;
- visual evidence;
- profile-driven output.

The generation backend and its models remain replaceable components of the wider architecture.

---

## Image-to-Video

AI Visual Composer includes an Image-to-Video generation layer for transforming generated images into temporal visual assets.

The I2V architecture supports:

- source-image analysis;
- motion intent;
- video prompt translation;
- ComfyUI integration;
- Wan I2V generation;
- clip manifests;
- generated video assets.

Generated clips remain available as independent project artifacts before final composition.

---

## Video Composition

Final audiovisual composition is performed through a modular FFmpeg-based video engine.

The composition pipeline supports:

```text
MOTION
   ↓
TRANSITIONS
   ↓
OVERLAYS
   ↓
VISUAL EFFECTS
   ↓
FADE
   ↓
SUBTITLES
```

The video engine also supports temporal preparation of generated I2V clips, including forward/reverse ping-pong looping when a generated clip must cover a longer scene duration.

Motion can be applied to both still images and generated I2V material.

---

## Subtitle System

AI Visual Composer includes a subtitle timing architecture designed to use real timing information whenever it is available.

Timing resolution follows the hierarchy:

```text
EDGE TTS WORDBOUNDARY
        ↓
WHISPER WORD TIMESTAMPS
        ↓
LEGACY SRT TIMING
```

The system supports:

- real word timing;
- word-by-word subtitles;
- single-line subtitles;
- Whisper timing fallback;
- legacy timing compatibility;
- micro-cue handling for extremely short subtitle events.

The micro-cue system operates exclusively on subtitle presentation and does not modify the original spoken content.

---

## Audio

The audiovisual pipeline includes dedicated processing for:

- voice generation;
- audio preparation;
- music;
- final audio mixing;
- subtitle timing sources.

Voice generation and subtitle timing remain coordinated while preserving their responsibilities as separate parts of the system.

---

## Profiles

AI Visual Composer uses a profile-driven architecture.

Validated output targets currently include:

- Instagram
- YouTube

Profiles allow generation and composition behavior to be adapted according to the target platform, orientation, resolution, subtitle configuration, motion behavior, and audiovisual requirements.

---

## Local Architecture

AI Visual Composer is designed to operate locally.

Its current ecosystem uses:

- Python
- Ollama
- ComfyUI
- FFmpeg
- Edge TTS
- OpenAI Whisper
- Flux
- Wan

Large AI models, external runtimes, generated content, temporary files, and private development resources remain outside the public source repository.

---

## Validation

AI Visual Composer V2.0 maintains a permanent validation baseline created from real executions of the system.

The baseline contains:

```text
GUION   20 real executions
IMAGEN   8 real executions
VIDEO    8 real executions
────────────────────────
TOTAL   36 real executions
```

Validation evidence is preserved under:

```text
validation/01_VALIDACION_2026-08-24/
```

with dedicated evidence for:

```text
validation/01_VALIDACION_2026-08-24/guion/
validation/01_VALIDACION_2026-08-24/imagen/
validation/01_VALIDACION_2026-08-24/video/
```

The validation system preserves representative artifacts such as:

- reports;
- metrics;
- inventories;
- manifests;
- storyboards;
- source images;
- I2V clips;
- final videos;
- representative samples.

This provides a permanent behavioral reference for future development, regression analysis, and restoration.

---

## Current Capabilities

AI Visual Composer V2.0 includes:

- script-based audiovisual processing;
- topic-driven content generation;
- voice generation;
- audio processing and mixing;
- subtitle generation;
- real subtitle word timing;
- word-by-word subtitle presentation;
- micro-cue handling;
- storyboard generation;
- Visual Truth;
- Visual Intelligence;
- Visual Analysis;
- Visual Reasoning;
- Visual Synthesis;
- Effective Visual Brief;
- Cinematic Direction;
- Prompt Translation;
- ComfyUI image generation;
- Flux support;
- ComfyUI Image-to-Video generation;
- Wan I2V support;
- Motion;
- ping-pong I2V looping;
- transitions;
- overlays;
- visual effects;
- fades;
- FFmpeg final composition;
- Studio rendering from an external MP4 and authoritative SRT;
- optional Studio music and INTRO/OUTRO composition;
- Instagram profiles;
- YouTube profiles;
- generation manifests;
- visual evidence;
- permanent validation baselines.

---

## Project Documentation

Official project documentation is separated by responsibility:

```text
README.md
```

General product overview.

```text
ARCHITECTURE.md
```

Internal system architecture and component relationships.

```text
INSTALL.md
```

Initial installation and environment requirements.

```text
START.md
```

Normal startup and shutdown procedure.

```text
ROADMAP.md
```

Current development state and future evolution.

```text
CHANGELOG.md
```

Historical record of relevant product changes.

```text
validation/
```

Permanent validation evidence and historical behavioral baselines.

---

## Repository Boundaries

The public repository contains the elements required to describe, understand, validate, and develop AI Visual Composer.

This may include:

- source code;
- configuration;
- official documentation;
- official assets;
- tests;
- validation baselines;
- technical references.

Local or private resources are intentionally kept outside the public distribution, including:

- generated runtime output;
- temporary files;
- local input content;
- local logs;
- secrets and credentials;
- local ComfyUI installation;
- downloaded AI models and checkpoints;
- private development memory;
- private agent workspaces.

---

## Installation

Initial installation and environment preparation are documented in:

**[INSTALL.md](INSTALL.md)**

---

## Startup

Normal startup and shutdown procedures are documented in:

**[START.md](START.md)**

---

## License

AI Visual Composer is released under the **MIT License**.

See **[LICENSE](LICENSE)** for the complete license terms.

---

## Copyright

Copyright © 2026 **Juan Bautista Galisteo Marqués**

All copyright notices and license notices must be preserved in copies or substantial portions of the software in accordance with the MIT License.

---

## Author

**Juan Bautista Galisteo Marqués**

Creator and maintainer of **AI Visual Composer**.

---

AI Visual Composer  
Professional AI Visual Generation Platform  
© 2026 Juan Bautista Galisteo Marqués
