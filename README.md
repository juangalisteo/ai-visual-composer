# AI Visual Composer

Professional AI Visual Generation Platform

AI Visual Composer is a profile-driven local generation system for scripts, images, image-to-video clips, and final video composition. The current documented product state is V2.0.

The application is operated from the console through:

```bash
python main.py
```

## Current Status

- Version: `V2.0`.
- State: validated by manual execution baselines.
- Baseline evidence:
  - `validation/v2_0/guion/`
  - `validation/v2_0/imagen/`
  - `validation/v2_0/video/`
- Validated executions: 36 real runs.
- Test suite at pre-checkpoint audit: 837 tests passing.

## Product Entries

The main console exposes:

```text
AI VISUAL COMPOSER

1. Guion
2. Imagen
3. Video
```

Each entry is implemented and validated in V2.0.

## Components

### Guion

The Guion component works with manual script input and can route the script toward Imagen, Video, or Diseno.

Validated routes include:

- Guion -> Imagen
- Guion -> Video
- Guion -> Diseno -> Imagen
- Guion -> Diseno -> Video

### Imagen

The Imagen component generates the visual image pipeline from script/storyboard evidence. It supports partial and complete execution modes.

Validated modes:

- Proyecto completo
- Solo audio
- Audio + subtitulos
- Audio + subtitulos + storyboard

### Video

The Video component is available as a product entry in V2.0. It supports partial video-oriented routes and complete image-to-video generation.

Validated modes:

- Proyecto completo
- Solo audio
- Audio + subtitulos
- Audio + subtitulos + storyboard

The complete Video route includes image generation, I2V clip generation, and final FFmpeg composition with ping-pong I2V looping and composition Motion over generated clips.

## Profiles

Validated profiles:

- Instagram
- YouTube

Profile configuration is loaded from `config/profiles/`.

Current profile families include:

- `config/profiles/guion/`
- `config/profiles/instagram/`
- `config/profiles/youtube/`
- `config/profiles/diseno/imagen/`
- `config/profiles/diseno/video/`
- `config/profiles/video/`

## Inputs

Current input files:

```text
input/tema.txt
input/guion.txt
input/guion_imagen.txt
input/guion_video.txt
```

Purpose:

- `input/tema.txt`: topic for generated script flows.
- `input/guion.txt`: manual script source for Guion routes.
- `input/guion_imagen.txt`: manual design source for Diseno -> Imagen.
- `input/guion_video.txt`: manual design source for Diseno -> Video.

## Outputs

Generated outputs are written under `output/` according to the selected product entry and route.

`output/` is runtime-temporary storage. It may be reset between executions, is excluded from Git, and is not part of any version or restoration point.

V2.0 baseline output families:

- `output/guion/`
- `output/imagen/`
- `output/video/`

Typical project artifacts include:

- `scripts/guion.txt`
- `audio/voz.mp3`
- `audio/audio_final.mp3`
- `subtitles/subtitulos.srt`
- `subtitles/subtitulos_video.srt`
- `storyboard/storyboard.json`
- `images/images_manifest.json`
- `images/scene_*.png`
- `images/evidence/`
- `video_clips/video_clips_manifest.json`
- `video_clips/scene_*.mp4`
- `video/*.mp4`

## Pipeline Capabilities

AI Visual Composer V2.0 includes:

- script generation and manual script ingestion;
- voice generation;
- audio mixing;
- subtitle generation and optimization;
- storyboard generation;
- Visual Truth based image runtime;
- Visual Intelligence evidence;
- prompt translation;
- ComfyUI image generation;
- ComfyUI I2V video clip generation;
- ping-pong I2V clip looping;
- image manifests;
- video clip manifests;
- Motion over images and I2V clips;
- transitions;
- overlays;
- visual effects;
- fade;
- subtitles in final video;
- FFmpeg final composition.

## Music

Music is optional.

The current console presents:

```text
MUSICA

1. Sin musica
2. Aleatoria
```

When enabled, music is selected from available assets under `assets/music/`.

## Overlays

Overlays are optional in complete video composition.

Current behavior includes:

- dynamic discovery under `assets/videos/overlays/`;
- semantic category resolution;
- `Light Leaks` neutral fallback;
- weighted thematic distribution;
- per-video category cooldown;
- immediate asset repeat avoidance.

## Visual Effects

Visual Effects are distinct from overlays. They are temporal video layer effects used by the video composition pipeline according to profile configuration.

## Video Composition Order

The FFmpeg video composition core applies:

```text
Motion
  -> Transitions
  -> Overlays
  -> Visual Effects
  -> Fade
  -> Subtitles
```

## External Runtime Requirements

AI Visual Composer uses local external runtimes:

- Ollama
- ComfyUI
- FFmpeg
- Edge TTS

The configured local AI provider is Ollama. ComfyUI workflows and models must be available in the local development environment.

External runtimes, generated output, local logs, models, checkpoints, secrets, and private development memory are not part of the public product repository.

## Validation

V2.0 baseline evidence:

- Guion: 20 executions.
- Imagen: 8 executions.
- Video: 8 executions.
- Total: 36 executions.

Permanent V2.0 baseline evidence is stored under `validation/v2_0/`. The baseline is self-contained for future comparisons and does not depend on the continued existence of the original runtime files under `output/`.

Any historical `source` metadata pointing to `output/` records the original execution location only. Those paths are not live dependencies and may stop resolving after `output/` is reset.

Baseline artifacts include:

- `report.md`
- `metrics.json`
- `metrics.csv`
- `inventory.json`
- `samples_manifest.json`
- `samples/`
- `charts/`

## Documentation

- `README.md`: operational overview.
- `ARCHITECTURE.md`: current architecture.
- `ROADMAP.md`: implemented V2.0 and future V2.x work.
- `CHANGELOG.md`: notable changes.
- `project_tree.txt`: generated architecture tree.
- `docs/reference/generate_project_tree.md`: project tree generator reference.

Private development memory and task handoff documents live in `CODEX/` and are intentionally excluded from the public repository and official releases.

## License

MIT License. See [LICENSE](LICENSE).

## Author

Juan Bautista Galisteo Marques

Creator and maintainer of AI Visual Composer.
