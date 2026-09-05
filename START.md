# AI Visual Composer — Start Guide

This document describes the normal startup and shutdown procedure for AI Visual Composer V2.0.

For first-time installation and environment setup, see:

```text
INSTALL.md
```

---

## 1. Startup Order

For Guion, Imagen, and Video generation, start the required services in this order:

```text
1. Ollama
2. ComfyUI
3. AI Visual Composer
```

Studio processes an existing MP4 and SRT with FFmpeg. It does not require Ollama or ComfyUI unless another component will also be used in the same session.

---

## 2. Start Ollama

### Normal Windows Procedure

Open the installed Ollama application.

Ollama runs locally and provides the language model used by AI Visual Composer.

Make sure Ollama is running before starting AI Visual Composer.

### Terminal Alternative

If Ollama is not running through the Windows application, it can be started manually with:

```powershell
ollama serve
```

Keep the terminal open while AI Visual Composer is running.

This is an alternative procedure, not the normal startup method when the Ollama Windows application is already active.

---

## 3. Start ComfyUI

Open a terminal in the AI Visual Composer project root.

Enter the local ComfyUI directory:

```powershell
cd ComfyUI
```

Start ComfyUI with:

```powershell
.\run_nvidia_gpu.bat
```

Keep this terminal open.

The expected local ComfyUI endpoint is:

```text
http://127.0.0.1:8188
```

ComfyUI must remain running while AI Visual Composer is generating images or I2V video clips.

---

## 4. Start AI Visual Composer

Open another terminal in the project root.

Run:

```powershell
python main.py
```

The main menu will display:

```text
AI VISUAL COMPOSER

1. Guion
2. Imagen
3. Video
4. Studio
```

Select the required product component and continue through the interactive options.

Typing `0` in any menu exits AI Visual Composer immediately.

---

## 5. Normal Runtime

During generation:

- keep Ollama running;
- keep ComfyUI running when visual generation is required;
- keep the AI Visual Composer terminal open;
- do not close required services while a generation is in progress;
- do not delete or modify active runtime output while the project is being generated.

Generated projects are written under:

```text
output/
```

according to the selected product route and project name.

### Studio Runtime

Place exactly one `.mp4` and one UTF-8 `.srt` file in:

```text
input/studio/
```

Then select `Studio`, the platform and subtitle style, followed by the optional Light Leaks, music, and INTRO/OUTRO choices. Studio preserves the source files and writes its validated result under `output/studio/<platform>/`.

---

## 6. Shutdown

When AI Visual Composer has finished the current operation:

1. Type `0` in the current menu when applicable.
2. Close the AI Visual Composer terminal when execution has finished.
3. Close the ComfyUI terminal if it is no longer required.
4. Close Ollama if it is no longer required.

Do not terminate ComfyUI, Ollama, FFmpeg, or AI Visual Composer while an active generation is still running unless the process must intentionally be aborted.

---

## 7. Quick Reference

Normal startup:

```text
OPEN OLLAMA
     ↓
START COMFYUI
     ↓
python main.py
     ↓
SELECT
GUION / IMAGEN / VIDEO / STUDIO
```

ComfyUI:

```powershell
cd ComfyUI
.\run_nvidia_gpu.bat
```

AI Visual Composer:

```powershell
python main.py
```

Normal shutdown:

```text
FINISH CURRENT GENERATION
        ↓
EXIT AI VISUAL COMPOSER
        ↓
CLOSE COMFYUI
        ↓
CLOSE OLLAMA
```

---

## Troubleshooting

If AI Visual Composer cannot access the language model:

```text
Check that Ollama is running.
```

If image or I2V generation cannot connect to the backend:

```text
Check that ComfyUI is running at:

http://127.0.0.1:8188
```

If `python main.py` fails because a dependency or external runtime is missing, consult:

```text
INSTALL.md
```

---

Copyright © 2026 Juan Bautista Galisteo Marqués.

AI Visual Composer was created and is maintained by Juan Bautista Galisteo Marqués.
