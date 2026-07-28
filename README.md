# AI Visual Composer

Professional AI Visual Generation Platform

AI Visual Composer is a profile-driven visual generation and composition platform. Version 1.0.0 ships a certified Image Component runtime and a stabilized video composition core that can assemble generated images, audio, subtitles, motion, transitions, overlays, visual effects, fade stages, and FFmpeg command generation into final videos.

The project is designed around explicit configuration, deterministic contracts, and independent components. The current official product entry is the Image Pipeline. Video Pipeline is visible as a future expansion, but is not implemented in this release.

## Project Goals

- Provide a modular visual generation platform controlled by profiles.
- Keep visual behavior explicit, inspectable, and configurable.
- Preserve a certified Image Component runtime.
- Preserve a stable FFmpeg-based video composition core.
- Keep external runtimes, models, generated outputs, logs, and local secrets outside the repository.
- Prepare the project for future AI Visual Composer product pipelines without changing the certified Image Component core.

## Main Features

- Official AI Visual Composer entry point.
- Image Pipeline as the first available product pipeline.
- Single cinematic Image Component runtime.
- Backend-neutral cognitive and cinematic contracts.
- Prompt translation through `BackendPrompt`.
- ComfyUI backend adapter and ComfyUI runtime integration.
- Optional Visual Quality validation and controlled retry infrastructure.
- Image manifest generation compatible with downstream video assembly.
- Profile-driven video configuration.
- Modular video pipeline: Motion, Transitions, Overlays, Visual Effects, Fade, Subtitles.
- FFmpeg `filter_complex` generation.
- FFmpeg command planning, execution, and output validation.
- Unit and certification test coverage.

## Architecture Summary

The Image Component runtime follows this flow:

```text
Storyboard scene
  -> StoryboardSceneAdapter
  -> RuntimeCognitiveAdapter
  -> EffectiveVisualBrief
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

The video core remains a separate FFmpeg composition pipeline:

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

The current video filter order is fixed:

1. Motion
2. Transitions
3. Overlays
4. Visual Effects
5. Fade
6. Subtitles

## Project Structure

```text
ai-visual-composer/
  app/
    backend_adapters/
    cinematic_direction/
    domain/
    modules/
      images/
      video/
    prompt_translation/
    visual_quality/
  assets/
  certification/
  config/
    profiles/
  data/
  docs/
    reference/
      prompt_music.md
  prompts/
  tests/
  main.py
  README.md
  ARCHITECTURE.md
  CHANGELOG.md
  ROADMAP.md
  LICENSE
  requirements.txt
```

`output/`, `logs/`, `.env`, `input/`, `CODEX/`, `ComfyUI/`, local models, checkpoints, LoRAs, VAE files, embeddings, ControlNet resources, external runtimes, and generated media are intentionally excluded from the public repository.

## Current Status

Release: `AI Visual Composer v1.0.0`

Status:

- Image Component 1.0 certified as `IMAGE_COMPONENT_1_0_READY`.
- Product Integration completed.
- Final Project Cleanup completed.
- Video composition core stabilized.
- Runtime legacy image path removed.
- Visual Quality infrastructure included.
- First official product entry available through `python main.py`.

## Requirements

Repository requirements:

- Python 3.13 or compatible Python 3 runtime.
- FFmpeg available on `PATH`.
- Python dependencies installed from `requirements.txt`.

External runtime requirements:

- ComfyUI installed outside the repository.
- Required ComfyUI models and checkpoints installed outside the repository.
- A compatible ComfyUI workflow available through local configuration.
- Ollama installed and running when using the local LLM provider.
- Required Ollama model pulled locally.
- Edge TTS network access for voice generation.
- Environment variables configured in a local `.env` file.

These external dependencies are not committed to the repository.

## Installation

Clone the repository:

```bash
git clone <repository-url> ai-visual-composer
cd ai-visual-composer
```

Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Verify FFmpeg:

```bash
ffmpeg -version
```

Prepare external tools:

1. Install ComfyUI outside this repository.
2. Install required image models and checkpoints in the ComfyUI environment.
3. Start ComfyUI and verify that it is reachable by the configured backend URL.
4. Install Ollama if using the local LLM provider.
5. Pull the configured Ollama model locally.
6. Ensure Edge TTS can access the network for voice generation.
7. Create a local `.env` file for secrets and machine-specific settings.

## Execution

Run the product entry point:

```bash
python main.py
```

The application starts with:

```text
AI VISUAL COMPOSER

¿Qué pipeline deseas utilizar?

1. Image Pipeline
2. Video Pipeline (Próximamente)
```

Select `Image Pipeline` to use the certified Image Component flow. `Video Pipeline` is visible only as a future expansion.

## Direct Video Core Usage

The video core can still be used directly from Python:

```python
from app.modules.video.video_builder import VideoBuilder

VideoBuilder().build(
    audio_path="output/example/audio/voice.mp3",
    subtitle_path="output/example/subtitles/subtitles.srt",
    images_manifest_path="output/example/images/images_manifest.json",
    output_path="output/example/video/final.mp4",
)
```

## Official Documentation

- `README.md`: official project overview and installation guide.
- `ARCHITECTURE.md`: current architecture.
- `CHANGELOG.md`: release history.
- `ROADMAP.md`: future work.

Private development memory lives in `CODEX/` and is intentionally excluded from the public repository and official releases.

## License

MIT License. See [LICENSE](LICENSE).

## Author

Juan Bautista Galisteo Marqués

Creator and maintainer of AI Visual Composer.
