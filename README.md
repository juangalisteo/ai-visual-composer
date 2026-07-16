# AI Video Composer

A profile-driven AI video composition engine.

AI Video Composer is a Python-based video composition engine designed around explicit configuration profiles. Its core renders videos by combining images, audio, subtitles, motion, transitions, overlays, visual effects, fade stages, and FFmpeg command generation through a modular pipeline.

The project is currently focused on a stable video composition core. The engine does not make hidden visual decisions by default: visual behavior is driven by profile configuration.

## Project Goals

- Provide a modular video composition engine controlled by profiles.
- Keep visual behavior explicit and configurable.
- Separate configuration, selection, graph building, command planning, rendering, and validation.
- Support horizontal and vertical render workflows.
- Maintain a stable core that can grow through independent components.
- Preserve reliable FFmpeg command generation and validation.

## Main Features

- Profile-driven video configuration.
- Modular video pipeline.
- Motion support for image scenes.
- FFmpeg `xfade` transitions.
- Overlay layer support.
- Visual effect layer support.
- Fade in and fade out stage support.
- Subtitle styling and rendering.
- FFmpeg `filter_complex` generation.
- Command planning and command serialization.
- Render execution through FFmpeg.
- Output validation with expected duration checks.
- Unit test coverage for the stabilized core.

## Architecture Summary

The video core is organized as a sequence of small responsibilities:

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

Each layer is responsible for one part of the composition process. Profiles define what is enabled and how each module behaves. Builders prepare selected operations. Graph builders turn those operations into FFmpeg filter graph fragments. The pipeline assembles those stages in a fixed order. The command layer produces the final FFmpeg command, which is then executed and validated.

## Engine Flow

The current video pipeline order is:

1. Motion
2. Transitions
3. Overlays
4. Visual Effects
5. Fade
6. Subtitles

The effective render flow is:

```text
Profile
  -> Media loading
  -> Timeline calculation
  -> Component creation
  -> FilterContext creation
  -> FilterPipeline execution
  -> filter_complex generation
  -> FFmpeg command planning
  -> FFmpeg command execution
  -> Output validation
```

## Project Structure

```text
ai-video-composer/
  app/
    modules/
      video/
        assets/
        config/
        ffmpeg/
        media/
        motion/
        overlays/
        subtitles/
        transitions/
        visual_effects/
  assets/
  config/
    profiles/
  docs/
  input/
  output/
  tests/
  CODEX/
    BITACORA.md
    CHATGPT.md
  main.py
  README.md
  ARCHITECTURE.md
  CHANGELOG.md
  ROADMAP.md
  LICENSE
  requirements.txt
```

`CODEX/BITACORA.md` and `CODEX/CHATGPT.md` are temporary development documents used to preserve technical context, decisions, audits, and milestones while the project continues to grow.

## Current Status

Version: `v1.0.0` core completed.

The video engine core has been completed and validated through tests, compile checks, real horizontal renders, real vertical renders, transition-specific renders, overlay renders, visual effect renders, combined renders, FFmpeg probing, and visual frame inspection.

Current core status:

- Architecture stabilized.
- Pipeline stabilized.
- Visual Effects validated.
- Overlays validated.
- Motion validated within the pipeline.
- Transitions aligned with FFmpeg `xfade`.
- CommandBuilder stabilized.
- VideoBuilder reduced to a lightweight facade.
- Final core audit completed.

## Technologies

- Python
- FFmpeg
- FFmpeg `filter_complex`
- FFmpeg `xfade`
- libass subtitles through FFmpeg
- JSON configuration profiles
- `unittest`

The broader repository also contains AI, image, audio, publishing, storyboard, thumbnail, and subtitle modules. This README documents the currently stabilized video composition core.

## Requirements

- Python 3.13 or compatible Python 3 runtime.
- FFmpeg available on `PATH`.
- Python dependencies installed from `requirements.txt`.
- Input audio file.
- Subtitle file.
- Image manifest with at least one image.
- A valid video profile under `config/profiles/`.

## Installation

Clone the repository:

```bash
git clone <repository-url> ai-video-composer
cd ai-video-composer
```

Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Verify FFmpeg:

```bash
ffmpeg -version
```

## Execution

The project entry point is:

```bash
python main.py
```

The video engine can also be used directly from Python:

```python
from app.modules.video.video_builder import VideoBuilder

VideoBuilder().build(
    audio_path="output/example/audio/voice.mp3",
    subtitle_path="output/example/subtitles/subtitles.srt",
    images_manifest_path="output/example/images/images_manifest.json",
    output_path="output/example/video/final.mp4",
)
```

## Basic Example

A basic render requires:

- an audio file;
- an SRT subtitle file;
- an image manifest;
- a selected video profile;
- an output path.

The selected profile controls resolution, FPS, motion, transitions, overlays, visual effects, fade behavior, subtitle styling, codecs, and validation tolerance.

Example:

```python
from app.modules.video.video_builder import VideoBuilder

output = VideoBuilder().build(
    audio_path="input/audio.mp3",
    subtitle_path="input/subtitles.srt",
    images_manifest_path="input/images_manifest.json",
    output_path="output/video.mp4",
)

print(output)
```

## Roadmap Summary

- Image Enhancement
- Thumbnail Generator
- AI Assistant
- Multi-layer Rendering
- Performance
- New Effects
- Automation
- Plugins
- Testing
- Documentation

See [ROADMAP.md](ROADMAP.md) for the project roadmap.

## License

MIT License. See [LICENSE](LICENSE).

## Author

Juan Bautista Galisteo Marqués

Creator and maintainer of AI Video Composer.
