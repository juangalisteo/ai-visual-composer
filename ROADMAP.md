# Roadmap

# AI Visual Composer

Professional AI Visual Generation Platform

This roadmap describes the current V2.0 implementation state and the future V2.x optimization line.

## V2.0 - Implemented And Validated

V2.0 establishes AI Visual Composer as a three-entry local generation platform:

```text
AI VISUAL COMPOSER

1. Guion
2. Imagen
3. Video
```

Validated baseline evidence:

- Guion: 20 real executions.
- Imagen: 8 real executions.
- Video: 8 real executions.
- Total: 36 real executions.

Baseline directories:

```text
validation/v2_0/guion/
validation/v2_0/imagen/
validation/v2_0/video/
```

## Guion

Implemented and validated:

- manual script source through `input/guion.txt`;
- generated script topic through `input/tema.txt`;
- Guion -> Imagen;
- Guion -> Video;
- Guion -> Diseno -> Imagen;
- Guion -> Diseno -> Video;
- Instagram and YouTube profiles.

## Imagen

Implemented and validated:

- Proyecto completo;
- Solo audio;
- Audio + subtitulos;
- Audio + subtitulos + storyboard;
- Storyboard generation;
- Visual Truth based image runtime;
- Visual Intelligence evidence;
- Prompt Translation;
- ComfyUI image generation;
- image manifests;
- final FFmpeg video composition in complete mode;
- Instagram and YouTube profiles.

## Video

Implemented and validated:

- Proyecto completo;
- Solo audio;
- Audio + subtitulos;
- Audio + subtitulos + storyboard;
- image generation as source for video;
- I2V clip generation;
- ping-pong/reverse I2V looping in FFmpeg composition;
- Motion applied over generated I2V clips;
- video clip manifests;
- final FFmpeg video composition;
- Instagram and YouTube profiles.

## Shared Runtime Capabilities

Implemented and validated:

- voice generation;
- audio mixing;
- subtitle generation and optimization;
- storyboard generation;
- image generation;
- I2V generation;
- ping-pong I2V clip looping;
- Motion over images and I2V clips;
- transitions;
- overlays;
- visual effects;
- fade;
- subtitles in final composition;
- pipeline summary output;
- manifests and validation baselines.

## Current Inputs

```text
input/tema.txt
input/guion.txt
input/guion_imagen.txt
input/guion_video.txt
```

## Current Outputs

V2.0 output families:

```text
output/guion/
output/imagen/
output/video/
```

## V2.x - Optimization / Polish

The following items are known future work. They are not part of the V2.0 checkpoint requirements unless a real functional failure is discovered.

### I2V

- Evaluate I2V quality vs VRAM constraints.
- Improve I2V quality presets when supported by local hardware.

### Motion

- Optimize Motion behavior beyond the validated V2.0 baseline.
- Refine motion distribution across different scene types.

### Overlays

- Improve professional overlay selection.
- Refine overlay density, timing, and category distribution.

### Transitions

- Improve transition style selection.
- Refine transition timing and visual continuity.

### Subtitles

- Optimize subtitle segmentation.
- Synchronize subtitles more deeply with real voice timing and silence.

### Performance

- Optimize processing time.
- Persist PipelineSummary timing metrics per project.
- Improve benchmark comparability across future runs.

## Future Version Policy

V2.x work must be opened explicitly by the owner.

Future checkpoints must only be created after:

- functional validation;
- baseline or test evidence;
- documentation update;
- clean Git review;
- explicit owner approval.
