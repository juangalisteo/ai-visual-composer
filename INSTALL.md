# AI Visual Composer — Installation Guide

This document describes the initial installation and environment setup required to run AI Visual Composer V2.0.

For normal startup after installation, see:

```text
START.md
```

---

## 1. System Requirements

AI Visual Composer is designed to run locally.

Recommended environment:

```text
Operating System: Windows
Python: 3.11 compatible environment
GPU: NVIDIA
GPU Acceleration: CUDA-compatible environment
```

The system also requires sufficient:

- GPU VRAM for local image and I2V generation;
- system RAM;
- disk space for AI models;
- disk space for generated audiovisual content.

Actual hardware requirements depend on the models and generation profiles being used.

---

## 2. Required Components

AI Visual Composer relies on the following main external components:

```text
Python
FFmpeg
Ollama
ComfyUI
Edge TTS
OpenAI Whisper
Flux models
Wan I2V models
```

These components serve different responsibilities and should not be treated as interchangeable dependencies.

---

## 3. Python Environment

Open a terminal in the project root.

Verify Python:

```powershell
python --version
```

A Python 3.11-compatible environment is recommended for the current project.

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

Install project dependencies:

```powershell
pip install -r requirements.txt
```

---

## 4. FFmpeg

AI Visual Composer uses FFmpeg for audiovisual processing and final composition.

FFmpeg is used for operations including:

- audio processing;
- temporal video preparation;
- Motion;
- transitions;
- overlays;
- visual effects;
- fades;
- subtitles;
- final video encoding.

Verify the installation:

```powershell
ffmpeg -version
```

Also verify FFprobe:

```powershell
ffprobe -version
```

Both commands should be available from the terminal.

If they are not recognized, install FFmpeg and ensure its executable directory is available through the system `PATH`.

---

## 5. Ollama

AI Visual Composer uses Ollama for local language-model execution.

Install Ollama for Windows using the official Ollama distribution.

After installation, verify:

```powershell
ollama --version
```

Check installed models:

```powershell
ollama list
```

The project configuration currently uses:

```text
qwen3:14b
```

If the configured model is not installed:

```powershell
ollama pull qwen3:14b
```

The model configured in AI Visual Composer and the model installed in Ollama must correspond.

For normal daily operation, the installed Ollama Windows application can be opened directly.

Manual terminal startup is also possible:

```powershell
ollama serve
```

See `START.md` for the normal startup procedure.

---

## 6. ComfyUI

AI Visual Composer uses ComfyUI as the local generation runtime for:

```text
Image Generation
I2V Video Generation
```

ComfyUI is maintained as a local external runtime and is not part of the core public repository.

The expected local project structure is:

```text
AI Visual Composer/
│
├── app/
├── config/
├── assets/
├── validation/
├── main.py
│
└── ComfyUI/
```

The `ComfyUI/` directory is excluded from Git.

Install and configure ComfyUI separately inside the local project environment.

The normal Windows NVIDIA startup command is:

```powershell
cd ComfyUI
.\run_nvidia_gpu.bat
```

The expected local endpoint is:

```text
http://127.0.0.1:8188
```

Verify that ComfyUI starts correctly before attempting real image or I2V generation.

---

## 7. Flux Image Generation

AI Visual Composer uses Flux through ComfyUI for local image generation.

The required Flux models must be installed in the appropriate local ComfyUI model directories.

The current generation architecture expects the Flux workflow and its required model components to be available locally.

Typical model responsibilities include:

```text
Flux model
Text encoder
VAE
```

Model files are intentionally excluded from the public Git repository because of their size and external distribution requirements.

Relevant model extensions may include:

```text
*.safetensors
*.ckpt
*.pt
*.pth
```

Do not commit local model files to the public repository.

The AI Visual Composer configuration and the actual ComfyUI installation must reference compatible model files.

---

## 8. Wan I2V

AI Visual Composer uses Wan through ComfyUI for Image-to-Video generation.

The current V2.0 video architecture expects the configured Wan I2V model and workflow to exist in the local ComfyUI environment.

The configured workflow is maintained under the project configuration.

The corresponding external model must be installed locally in the appropriate ComfyUI model directory.

Wan model files are not stored in the public repository.

Before running a complete Video workflow, verify that:

```text
ComfyUI starts correctly
Wan model is available
Required nodes are available
Configured workflow loads correctly
I2V generation can execute
```

---

## 9. ComfyUI Workflows

AI Visual Composer communicates with ComfyUI through configured API workflows.

Relevant workflow configuration is maintained under:

```text
config/
```

The workflows define the generation graph expected by the application.

Do not modify workflow node identifiers, model references, or required graph structure without understanding how AI Visual Composer maps runtime parameters into the workflow.

A workflow that opens successfully in ComfyUI is not automatically proof that the application integration remains compatible.

Real integration should be validated through AI Visual Composer.

---

## 10. Edge TTS

AI Visual Composer uses Edge TTS for voice synthesis.

The current subtitle architecture can also use Edge TTS `WordBoundary` metadata as its preferred source of real word timing.

Edge TTS is installed through the project Python dependencies.

Verify that the package is available:

```powershell
python -c "import edge_tts; print('Edge TTS OK')"
```

Voice generation should ultimately be validated through a real AI Visual Composer execution.

---

## 11. OpenAI Whisper

AI Visual Composer uses OpenAI Whisper for transcription and subtitle timing fallback.

The current subtitle timing priority is:

```text
Edge TTS WordBoundary
        ↓
Whisper Word Timestamps
        ↓
Whisper SRT Timing
```

Whisper must therefore be available in the Python environment used by AI Visual Composer.

Verify:

```powershell
whisper --help
```

If Whisper is installed correctly, the command should display its available options.

Whisper relies on FFmpeg, so FFmpeg must also be available through the system `PATH`.

---

## 12. Triton Windows Reference Environment

The validated Windows environment uses `triton-windows` to avoid Whisper Triton fallback warnings when PyTorch CUDA is already operational.

Install the compatible Triton Windows package with:

```powershell
python -m pip install -U "triton-windows>=3.7,<3.8"
```

Validated reference environment:

```text
Python: 3.13.12
PyTorch: 2.12.0.dev20260408+cu128
PyTorch CUDA runtime: 12.8
CUDA available: True
GPU: NVIDIA GeForce RTX 5070 Laptop GPU
triton-windows: 3.7.1.post27
Imported Triton version: 3.7.1
```

In this validated environment, installing `triton-windows` removed Whisper warnings about failed Triton kernel launch and fallback to slower median kernel and DTW implementations.

A full CUDA Toolkit installation was not required because PyTorch already provided a working CUDA runtime in this environment.

These versions describe the validated Windows reference environment. They are not universal project requirements.

---

## 13. Project Assets

AI Visual Composer uses local project assets under:

```text
assets/
```

Official version-controlled product assets may include resources such as:

```text
assets/fonts/
assets/music/
assets/videos/visual_effects/
```

Local generated assets remain excluded from Git where appropriate.

Do not remove official project assets unless the corresponding feature has been deliberately modified.

---

## 14. Configuration

System configuration is maintained under:

```text
config/
```

This includes profile-driven behavior and generation configuration.

Relevant profile families include:

```text
config/profiles/guion/
config/profiles/imagen/
config/profiles/video/
config/profiles/studio/
```

Within each component/platform, ESTÁNDAR profiles are discovered from
`estandar/` and self-contained DISEÑO JSON profiles from `design/`. An empty
`design/` directory does not expose DISEÑO.

Configuration should remain portable.

Do not introduce personal absolute filesystem paths into shared configuration.

For example, avoid public configuration such as:

```text
C:\Users\PERSONAL_USER\Desktop\...
```

Local machine-specific information should remain private or excluded from the public repository.

---

## 15. Local Inputs and Outputs

AI Visual Composer includes four empty runtime input files:

```text
input/guion.txt
input/tema.txt
input/guion_imagen.txt
input/guion_video.txt
```

These files belong to the public project structure and are included in a clone or download of the repository.

They are intentionally empty. The user writes into them when preparing a local generation.

Generated projects are maintained under:

```text
output/
```

Generated runtime output is excluded from the public repository.

Permanent validation evidence is stored separately under:

```text
validation/
```

Do not confuse:

```text
input/
output/
```

with:

```text
validation/
```

Runtime input content is local user state.

Runtime output may be regenerated or removed.

Validation evidence represents preserved historical system behavior.

---

## 16. Private Development State

Private development and agent state may exist under:

```text
AGENT_AI/CODEX/
AGENT_AI/ANTIGRAVITY/
CODEX/
.agents/
.codex/
```

These locations are intentionally excluded from the public repository.

The root:

```text
AGENTS.md
```

is different.

It contains the public AI-assisted development methodology and is intended to remain version-controlled.

Private agent configuration must not be copied into the public `AGENTS.md`.

---

## 17. Environment and Secrets

Local environment files are excluded from Git:

```text
.env
.env.*
```

An example environment template may be versioned as:

```text
.env.example
```

Never commit:

- passwords;
- API keys;
- access tokens;
- private credentials;
- machine-specific secrets.

Even though AI Visual Composer is designed primarily around local execution, repository hygiene must still protect local credentials and private state.

---

## 18. Initial Verification

After installing the required components, verify the Python project before performing expensive generation tests.

### Python Compilation

Run:

```powershell
python -m compileall app tests certification
```

The command should complete without compilation errors.

### Automated Tests

Run:

```powershell
python -m unittest discover
```

The expected test count can evolve as the project develops.

The important requirement is that the current test suite completes successfully.

### Git Diff Check

For a development checkout:

```powershell
git diff --check
```

This checks the current diff for whitespace errors.

It does not validate runtime behavior.

---

## 19. External Runtime Verification

Before the first complete generation, verify each external runtime independently.

### Ollama

```powershell
ollama list
```

Confirm that the configured language model is available.

### ComfyUI

Start:

```powershell
cd ComfyUI
.\run_nvidia_gpu.bat
```

Confirm that the local server becomes available at:

```text
http://127.0.0.1:8188
```

### FFmpeg

```powershell
ffmpeg -version
ffprobe -version
```

### Whisper

```powershell
whisper --help
```

Once these checks pass, return to the project root before starting AI Visual Composer.

---

## 20. First Real Validation

Installation is not fully demonstrated merely because dependencies import successfully.

After setup, perform a controlled real execution through AI Visual Composer.

The validation should confirm the parts of the system required by the selected route.

Depending on the workflow, this may include:

```text
Ollama
   ↓
Script Processing
   ↓
Edge TTS
   ↓
Whisper / Subtitle Timing
   ↓
Storyboard
   ↓
ComfyUI
   ↓
Flux
   ↓
Wan I2V
   ↓
FFmpeg
   ↓
Final Output
```

Not every execution mode uses every stage.

If a real external stage has not been executed, do not consider that stage validated solely because static checks or automated tests pass.

---

## 21. Normal Startup

Once installation and initial verification are complete, normal daily use does not require repeating this installation procedure.

Use:

```text
START.md
```

The normal startup order is:

```text
OLLAMA
   ↓
COMFYUI
   ↓
AI VISUAL COMPOSER
```

AI Visual Composer itself is started from the project root with:

```powershell
python main.py
```

---

## 22. Installation Checklist

Before considering the local installation ready:

```text
[ ] Compatible Python environment available
[ ] Virtual environment created
[ ] requirements.txt installed
[ ] FFmpeg available
[ ] FFprobe available
[ ] Ollama installed
[ ] Configured Ollama model available
[ ] ComfyUI installed locally
[ ] Flux requirements available in ComfyUI
[ ] Wan I2V requirements available in ComfyUI
[ ] Required ComfyUI workflows compatible
[ ] Edge TTS available
[ ] Whisper available
[ ] Official project assets present
[ ] Project configuration reviewed
[ ] Python compilation passes
[ ] Automated tests pass
[ ] External runtimes start correctly
[ ] Controlled real execution completed
```

---

## Installation Complete

Once the environment is installed and validated, use:

```text
START.md
```

for normal operation.

Keep external runtimes, downloaded models, generated output, secrets, personal paths, and private development state outside the public repository.

---

Copyright © 2026 Juan Bautista Galisteo Marqués.

AI Visual Composer was created and is maintained by Juan Bautista Galisteo Marqués.
