# Visual Director

Visual Director is the image prompt direction subsystem of AI Video Composer.

It enriches scene prompts before they are sent to the image generation backend. It does not generate images, does not call ComfyUI, and does not modify the video composition engine.

## Objective

Visual Director acts as a lightweight art director and director of photography for generated scene images.

Its responsibility is to transform a storyboard scene into a more complete image prompt while preserving:

- the original scene meaning;
- the original `visual_idea`;
- the scene duration;
- the scene count;
- the current image generation flow;
- backend independence.

Current functional flow:

```text
Script
  -> Storyboard
  -> Scene text and visual_idea
  -> Visual Director
  -> Directed prompt
  -> ImageBuilder
  -> Image backend
  -> Image manifest
```

## Philosophy

Visual Director improves prompt quality without taking ownership away from the project pipeline.

The subsystem follows these principles:

- it enriches prompts, but does not generate images;
- it preserves the source visual idea instead of replacing it;
- it remains backend-neutral;
- it avoids hidden runtime dependencies;
- it keeps all decisions inspectable through prompt metadata;
- it fails safely by returning to the legacy prompt path;
- it does not affect the video render pipeline.

## Current Implementation

The first functional version is implemented in:

```text
app/modules/visual_director/
  __init__.py
  visual_director.py
```

It is integrated from:

```text
app/modules/images/image_builder.py
```

The implementation is deterministic and local. It does not call an AI model and does not perform network requests.

## Integration Point

Visual Director runs inside `ImageBuilder.build(...)`, after each storyboard scene is loaded and before `_generate_image(...)` injects the prompt into the image backend workflow.

```text
Storyboard scene
  -> legacy prompt available as fallback
  -> VisualDirectionContext
  -> VisualDirector.direct(...)
  -> DirectedPrompt
  -> _generate_image(...)
```

If Visual Director raises an exception, `ImageBuilder` logs a warning and uses the previous legacy prompt for that scene.

## Data Contracts

### VisualDirectionContext

Input dataclass passed to Visual Director.

Fields:

- `scene_text`
- `visual_idea`
- `duration`
- `scene_index`
- `scene_count`
- `orientation`
- `previous_directives`

### DirectedPrompt

Output dataclass returned by Visual Director.

Fields:

- `positive_prompt`
- `negative_prompt`
- `final_prompt`
- `directives`

`final_prompt` is the prompt sent to the image backend.

## Prompt Enrichment

The current version enriches prompts with:

- subject guidance derived from scene text and visual idea;
- environment guidance;
- emotional mood guidance;
- composition guidance;
- camera guidance;
- lighting guidance;
- color guidance;
- orientation guidance for horizontal or vertical output;
- realism and detail guidance;
- neutral negative prompt constraints against text, logos, watermarks, captions, illustration styles, distorted forms, and clutter.

`ImageBuilder` adds a brief general cinematic identity and keeps final backend prompts limited to Visual Director output, legacy fallback text when needed, and neutral prompt restrictions.

## Orientation

Orientation is derived from the active profile format.

Horizontal profiles receive 16:9 cinematic framing guidance.

Vertical profiles receive 9:16 mobile framing guidance with subject-safe composition.

## Continuity

Visual Director keeps a small in-memory directive context while processing scenes in one `ImageBuilder.build(...)` run.

This allows adjacent prompt directives to avoid repeating the same composition, camera, lighting, or color choice when a direct repeat would occur.

The continuity state is local to a single build and is not persisted.

## Fallback Behavior

Fallback is mandatory for reliability.

If Visual Director fails for a scene:

```text
Visual Director failure
  -> warning log
  -> legacy ImageBuilder prompt
  -> image generation continues
```

The full project must not stop because Visual Director fails.

The manifest records fallback metadata so the result can be audited.

## Manifest Output

Image manifest entries now preserve both the prompt used by the backend and Visual Director metadata.

Additional fields:

```json
{
  "prompt": "...",
  "positive_prompt": "...",
  "negative_prompt": "...",
  "visual_director": {
    "enabled": true,
    "fallback": false,
    "scene": 1,
    "directives": {
      "subject": "...",
      "environment": "...",
      "emotion": "...",
      "composition": "...",
      "camera": "...",
      "lighting": "...",
      "color": "...",
      "orientation": "...",
      "detail": "...",
      "realism": "..."
    }
  }
}
```

Existing fields such as `scene`, `image`, `width`, `height`, and `duration` remain unchanged.

## Optional Profile Toggle

The current profiles do not need to change.

If a profile later includes:

```json
{
  "visual_director": {
    "enabled": false
  }
}
```

`ImageBuilder` will use the legacy prompt path.

No additional Visual Director profile options exist in the current implementation.

## Backend Decoupling

Visual Director is intentionally decoupled from image backends.

Rules:

- no ComfyUI imports;
- no workflow node knowledge;
- no HTTP calls;
- no model-specific execution logic;
- no video engine coupling.

The image backend remains responsible for actual generation.

Future backend-specific prompt adaptation can be added outside the core Visual Director contract.

## Relationship With Existing Modules

### Storyboard

Storyboard remains responsible for scene text, duration, and `visual_idea`.

Visual Director refines that information into a directed prompt.

### ImageBuilder

ImageBuilder remains responsible for:

- loading storyboard scenes;
- loading image dimensions from the profile;
- requesting prompt direction;
- calling the image backend;
- writing the image manifest.

### Video Engine

The video engine remains unaffected.

It still consumes image manifests and renders videos through the existing video pipeline.

## Tests

Characterization tests cover:

- directed prompt creation;
- negative prompt generation;
- horizontal and vertical orientation guidance;
- continuity directive variation;
- invalid context rejection;
- ImageBuilder integration;
- fallback to legacy prompts;
- optional profile disabling;
- preservation of scene duration and manifest structure.

## Future Evolution

Potential future work:

- split the current logic into smaller director components;
- add explicit profile-controlled visual style settings;
- add reusable prompt adapters for different backends;
- support thumbnails, covers, backgrounds, and future generated assets;
- add richer continuity memory;
- add prompt length policies;
- add model-specific adapters without coupling them to Visual Director.

These future changes should remain incremental and must not modify the video render core.
