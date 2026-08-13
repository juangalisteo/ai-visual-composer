# AI Visual Composer

Professional AI Visual Generation Platform

AI Visual Composer is a profile-driven generation and video composition system. The current repository state is the official stable V.1 baseline.

The system can generate scripts, voice, mixed audio, subtitles, storyboard, images through ComfyUI, and final FFmpeg videos with motion, transitions, overlays, visual effects, fade stages, and subtitles.

## Current Status

Status:

- General system version: `V.1`.
- State: `STABLE`.
- Current restoration point: `PR1`.
- `V.1` identifies the general system version.
- `PR1` identifies the first official restoration point inside `V.1`.

Current local AI provider:

- Provider: `ollama`
- Model: `qwen3:14b`
- API: `http://localhost:11434/api/generate`

Current ComfyUI workflow:

- `config/comfyui_flux_workflow_api.json`

## Main Capabilities

- Console entry point through `python main.py`.
- Execution modes:
  - Proyecto completo.
  - Solo guion.
  - Solo audio.
  - Audio + subtítulos.
  - Audio + subtítulos + storyboard.
- Script generation through Ollama.
- Manual script support through `input/guion.txt`.
- Topic input through `input/tema.txt`.
- Voice generation through Edge TTS.
- Optional random music selection from `assets/music/`.
- Subtitle generation and optimization.
- Storyboard generation with Visual Truth 2.0.
- Visual Intelligence runtime for image generation.
- Prompt Translation and backend-neutral prompt compilation.
- ComfyUI backend integration.
- Image manifest generation.
- FFmpeg video rendering.
- Motion, Transitions, Overlays, Visual Effects, Fade, and Subtitles stages.
- Smart overlays with thematic category selection, `Light Leaks` neutral fallback, weighted distribution, and per-video category cooldown.

## First Installation

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

Install Ollama and pull the configured model:

```bash
ollama pull qwen3:14b
```

Install ComfyUI as a local external runtime. The working local startup flow expects a `ComfyUI/` directory beside the project root or otherwise reachable from the local development environment.

Install the required ComfyUI models, checkpoints, and custom nodes required by:

```text
config/comfyui_flux_workflow_api.json
```

ComfyUI, models, checkpoints, generated output, logs, local secrets, and private development memory are not part of the public product repository.

## Normal Startup

Open three terminals and keep the external runtimes running while using AI Visual Composer.

### Terminal 1 - Ollama

Start Ollama first:

```bash
ollama serve
```

Ollama must remain running because AI Visual Composer calls the local Ollama API directly.

Configured model:

```text
qwen3:14b
```

### Terminal 2 - ComfyUI

Start ComfyUI second:

```bat
cd ComfyUI
.\run_nvidia_gpu.bat
```

ComfyUI must remain running while using image generation.

### Terminal 3 - AI Visual Composer

From the project root:

```bash
python main.py
```

## Console Flow

The console starts with:

```text
AI VISUAL COMPOSER

1. Imagen
2. Vídeo
```

`Imagen` is the available product entry. `Vídeo` is visible in the console but remains unavailable as a separate product pipeline.

After selecting `Imagen`, the runtime offers:

```text
MODO

1. Proyecto completo
2. Solo guion
3. Solo audio
4. Audio + subtítulos
5. Audio + subtítulos + storyboard
```

Mode behavior:

- `Proyecto completo`: Script -> Voice -> Audio -> Subtitles -> Storyboard -> Images -> Video.
- `Solo guion`: Script -> stop.
- `Solo audio`: Script -> Voice -> Audio -> stop.
- `Audio + subtítulos`: Script -> Voice -> Audio -> Subtitles -> stop.
- `Audio + subtítulos + storyboard`: Script -> Voice -> Audio -> Subtitles -> Storyboard -> stop.

The global `0` rule exits the application:

```text
Finalizando AI Visual Composer...
```

## Inputs

Main topic:

```text
input/tema.txt
```

Optional manual script:

```text
input/guion.txt
```

If `input/guion.txt` exists and contains text, the system uses it as the script. Otherwise it generates the script from `input/tema.txt` through Ollama.

## Profiles And Configuration

Current application profile configuration:

```text
config/app.json
platform: youtube
profile: modo_conciencia
language: es
```

Available profiles:

- `config/profiles/instagram/modo_conciencia.json`
- `config/profiles/youtube/modo_conciencia.json`

Available voice configs:

- `config/voice_configs/femenina.json`
- `config/voice_configs/masculina.json`

Available subtitle configs:

- `config/subtitle_configs/single_line.json`
- `config/subtitle_configs/word_by_word.json`

## Music

The console currently offers:

```text
MÚSICA

1. Sin música
2. Aleatoria
```

When random music is enabled, the system selects from available categories under:

```text
assets/music/
```

Current categories include:

- `action`
- `ambient`
- `calm`
- `cinematic`
- `documentary`
- `electronic`
- `emotional`
- `epic`
- `meditation`
- `mystery`

## Overlays

Overlays are available in `Proyecto completo` mode through:

```text
OVERLAYS

1. Sí
2. No
```

When overlays are enabled:

1. The system reads the topic.
2. It discovers real folders under `assets/videos/overlays/`.
3. It asks the semantic overlay resolver for a primary thematic category and optional secondary categories.
4. It validates all returned categories against real folders.
5. It adds `Light Leaks` as neutral fallback when available.
6. It applies weighted category selection:
   - primary: `3.0`;
   - secondary: `2.0`;
   - `Light Leaks`: `1.0`.
7. It applies per-video category cooldown to reduce immediate category repetition when alternatives exist.
8. It selects a concrete MP4 using the existing file selector.

Current overlay folders:

- `Electricity`
- `Light Leaks`

Behavior:

- If a clear thematic category exists, thematic overlays can participate.
- If no clear thematic category exists, `NONE -> Light Leaks`.
- If no neutral fallback exists and no thematic category is valid, overlays are disabled safely.
- File selection still avoids only immediate MP4 repetition according to the existing selector behavior.

## Visual Effects

Visual Effects are separate from overlays.

Current visual effects folder:

```text
assets/videos/visual_effects/LightLeak/
```

Visual Effects are used as temporal video layer effects according to the profile configuration. They are not the same as thematic overlays.

## Video Composition Core

The video composition order is:

1. Motion
2. Transitions
3. Overlays
4. Visual Effects
5. Fade
6. Subtitles

The public video facade remains:

```python
from app.modules.video.video_builder import VideoBuilder

VideoBuilder().build(
    audio_path=None,
    subtitle_path=None,
    images_manifest_path=None,
    output_path=None,
)
```

## Project Structure

The documentation tree is maintained in:

```text
project_tree.txt
```

This file is a documentation snapshot of the architecture, not a full inventory of local resources.

## Official Documentation

- `README.md`: overview, setup, startup, and operational usage.
- `ARCHITECTURE.md`: current architecture.
- `ROADMAP.md`: future work for the stable V.1 baseline.
- `CHANGELOG.md`: notable changes.
- `docs/architecture/VISUAL_INTELLIGENCE_ARCHITECTURE_v1.0.md`: frozen Visual Intelligence architecture specification.
- `docs/reference/generate_project_tree.md`: project tree generator reference.
- `docs/reference/prompt_music.md`: music prompt reference.
- `docs/restoration/RESTORATION_POINT_PR1.md`: official V.1 stable restoration point.

Private development memory and task reports live in `CODEX/` and are intentionally excluded from the public repository and official releases.

## Restoration Structure

Official restoration structure:

```text
V.1
|
└── PR1 - STABLE
```

Future stable restoration points inside `V.1` may be named `PR2`, `PR3`, `PR4`, and so on. `V.2` must only be created after an explicit owner decision.

## License

MIT License. See [LICENSE](LICENSE).

## Author

Juan Bautista Galisteo Marqués

Creator and maintainer of AI Visual Composer.
