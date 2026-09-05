# AI Visual Composer Architecture

Professional AI Visual Generation Platform

This document describes the internal architecture of AI Visual Composer V2.0.

AI Visual Composer is organized around four main product components:

```text
AI VISUAL COMPOSER

1. Guion
2. Imagen
3. Video
4. Studio
```

Diseño is an integrated capability and scalability path. It is not a fifth main product component.

The architecture is profile-driven and locally executed. It separates product selection, runtime orchestration, script preparation, audio, subtitle timing, storyboard construction, visual interpretation, image generation, image-to-video generation, temporal processing, and final FFmpeg composition.

---

## 1. Architectural Principles

AI Visual Composer follows several fundamental architectural principles:

- Guion, Imagen, Video, and Studio are the four main product components.
- Diseño is an integrated capability, not an independent fifth component.
- Product architecture and operational routing are separate concepts.
- Narrative information must remain separated from backend-specific generation instructions.
- Visual generation must pass through structured visual contracts.
- Image generation and I2V generation remain separated from final audiovisual composition.
- Runtime configuration is profile-driven.
- Generated artifacts and manifests provide traceability throughout the pipeline.
- Validation evidence is preserved separately from temporary runtime output.
- External AI runtimes and models remain outside the core public repository.

---

## 2. High-Level Runtime Flow

At the highest operational level:

```text
Console
   ↓
RunController
   ↓
Runtime Options
   ↓
app.core.start.iniciar()
   ↓
Component Orchestration
   ↓
Builders
   ↓
Generation Backends
   ↓
Manifests
   ↓
Output Artifacts
```

The console does not generate audiovisual content directly.

Its responsibility is to collect the user's operational selections, including:

- product entry;
- execution mode;
- profile;
- voice;
- subtitle configuration;
- music;
- overlays;
- project name;
- output reset behavior.

Runtime execution is delegated to the internal orchestration layer.

---

## 3. Product Architecture

The conceptual product architecture contains exactly four main components:

```text
AI VISUAL COMPOSER
│
├── GUION
│
├── IMAGEN
│
├── VIDEO
│
└── STUDIO
```

This level describes what the product is.

Operational routes describe how the console and controller allow the user to reach those capabilities.

Integrated capabilities describe additional generation paths that reuse the existing architecture without becoming new main product components.

---

# 4. GUION

Guion is the script-centered product component.

Its source is:

```text
input/guion.txt
```

The user provides the complete text or script.

The base textual content therefore already exists and AI Visual Composer processes that source through the selected destination.

Guion does not need to invent the original text supplied by the user.

## Responsibilities

Guion is responsible for:

- reading the manual script source;
- preserving the user-provided textual content;
- preparing the script for the selected workflow;
- routing the content toward Imagen or Video;
- exposing operational access to Diseño when selected;
- keeping script preparation independent from visual rendering.

## Operational Routes

Current operational route families include:

```text
Guion -> Imagen

Guion -> Video

Guion -> Diseño -> Imagen

Guion -> Diseño -> Video
```

These are operational controller routes.

They do not mean that Diseño is conceptually part of Guion or dependent on Guion as a product capability.

---

# 5. IMAGEN

Imagen is the image-centered product component.

For its normal topic-driven operation, the source is:

```text
input/tema.txt
```

The user can provide a topic, idea, description, short paragraph, or brief text.

The system develops the content required by the selected execution mode and processes it through the visual generation architecture.

## Responsibilities

Depending on the selected mode, Imagen can coordinate:

- content preparation;
- voice generation;
- audio;
- subtitles;
- storyboard generation;
- Visual Truth;
- Visual Intelligence;
- Cinematic Direction;
- Prompt Translation;
- image generation;
- image manifests;
- visual evidence;
- final FFmpeg composition.

## Complete Image Flow

At a high level:

```text
Input
   ↓
Script Preparation
   ↓
Voice
   ↓
Audio
   ↓
Subtitles
   ↓
Storyboard
   ↓
Visual Truth
   ↓
Visual Intelligence
   ↓
Cinematic Direction
   ↓
Prompt Translation
   ↓
Image Generation
   ↓
Image Manifest
   ↓
FFmpeg Composition
   ↓
Final Video
```

The image generation layer remains independent from final video composition.

---

# 6. VIDEO

Video is the video-centered product component.

For its normal topic-driven operation, the source is:

```text
input/tema.txt
```

The user provides a topic, idea, description, short paragraph, or brief text.

The runtime develops the content required to create the audiovisual sequence.

## Responsibilities

Video can coordinate:

- content preparation;
- voice generation;
- audio;
- subtitles;
- storyboard generation;
- Visual Truth;
- Visual Intelligence;
- image generation;
- source-image analysis;
- motion intent;
- I2V prompt translation;
- I2V generation;
- video clip manifests;
- temporal preparation;
- Motion;
- transitions;
- overlays;
- visual effects;
- fade;
- subtitles;
- final FFmpeg composition.

## Complete Video Flow

```text
Input
   ↓
Script Preparation
   ↓
Voice
   ↓
Audio
   ↓
Subtitles
   ↓
Storyboard
   ↓
Visual Truth
   ↓
Visual Intelligence
   ↓
Prompt Translation
   ↓
Image Generation
   ↓
I2V Generation
   ↓
Temporal Preparation
   ↓
Motion
   ↓
Transitions
   ↓
Overlays
   ↓
Visual Effects
   ↓
Fade
   ↓
Subtitles
   ↓
Final Video
```

---

# 7. STUDIO

Studio is the finishing component for externally supplied audiovisual material.

Its source contract is:

```text
input/studio/
├── exactly one MP4
└── exactly one UTF-8 SRT
```

The SRT is authoritative: Studio preserves its text, order, and timings, applies the selected component-scoped subtitle render style with zero offset, and does not invoke Whisper, SubtitleBuilder, or SrtOptimizer.

The complete flow is:

```text
External MP4 + SRT
   ↓
Studio profile (Instagram / YouTube)
   ↓
Subtitle style
   ↓
Optional Light Leaks (1 s active / 4 s clean)
   ↓
Optional explicit music selection
   ↓
Single audiovisual FFmpeg render
   ↓
Optional INTRO / OUTRO concat with stream copy
   ↓
Validated output/studio/<platform>/ result
```

Studio has its own `ProfileKey`, main profiles, subtitle profiles, input preparation, output naming, and render service. It does not fall back to Guion, Imagen, or Video and does not invoke Ollama, Flux, Wan, ComfyUI, Motion, storyboard generation, or narrative audio generation.

Its base render preserves aspect ratio through `scale` plus `pad`, emits H.264/yuv420p video and AAC 48 kHz stereo audio, and uses the profile resolution and FPS. Source audio remains at nominal gain; a compatible silent stream is supplied when the source has no audio. Optional music is mixed at `0.25` with `amix normalize=0` and a `0.95` limiter.

When INTRO or OUTRO is selected, only incompatible assets are normalized. The validated Studio principal is then concatenated through the concat demuxer with `-c copy`, so it is not encoded a second time.

---

# 8. INTEGRATED DESIGN CAPABILITY

Diseño is an integrated capability that allows direct visual intent to become the source for image or video generation.

It is a scalability path.

It is not a fifth main product component.

Diseño uses dedicated manual inputs and converts direct visual descriptions into information compatible with the existing generation architecture.

---

## Diseño -> Imagen

Source:

```text
input/guion_imagen.txt
```

Operational flow:

```text
input/guion_imagen.txt
   ↓
ImageDesignPreparationService
   ↓
ImageDesignVisualTruthAdapter
   ↓
ImageBuilder
   ↓
Standalone Images
```

This route produces standalone visual assets.

It does not execute the complete audiovisual Imagen workflow.

It does not produce:

- voice;
- subtitles;
- music;
- final audiovisual composition.

---

## Diseño -> Video

Source:

```text
input/guion_video.txt
```

Operational flow:

```text
input/guion_video.txt
   ↓
VideoDesignPreparationService
   ↓
VideoDesignVisualTruthAdapter
   ↓
ImageBuilder
   ↓
VideoComponentBuilder
   ↓
Standalone Video Clips
```

This route generates the visual source required for I2V and produces standalone video clips.

It does not represent the complete Video product pipeline.

It does not produce:

- complete narration;
- subtitles;
- music;
- final audiovisual composition.

---

## Diseño Boundaries

Diseño may:

- receive direct visual intent;
- prepare visual descriptions;
- adapt visual information into Visual Truth compatible scenes;
- reuse image generation infrastructure;
- reuse I2V generation infrastructure.

Diseño must not:

- replace Guion;
- replace Imagen;
- replace Video;
- become a fifth main product component;
- create an independent parallel generation architecture.

---

# 9. EXECUTION MODES

Validated execution modes for Imagen and Video include:

```text
Proyecto completo
Solo audio
Audio + subtítulos
Audio + subtítulos + storyboard
```

Their general behavior is:

## Solo audio

```text
Script
   ↓
Voice
   ↓
Audio
   ↓
STOP
```

## Audio + subtítulos

```text
Script
   ↓
Voice
   ↓
Audio
   ↓
Subtitles
   ↓
STOP
```

## Audio + subtítulos + storyboard

```text
Script
   ↓
Voice
   ↓
Audio
   ↓
Subtitles
   ↓
Storyboard
   ↓
STOP
```

## Proyecto completo — Imagen

```text
Script
   ↓
Voice
   ↓
Audio
   ↓
Subtitles
   ↓
Storyboard
   ↓
Images
   ↓
Final Video
```

## Proyecto completo — Video

```text
Script
   ↓
Voice
   ↓
Audio
   ↓
Subtitles
   ↓
Storyboard
   ↓
Images
   ↓
I2V Clips
   ↓
Final Video
```

---

# 10. INPUT ARCHITECTURE

The current manual input files are:

```text
input/guion.txt
input/tema.txt
input/guion_imagen.txt
input/guion_video.txt
input/studio/ (one MP4 and one SRT at runtime)
```

Their responsibilities are deliberately separated.

## `input/guion.txt`

Complete text or script supplied directly by the user.

Used by:

```text
GUION
```

The original textual source already exists and must be preserved.

---

## `input/tema.txt`

Topic, idea, description, short paragraph, or brief text.

Used by:

```text
IMAGEN
VIDEO
```

The AI runtime can develop the necessary textual content from this source according to the selected workflow.

---

## `input/guion_imagen.txt`

Direct visual source for:

```text
DISEÑO -> IMAGEN
```

Produces standalone images.

---

## `input/guion_video.txt`

Direct visual source for:

```text
DISEÑO -> VIDEO
```

Produces standalone I2V video clips.

---

## `input/studio/`

Runtime source directory for Studio. It requires exactly one MP4 and one UTF-8 SRT, discovered by extension rather than by a fixed filename. Runtime media is ignored by Git while `.gitkeep` preserves the directory.

---

# 11. OUTPUT ARCHITECTURE

Generated runtime projects are grouped by main product entry:

```text
output/guion/
output/imagen/
output/video/
output/studio/
```

Depending on the execution path, projects may contain:

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

Important runtime manifests include:

```text
storyboard/storyboard.json

images/images_manifest.json

video_clips/video_clips_manifest.json
```

`output/` is temporary runtime storage.

It is not a permanent validation baseline and is not a mechanism for integral system restoration.

Permanent validation evidence is stored separately under:

```text
validation/
```

---

# 12. SCRIPT LAYER

The script layer is implemented primarily under:

```text
app/modules/script/
```

Its responsibilities include:

- loading or generating script content according to the selected source;
- preparing textual content for downstream processing;
- validating script output contracts;
- preventing invalid conversational model responses from entering downstream pipelines;
- keeping script handling independent from image and video rendering.

Key elements include:

```text
ScriptPreparationService
ScriptOperation
ScriptBuilder
ScriptOutputValidator
```

---

# 13. AUDIO AND VOICE LAYER

The audio architecture coordinates voice generation and final audio preparation.

Responsibilities include:

- voice synthesis;
- voice artifact persistence;
- timing metadata capture;
- music integration when enabled;
- audio preparation;
- final audio mixing.

Edge TTS provides both synthesized voice and WordBoundary timing metadata used by the subtitle timing system.

Audio generation remains logically separated from subtitle presentation.

---

# 14. SUBTITLE LAYER

The subtitle layer is implemented under:

```text
app/modules/subtitles/
```

AI Visual Composer V2.0 uses a provider-neutral timing architecture designed to use real word timing whenever available.

## Timing Priority

```text
Edge TTS WordBoundary
        ↓
Whisper JSON Word Timestamps
        ↓
Whisper SRT Segment Timing
```

The system therefore prefers the most precise available timing evidence while maintaining compatibility when richer timing data is unavailable.

## Responsibilities

The subtitle layer can:

- generate subtitle files from real audio;
- consume Edge TTS WordBoundary metadata;
- request and preserve Whisper word timestamps;
- resolve the best available timing source;
- preserve legacy timing fallback;
- render single-line subtitles;
- render word-by-word subtitles;
- detect extremely short subtitle cues;
- apply presentation-level micro-cue handling.

## Main Components

```text
SubtitleBuilder
SrtOptimizer
SubtitleTiming
SubtitleTimingResolver
EdgeWordBoundaryParser
WhisperTimingParser
SingleLineModel
WordByWordModel
MicroCuePolicy
```

## Timing Resolution

The timing resolver follows:

```text
1. Edge WordBoundary
2. Whisper word timestamps
3. Legacy SRT timing
```

This allows the subtitle models to use real timing information when available without breaking compatibility with previous subtitle sources.

## Micro-Cue Policy

Very short word-level subtitle events can produce visual cues that are technically correct but too brief to be perceived correctly during playback.

`MicroCuePolicy` handles those cases at presentation level.

Its purpose is to preserve spoken content while improving the visual presentation of extremely short subtitle cues.

The policy must not:

- delete spoken words;
- alter the source audio;
- alter the script;
- modify image generation;
- modify I2V generation.

Subtitle timing and presentation remain isolated from visual generation.

---

# 15. STORYBOARD LAYER

Storyboard generation is implemented primarily under:

```text
app/modules/storyboard/
```

Responsibilities include:

- interpreting prepared script content;
- dividing content into visual scenes;
- validating storyboard structure;
- preserving Visual Truth information;
- providing structured scenes to downstream visual generation.

The storyboard acts as the narrative-to-visual transition point of the system.

---

# 16. VISUAL TRUTH

Visual Truth is the operational visual contract of the Image Pipeline.

Its purpose is to preserve the visual information that must survive from storyboard interpretation to backend-neutral generation.

This may include:

- visible subjects;
- visible actions;
- environments;
- objects;
- spatial relationships;
- continuity relationships;
- visual constraints;
- filmable interpretation.

Visual Truth must remain backend-neutral.

It must not contain ComfyUI-specific execution instructions.

---

# 17. VISUAL INTELLIGENCE

Visual Intelligence is the structured interpretation layer between Visual Truth and Prompt Translation.

Its architecture follows:

```text
Visual Analysis
      ↓
Visual Reasoning
      ↓
Visual Synthesis
      ↓
EffectiveVisualBrief
```

## Visual Analysis

Inspects the structured visual information and identifies relevant visual semantics and priorities.

## Visual Reasoning

Reasons about:

- scene intent;
- visual strategy;
- continuity;
- conflicts;
- priorities;
- relationships between visual elements.

## Visual Synthesis

Consolidates the interpreted visual information into a canonical:

```text
EffectiveVisualBrief
```

This brief becomes the structured source for downstream cinematic direction and prompt translation.

## Responsibilities

Visual Intelligence is responsible for:

- inspecting Visual Truth;
- classifying visual semantics;
- establishing priorities;
- reasoning about intent;
- reasoning about continuity;
- resolving structured visual strategy;
- reporting conflicts;
- synthesizing the Effective Visual Brief;
- preserving traceability.

Visual Intelligence does not generate backend prompts directly.

---

# 18. CINEMATIC DIRECTION

Cinematic Direction operates after Visual Intelligence and before final backend prompt construction.

Its purpose is to convert structured visual understanding into cinematographic direction.

It can represent aspects such as:

- composition;
- framing;
- photographic intention;
- visual movement;
- cinematic treatment.

Cinematic Direction remains part of the structured visual interpretation process and does not directly execute generation.

---

# 19. PROMPT TRANSLATION

Prompt Translation is implemented under:

```text
app/prompt_translation/
```

Its responsibility is to transform structured visual information into generation instructions suitable for the selected backend.

Responsibilities include:

- consuming the Effective Visual Brief;
- selecting relevant prompt information;
- prioritizing visual content;
- deduplicating prompt fragments;
- respecting backend prompt budgets;
- assembling backend-compatible prompt data;
- preserving traceability.

Prompt Translation must not reinterpret the original narrative intent.

It translates structured visual intent rather than replacing it.

---

# 20. IMAGE RUNTIME

The image runtime is implemented primarily through:

```text
app/modules/images/
app/domain/adapters/storyboard_scene_adapter.py
app/visual_intelligence/
app/prompt_translation/
app/modules/images/backends/comfyui_backend.py
```

The principal flow is:

```text
StoryboardScene
      ↓
StoryboardSceneAdapter
      ↓
Visual Analysis
      ↓
Visual Reasoning
      ↓
Visual Synthesis
      ↓
EffectiveVisualBrief
      ↓
Cinematic Direction
      ↓
Prompt Translation
      ↓
BackendPrompt
      ↓
ComfyUI
      ↓
Generated Image
      ↓
images_manifest.json
```

Generation evidence may be persisted under:

```text
images/evidence/
```

The image runtime remains separated from final FFmpeg composition.

---

# 21. VIDEO COMPONENT

The I2V video component is implemented under:

```text
app/modules/video_component/
```

Its responsibility is to transform source images into generated temporal visual assets.

The component can:

- analyze source images;
- construct motion intent;
- translate visual video intent;
- prepare backend requests;
- execute ComfyUI I2V generation;
- persist generated clip manifests.

High-level flow:

```text
Source Image
      ↓
SourceImageAnalyzer
      ↓
MotionIntentBuilder
      ↓
VideoPromptTranslator
      ↓
BackendVideoPrompt
      ↓
ComfyUIVideoAdapter
      ↓
ComfyUI
      ↓
Wan I2V
      ↓
Generated Clip
      ↓
video_clips_manifest.json
```

The component is used by:

```text
VIDEO — Proyecto completo

DISEÑO -> VIDEO
```

---

# 22. I2V

I2V generation transforms a source image into a generated video clip.

Evidence is persisted through:

```text
video_clips/video_clips_manifest.json
video_clips/scene_*.mp4
```

The current local backend uses ComfyUI with the configured Wan I2V workflow.

Generated I2V clips remain independent project artifacts.

They are later consumed by the FFmpeg composition architecture when producing a complete Video project.

---

# 23. TEMPORAL PREPARATION

Generated I2V clips have their own native duration.

When a scene requires more time than the generated source clip provides, AI Visual Composer can prepare the temporal asset before final composition.

The validated behavior supports forward/reverse ping-pong looping.

Conceptually:

```text
FORWARD
   ↓
REVERSE
   ↓
REPEAT AS REQUIRED
   ↓
TRIM TO EXACT SCENE DURATION
```

Duplicated endpoint frames are avoided during the forward/reverse transition.

This allows an existing I2V clip to cover the required scene duration without regenerating the Wan output.

---

# 24. FFMPEG VIDEO COMPOSITION CORE

The final video composition architecture is implemented primarily under:

```text
app/modules/video/
```

The validated stage order is:

```text
Motion
   ↓
Transitions
   ↓
Overlays
   ↓
Visual Effects
   ↓
Fade
   ↓
Subtitles
```

Main responsibilities include:

- loading video profile configuration;
- selecting temporal assets;
- preparing scene-level media;
- constructing FFmpeg filter stages;
- constructing command plans;
- serializing FFmpeg commands;
- executing final rendering;
- validating the resulting video.

Key components include:

```text
VideoBuildContextFactory
VideoComponentFactory
VideoFilterContextFactory
VideoRenderService
VideoBuilder
CommandPlanBuilder
CommandBuilder
Runner
VideoValidator
```

---

# 25. MOTION

Motion is part of the FFmpeg composition graph.

It applies scene-level visual movement according to profile configuration and available media.

Motion can operate over:

```text
Still Images
Generated I2V Clips
```

This means I2V generation and Motion are separate stages.

Wan generates the temporal visual source.

Motion can subsequently apply additional compositional movement during final FFmpeg processing.

---

# 26. TRANSITIONS

Transitions are handled by the FFmpeg composition layer.

Their behavior is controlled through profile configuration.

Transitions remain separate from:

- Motion;
- overlays;
- visual effects;
- subtitles.

This separation allows each stage to evolve independently.

---

# 27. OVERLAYS

Overlay assets are sourced from:

```text
assets/videos/overlays/
```

The architecture supports:

- semantic category resolution;
- weighted distribution;
- category cooldown;
- neutral fallback behavior.

`Light Leaks` can operate as a neutral fallback when appropriate.

Overlay processing remains independent from transitions and visual effects.

---

# 28. VISUAL EFFECTS

Visual Effects are applied as an independent stage of the FFmpeg composition pipeline.

They remain configurable through video profiles and are not structurally coupled to overlays or transitions.

---

# 29. FADE

Fade behavior is controlled independently through profile configuration.

It operates after visual effects and before subtitle rendering in the validated composition order.

---

# 30. MUSIC

Music is selected when enabled by runtime configuration.

Music assets are sourced from:

```text
assets/music/
```

Music remains part of the audiovisual composition process and does not affect visual generation.

---

# 31. PROFILES AND CONFIGURATION

AI Visual Composer is profile-driven.

Relevant profile families include:

```text
config/profiles/guion/
config/profiles/imagen/
config/profiles/video/
config/profiles/studio/
```

Design routes use the profile family of their target component: Image or Video.

Additional system configuration is maintained under:

```text
config/
```

Runtime selections are propagated from the console/controller layer into the execution environment.

Profiles control behavior without requiring the core architecture to be rewritten for each output target.

---

# 32. EXTERNAL RUNTIMES

AI Visual Composer relies on several local external runtimes and tools.

## Ollama

Used for local language-model processing.

## ComfyUI

Used for:

- image generation;
- I2V generation.

## FFmpeg

Used for:

- audio processing;
- temporal preparation;
- Motion;
- transitions;
- overlays;
- visual effects;
- fades;
- subtitles;
- final audiovisual composition.
- Studio rendering and optional INTRO/OUTRO stream-copy composition.

## Edge TTS

Used for:

- voice synthesis;
- WordBoundary timing metadata.

## OpenAI Whisper

Used for:

- subtitle transcription;
- word timestamp fallback.

External runtimes, downloaded models, checkpoints, generated outputs, secrets, and private development resources are not part of the core public repository.

---

# 33. VALIDATION ARCHITECTURE

AI Visual Composer V2.0 maintains permanent validation evidence created from real executions of the system.

The historical V2.0 validation baseline is divided into three preserved areas that predate Studio:

```text
validation/01_VALIDACION_2026-08-24/
│
├── guion/
├── imagen/
└── video/
```

Validated execution count:

```text
GUION    20
IMAGEN    8
VIDEO     8
───────────
TOTAL     36
```

Each baseline may contain:

```text
report.md
metrics.json
metrics.csv
inventory.json
samples_manifest.json
samples/
charts/
```

The preserved samples provide historical behavioral evidence for comparison against future system states.

Depending on the route, preserved evidence may include:

- scripts;
- audio;
- subtitles;
- storyboards;
- image manifests;
- source images;
- I2V manifests;
- I2V clips;
- final videos.

This makes the validation baseline independent from temporary runtime output.

---

# 34. RUNTIME OUTPUT VS VALIDATION

The architecture deliberately separates:

```text
output/
```

from:

```text
validation/
```

`output/` contains temporary generated projects.

It may be replaced, cleaned, or regenerated during normal operation.

`validation/` contains preserved evidence used to establish historical behavior.

Therefore:

```text
OUTPUT ≠ BASELINE
```

and:

```text
OUTPUT ≠ RESTORATION POINT
```

Validation evidence must remain preserved when runtime output is cleaned.

---

# 35. REPOSITORY BOUNDARIES

The public repository may contain:

- source code;
- configuration;
- tests;
- official documentation;
- official assets;
- validation evidence;
- technical references.

Local or private resources remain outside public distribution, including:

- generated output;
- temporary runtime files;
- local input content;
- local logs;
- secrets;
- local ComfyUI runtime;
- downloaded AI models;
- checkpoints;
- private development memory;
- private agent workspaces.

Personal absolute filesystem paths must not be introduced into public documentation or shared configuration.

---

# 36. DOCUMENTATION RESPONSIBILITIES

Official documentation is separated by responsibility.

## README.md

Product overview.

## ARCHITECTURE.md

Internal architecture and component relationships.

## INSTALL.md

Initial installation and environment requirements.

## START.md

Normal startup and shutdown.

## ROADMAP.md

Current implementation state and future development direction.

## CHANGELOG.md

Historical record of product changes.

## validation/

Permanent behavioral validation evidence.

---

# 37. VERSION STATE

The current stable architecture is:

```text
AI VISUAL COMPOSER V2.0
```

V2.0 includes the validated architecture for:

```text
GUION
IMAGEN
VIDEO
STUDIO
```

together with the integrated Diseño capability and the current subtitle timing architecture.

The permanent validation baseline contains 36 historical real executions and remains the reference evidence for regression analysis and future evolution.

Future architectural changes must be validated before becoming part of a new stable system state.

---

# 38. ARCHITECTURAL SUMMARY

The complete conceptual architecture can be summarized as:

```text
AI VISUAL COMPOSER
│
├── GUION / IMAGEN / VIDEO
│      ↓
│   CONTENT + STORYBOARD + VISUAL GENERATION
│      ↓
│   AUDIO + SUBTITLES + VIDEO COMPOSITION
│
└── STUDIO
       ↓
    EXTERNAL MP4 + AUTHORITATIVE SRT
       ↓
    SUBTITLE RENDER + OPTIONAL LIGHT LEAKS / MUSIC
       ↓
    OPTIONAL INTRO / OUTRO STREAM COPY
       ↓
    VALIDATED FINAL VIDEO
```

Diseño integrates into the Image and Video infrastructure through dedicated direct visual inputs without becoming a fifth product component.

---

## Architecture Status

```text
AI VISUAL COMPOSER
VERSION: V2.0
ARCHITECTURE: MODULAR
EXECUTION: LOCAL
CONFIGURATION: PROFILE-DRIVEN
VALIDATION: 36 REAL BASELINE EXECUTIONS
MAIN COMPONENTS: GUION / IMAGEN / VIDEO / STUDIO
INTEGRATED CAPABILITY: DISEÑO
```

---

Copyright © 2026 Juan Bautista Galisteo Marqués.

AI Visual Composer was created and is maintained by Juan Bautista Galisteo Marqués.
