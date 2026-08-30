# AI Visual Composer Roadmap

Professional AI Visual Generation Platform

This document describes the current development state and future direction of AI Visual Composer.

The current stable system is:

```text
AI VISUAL COMPOSER V2.0
```

AI Visual Composer is organized around three main product components:

```text
AI VISUAL COMPOSER

1. Guion
2. Imagen
3. Video
```

Diseño is an integrated capability and scalability path. It is not a fourth main product component.

---

## 1. Current State

AI Visual Composer V2.0 provides a modular local architecture for AI-assisted audiovisual generation.

The current system integrates:

- script preparation;
- local language-model processing;
- voice generation;
- audio processing;
- subtitle generation;
- real subtitle timing;
- storyboard generation;
- Visual Truth;
- Visual Intelligence;
- Cinematic Direction;
- Prompt Translation;
- Flux image generation through ComfyUI;
- Wan I2V generation through ComfyUI;
- Motion;
- transitions;
- overlays;
- visual effects;
- fade;
- FFmpeg audiovisual composition;
- profile-driven output;
- permanent validation evidence.

The architecture is designed to improve existing capabilities without unnecessarily increasing system complexity.

---

# 2. Product Components

## Guion

Status:

```text
IMPLEMENTED
VALIDATED
```

Guion processes complete text or scripts supplied directly by the user.

Current operational capabilities include:

```text
Guion -> Imagen
Guion -> Video
Guion -> Diseño -> Imagen
Guion -> Diseño -> Video
```

Guion remains the script-centered product component and is independent from the rendering engines used downstream.

---

## Imagen

Status:

```text
IMPLEMENTED
VALIDATED
```

Imagen provides the image-centered generation workflow.

Depending on the selected execution mode, the current architecture supports:

- content preparation;
- voice;
- audio;
- subtitles;
- storyboard;
- Visual Truth;
- Visual Intelligence;
- Cinematic Direction;
- Prompt Translation;
- image generation;
- image manifests;
- visual evidence;
- final audiovisual composition.

Current execution modes include:

```text
Proyecto completo
Solo audio
Audio + subtítulos
Audio + subtítulos + storyboard
```

---

## Video

Status:

```text
IMPLEMENTED
VALIDATED
```

Video provides the video-centered audiovisual generation workflow.

The current architecture supports:

- content preparation;
- voice;
- audio;
- subtitles;
- storyboard;
- image generation;
- source-image analysis;
- motion intent;
- I2V prompt translation;
- ComfyUI I2V generation;
- Wan;
- generated clip manifests;
- temporal preparation;
- Motion;
- transitions;
- overlays;
- visual effects;
- fade;
- subtitles;
- final FFmpeg composition.

Current execution modes include:

```text
Proyecto completo
Solo audio
Audio + subtítulos
Audio + subtítulos + storyboard
```

---

# 3. Integrated Diseño Capability

Status:

```text
IMPLEMENTED
VALIDATED
```

Diseño provides direct visual generation routes while reusing the existing Image and Video infrastructure.

It is not a fourth main product component.

Current routes:

```text
Diseño -> Imagen
Diseño -> Video
```

## Diseño -> Imagen

Direct visual intent can be transformed into standalone generated images.

The route reuses:

- visual preparation;
- Visual Truth adaptation;
- image generation infrastructure.

It does not execute the complete audiovisual Imagen pipeline.

## Diseño -> Video

Direct visual intent can be transformed into standalone generated video clips.

The route reuses:

- visual preparation;
- Visual Truth adaptation;
- image generation;
- I2V generation.

It does not execute the complete audiovisual Video pipeline.

---

# 4. Visual Architecture

Status:

```text
IMPLEMENTED
```

The current visual architecture follows:

```text
Visual Truth
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
Generation Backend
```

This separation allows narrative information, visual interpretation, cinematic decisions, and backend-specific instructions to evolve independently.

---

# 5. Visual Intelligence

Status:

```text
IMPLEMENTED
```

Visual Intelligence currently provides three principal stages:

```text
ANALYSIS
   ↓
REASONING
   ↓
SYNTHESIS
```

The resulting canonical contract is:

```text
EffectiveVisualBrief
```

Current responsibilities include:

- visual semantic analysis;
- intent interpretation;
- priority resolution;
- continuity reasoning;
- visual conflict handling;
- structured visual synthesis;
- traceability toward downstream generation.

The architecture is already present.

Future work should focus primarily on extracting more value from the existing information rather than replacing the architecture.

---

# 6. Image Generation

Status:

```text
IMPLEMENTED
VALIDATED
```

The current image generation architecture uses:

```text
Visual Truth
   ↓
Visual Intelligence
   ↓
Cinematic Direction
   ↓
Prompt Translation
   ↓
ComfyUI
   ↓
Flux
```

The current system already produces high-quality image generation results.

Future development should preserve this quality and avoid unnecessary architectural changes.

Potential future work may include controlled evaluation of:

- prompt quality;
- cinematic direction;
- composition;
- model parameters;
- scheduler behavior;
- generation steps.

Any modification affecting visual quality should be evaluated against existing real outputs whenever possible.

---

# 7. I2V Video Generation

Status:

```text
IMPLEMENTED
VALIDATED
```

Current architecture:

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
ComfyUI
      ↓
Wan I2V
      ↓
Generated Clip
```

Generated clips are preserved through:

```text
video_clips_manifest.json
```

The current architecture also supports temporal preparation of generated clips for longer scene durations.

---

# 8. Temporal Video Preparation

Status:

```text
IMPLEMENTED
VALIDATED
```

Generated I2V clips can be extended using forward/reverse ping-pong preparation.

Conceptually:

```text
FORWARD
   ↓
REVERSE
   ↓
REPEAT
   ↓
TRIM TO REQUIRED DURATION
```

This allows existing generated clips to cover longer scene durations without requiring unnecessary Wan regeneration.

Duplicated endpoint frames are avoided during forward/reverse transitions.

---

# 9. Motion

Status:

```text
IMPLEMENTED
VALIDATED
```

Motion can operate over:

```text
Still Images
Generated I2V Clips
```

The current profile-driven system supports multiple movement types, including:

```text
zoom_in
zoom_out
pan_left
pan_right
pan_up
pan_down
```

Future improvement should focus on making better use of existing visual information when selecting and applying movement.

Potential research direction:

```text
Visual Intelligence
        ↓
Composition / Movement Intent
        ↓
Motion Selection
```

This should be evaluated incrementally rather than through a rewrite of the Motion system.

---

# 10. Video Composition

Status:

```text
IMPLEMENTED
VALIDATED
```

The FFmpeg composition architecture currently follows:

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

The system already provides modular builders for the composition process.

Future development should preserve this separation.

---

# 11. Subtitles

Status:

```text
IMPLEMENTED
AUTOMATED TESTS VALIDATED
REAL FINAL RUNTIME VALIDATION PENDING
```

The current V2.0 state includes the restored real subtitle timing architecture.

Timing priority:

```text
Edge TTS WordBoundary
        ↓
Whisper Word Timestamps
        ↓
Whisper SRT Timing
```

Current capabilities include:

- Edge TTS WordBoundary capture;
- Whisper JSON word timestamps;
- deterministic timing-source resolution;
- legacy fallback;
- real word-by-word timing;
- single-line timing integration;
- micro-cue presentation handling.

The micro-cue system operates at presentation level and preserves spoken content.

Automated subtitle timing tests are currently passing.

A final real runtime execution of the recovered complete system remains pending before definitive V2.0 closure.

---

# 12. Audio

Status:

```text
IMPLEMENTED
```

Current audio capabilities include:

- Edge TTS voice generation;
- generated voice persistence;
- music integration;
- FFmpeg audio processing;
- final audiovisual audio composition.

Potential future improvements may include controlled evaluation of:

- loudness normalization;
- music volume behavior;
- unnecessary transcoding;
- final audio consistency.

These are optimization opportunities, not requirements for the current architecture.

---

# 13. Profiles

Status:

```text
IMPLEMENTED
VALIDATED
```

AI Visual Composer uses profile-driven behavior for different generation targets.

Current profile families include:

```text
Guion
Instagram
YouTube
Diseño -> Imagen
Diseño -> Video
Video
```

Profiles allow generation and composition behavior to evolve without requiring architectural rewrites.

Future changes should preserve this principle.

---

# 14. Validation Baseline

Status:

```text
ESTABLISHED
PRESERVED
```

AI Visual Composer V2.0 maintains permanent validation evidence under:

```text
validation/01_VALIDACION_2026-08-24/
```

The baseline contains:

```text
Guion    20 real executions
Imagen    8 real executions
Video     8 real executions
─────────────────────────
Total    36 real executions
```

The baseline preserves real historical outputs and supporting evidence for future regression analysis.

Depending on the route, evidence may include:

- scripts;
- audio;
- subtitles;
- storyboards;
- images;
- image manifests;
- I2V clips;
- I2V manifests;
- final videos;
- metrics;
- inventories;
- reports.

Future development should use these artifacts when evaluating behavioral or quality regressions.

---

# 15. Current Automated Verification

The recovered V2.0 state currently passes:

```text
864 automated tests
```

Additional technical verification includes:

```text
python -m compileall app tests certification
git diff --check
```

The historical V2.0 baseline was originally established with:

```text
837 automated tests
```

The additional test coverage corresponds primarily to the subtitle timing architecture integrated into the current V2.0 state.

Automated tests do not replace real runtime validation when external generation systems or perceptual quality are involved.

---

# 16. Current Preservation Sequence

AI Visual Composer is currently identified as `V2.0`.

V2.0 is the stable state that must be preserved before the next deep general validation.

The established order is:

```text
1. Correct documentation
2. Review general documentation coherence
3. Establish CHECKPOINT V2.0
4. Create a full backup of the V2.0 state
5. Execute deep general validation
6. Correct any discovered issues afterwards from the preserved V2.0 base
```

## 16.1 Documentation Consistency

Ensure that official documentation consistently describes the current state as AI Visual Composer V2.0.

The objective is to remove ambiguity before preserving the V2.0 state.

## 16.2 V2.0 Git Checkpoint

Create the definitive V2.0 Git checkpoint for the current state.

The checkpoint is not conditional on the future deep general validation. It identifies the current V2.0 versioned state so that future corrections can start from a known Git reference.

## 16.3 Full V2.0 Backup

Create a full backup of the V2.0 state after the checkpoint.

The backup should preserve or identify the relevant local state needed to restore the project beyond Git-tracked files when applicable.

## 16.4 Deep General Validation

Execute the complete real pipeline after the V2.0 checkpoint and backup.

The objective is to determine the real runtime behavior of the preserved V2.0 state with the local execution environment.

## 16.5 Visual Video Quality Verification

The existing V2.0 baseline should be used as reference when investigating perceived video-quality differences.

The objective is to determine whether any degradation exists and, if so, identify the first stage where it appears.

No generation parameters should be changed merely to compensate for an unlocated regression.

## 16.6 Architecture Naming Reference

Ensure that official documentation consistently describes:

```text
AI Visual Composer V2.0
```

and the same architecture:

```text
Guion
Imagen
Video

Integrated capability:
Diseño
```

## 16.7 Post-Validation Corrections

Any issue discovered during the later deep general validation should be corrected from the preserved V2.0 base.

---

# 17. Future Development Principles

Future development should follow several principles.

## Improve Before Expanding

The priority is to improve the capabilities already present in AI Visual Composer before adding unnecessary new systems.

```text
BETTER EXISTING CAPABILITIES
>
MORE UNNECESSARY CAPABILITIES
```

## Preserve Validated Quality

Existing validated behavior should be treated as an asset.

Improvements must not silently degrade previously accepted results.

## Evidence Before Optimization

Do not optimize components based solely on theoretical improvements.

Use:

- real outputs;
- controlled comparisons;
- baseline evidence;
- measurable behavior;
- perceptual evaluation where appropriate.

## Avoid Architectural Rewrites Without Need

The current architecture already separates:

- script;
- audio;
- subtitles;
- storyboard;
- visual intelligence;
- image generation;
- I2V;
- temporal processing;
- composition.

Future improvements should normally evolve these components rather than replacing the complete architecture.

---

# 18. Future Optimization Areas

The following areas represent possible future work.

They are not commitments and are not considered part of the current stable implementation until validated.

---

## 18.1 Visual Intelligence -> Motion

Investigate whether existing Visual Intelligence information can better influence Motion selection.

Potential relationship:

```text
Cinematic Direction
        ↓
Movement Intent
        ↓
Motion
```

Objective:

Make camera movement more semantically connected to the visual scene.

---

## 18.2 Visual Intelligence -> I2V

Investigate richer transfer of structured visual information into I2V prompt construction.

Potential information includes:

- subject;
- action;
- composition;
- depth;
- movement intent;
- photographic intent.

Objective:

Use more of the information the system already understands before Wan generation.

---

## 18.3 I2V Quality

Evaluate I2V quality improvements through controlled A/B testing.

Possible variables may include:

- generation steps;
- FPS;
- sampling configuration;
- prompt information;
- motion intent.

Constraints:

- local hardware;
- VRAM;
- generation time;
- stability;
- visual quality.

Changes should not be adopted without real comparison against existing outputs.

---

## 18.4 Motion Quality

Potential areas:

- easing;
- composition-aware movement;
- diagonal movement;
- scene-aware selection;
- improved movement continuity.

Any improvement should remain compatible with both still images and generated I2V clips.

---

## 18.5 Transitions

Evaluate transition behavior only when there is a demonstrated visual benefit.

Avoid adding transitions simply to increase variety.

---

## 18.6 Overlays and Visual Effects

Overlays and Visual Effects already exist and remain configurable.

They should not be globally enabled merely because they are available.

Future work may evaluate:

- semantic selection;
- contextual use;
- profile-specific behavior;
- controlled aesthetic combinations.

The objective is visual coherence rather than maximum effect density.

---

## 18.7 Audio Optimization

Potential evaluation areas:

- loudness consistency;
- music balance;
- normalization;
- transcoding efficiency.

Changes should preserve current audio reliability.

---

## 18.8 Subtitle Evolution

The current subtitle architecture should remain stable unless new real evidence demonstrates a problem.

Future subtitle work should be evidence-driven.

Do not redesign timing behavior solely because another theoretical implementation is possible.

---

# 19. Future Version Policy

A future version should not be created simply because development continues.

A new stable version should represent a meaningful, validated system state.

Before creating a future stable version:

```text
IMPLEMENT
    ↓
VALIDATE
    ↓
COMPARE
    ↓
DOCUMENT
    ↓
REVIEW
    ↓
VERSION
    ↓
CHECKPOINT
```

A version must correspond to identifiable evidence.

---

# 20. Version and Backup Strategy

Future version references must distinguish between:

```text
GIT CHECKPOINT
```

and:

```text
FULL PHYSICAL BACKUP
```

A Git checkpoint preserves version-controlled files.

A full physical backup must preserve or identify all relevant state required to reproduce the validated system.

Where appropriate, this may include:

- exact Git commit;
- tag;
- full project snapshot;
- private local state;
- configuration;
- validation manifest;
- version;
- date;
- test results.

The objective is simple:

Git commits and tags are exact version references. Full physical backups are the mechanism for integral restoration.

---

# 21. Long-Term Direction

AI Visual Composer should continue evolving as a coherent local audiovisual generation platform.

The long-term objective is not to accumulate independent AI features.

The objective is to improve the quality, intelligence, controllability, reliability, and traceability of the complete generation system.

The core architecture remains:

```text
                    AI VISUAL COMPOSER
                             │
             ┌───────────────┼───────────────┐
             │               │               │
           GUION           IMAGEN           VIDEO
             │               │               │
             └───────────────┴───────────────┘
                             │
                    VISUAL ARCHITECTURE
                             │
                 GENERATION / COMPOSITION
                             │
                           OUTPUT
```

With Diseño operating as an integrated visual generation capability across the existing architecture.

---

## Current Roadmap Status

```text
VERSION
V2.0

CORE PRODUCT
GUION   -> IMPLEMENTED / VALIDATED
IMAGEN  -> IMPLEMENTED / VALIDATED
VIDEO   -> IMPLEMENTED / VALIDATED

INTEGRATED CAPABILITY
DISEÑO  -> IMPLEMENTED / VALIDATED

AUTOMATED TESTS
864 PASSING

PERMANENT BASELINE
36 REAL EXECUTIONS

PENDING BEFORE DEFINITIVE V2.0 CLOSURE
- Complete official documentation review
- Create definitive V2.0 Git checkpoint
- Create full V2.0 backup
- Execute deep general validation afterwards
- Resolve any discovered issues from the preserved V2.0 base
```

---

Copyright © 2026 Juan Bautista Galisteo Marqués.

AI Visual Composer was created and is maintained by Juan Bautista Galisteo Marqués.
