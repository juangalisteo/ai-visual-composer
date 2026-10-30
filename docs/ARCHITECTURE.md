# Arquitectura de AI Visual Composer

Este documento explica cómo está construido AI Visual Composer por dentro: qué
partes tiene, cómo viaja una ejecución desde el menú hasta el archivo final y
dónde vive cada responsabilidad.

Otros documentos:

| Para saber… | Documento |
|---|---|
| Cómo se usa el programa (menús, carpetas de entrada, resultados) | [START.md](START.md) |
| Cómo se instala | [INSTALL.md](INSTALL.md) |
| Cómo funcionan los perfiles de subtítulos (familias, modos, estilos y efectos) | [SUBTITLES.md](SUBTITLES.md) |
| Cómo se genera la voz y cuánto dura un guion | [VOICEOVER.md](VOICEOVER.md) |
| Qué ha cambiado y cuándo | [CHANGELOG.md](../CHANGELOG.md) |

---

## 1. Principios

- **El código implementa capacidades; la configuración declara entidades.**
  Python contiene los componentes fijos y las capacidades técnicas (preparar un
  guion, generar voz, transcribir, generar imágenes y clips, componer con
  FFmpeg…). Los formatos, las familias de subtítulos, los perfiles y sus valores
  se declaran en `config/` y se descubren leyendo sus carpetas. Un perfil o una
  familia nuevos que usen capacidades existentes no necesitan cambiar Python.
- **La identidad es técnica.** Un perfil se identifica por su clave
  (`OperationalProfileKey` o `SubtitleProfileKey`, [apartado 11](#11-identidad-y-perfiles)).
  `display_name` y las etiquetas de los menús solo sirven para mostrar; nunca
  deciden qué se carga ni qué se ejecuta.
- **El menú construye una petición completa antes de ejecutar.** Todo lo que el
  usuario elige viaja en una petición tipada (`ApplicationExecutionRequest`),
  no en variables de entorno ni en diccionarios sueltos.
- **Un coordinador por ruta.** La ruta estándar (GUION, IMAGEN, VIDEO), STUDIO y
  la ruta DISEÑO tienen cada una su coordinador; el despachador solo elige cuál.
- **Una sola frontera de errores.** Los errores se presentan en `main.py`, que
  decide el texto que ve el usuario y el código de salida.
- **Ejecución local.** Ollama, ComfyUI (Flux y Wan), Piper, Whisper y FFmpeg se
  ejecutan en el propio equipo; sus modelos no forman parte del repositorio.
  Las llamadas a Ollama y a Wan no tienen tiempo límite, a propósito
  ([AGENTS.md](../AGENTS.md) §8).

---

## 2. Componentes y rutas

El menú principal ofrece los cuatro componentes del producto:

```text
AI VISUAL COMPOSER

1. Guion
2. Imagen
3. Video
4. Studio
```

| Componente | De qué parte | Qué produce |
|---|---|---|
| **GUION** | Un texto completo escrito por el usuario (`input/guion.txt`) | Un proyecto de Imagen o de Video con ese texto tal cual, o la ruta DISEÑO |
| **IMAGEN** | Un tema o una idea (`input/tema.txt`); la IA escribe el guion | Un vídeo hecho con imágenes generadas |
| **VIDEO** | Un tema o una idea (`input/tema.txt`); la IA escribe el guion | Un vídeo hecho con clips generados a partir de esas imágenes (imagen a vídeo, I2V) |
| **STUDIO** | Material propio ya grabado (vídeo, audio, SRT) en `input/studio/` | El vídeo terminado (subtítulos, audio nuevo, montaje, intro/outro) o un SRT |

GUION, IMAGEN y VIDEO comparten la **ruta estándar** ([apartado 5](#5-ruta-estándar-guion-imagen-y-video)).
Dentro de GUION, el destino «Diseño» abre la **ruta DISEÑO**
([apartado 7](#7-ruta-diseño)), que no es un quinto componente. STUDIO tiene su
propia ruta ([apartado 8](#8-studio)) y no usa la IA generativa.

**DISEÑO no es la familia `design`.** La palabra aparece en dos sitios que no
tienen relación:

| Nombre | Qué es |
|---|---|
| **Ruta DISEÑO** | GUION → Diseño → Imagen o Video: genera una sola imagen o un solo clip a partir de una descripción visual directa |
| **Familia de subtítulos `design` (MODO CONCIENCIA)** | Una de las familias de perfiles de subtítulos; en el menú se llama «MODO CONCIENCIA» ([SUBTITLES.md](SUBTITLES.md)) |

---

## 3. Flujo de ejecución

```text
python main.py
   ↓
main.py                      valida config/formats.json antes del primer menú
   ↓
RunController.run()          menús → ApplicationExecutionRequest
   ↓
(ELIMINAR OUTPUT = Sí)       OutputManager().reset() vacía output/
   ↓
run_application(request)     app/core/start.py: elige el coordinador por el tipo de ruta
   ↓
StandardExecutionCoordinator | StudioExecutionCoordinator | DesignExecutionCoordinator
   ↓
builders y servicios         guion, voz, subtítulos, storyboard, imágenes, clips, FFmpeg
   ↓
output/<proyecto>/…          artefactos y vídeo final
   ↓
resumen en la terminal
```

**La petición.** `RunController.run()` (`app/controllers/run_controller.py`)
recorre los menús con los selectores de `app/controllers/interaction/` y
devuelve una `ApplicationExecutionRequest` (`app/core/execution_request.py`):

| Campo | Contenido |
|---|---|
| `project_name` | Nombre del proyecto (menú PROYECTO) |
| `clear_output` | Si se vacía `output/` antes de empezar (menú ELIMINAR OUTPUT) |
| `operational_profile_key` | `OperationalProfileKey` del perfil elegido |
| `subtitle_profile_key` | `SubtitleProfileKey` elegida, o `None` si la ejecución no lleva subtítulos |
| `route` | `StandardExecutionRequest`, `StudioExecutionRequest` o `DesignExecutionRequest` |

Cada tipo de ruta comprueba sus datos al construirse; por ejemplo,
`StandardExecutionRequest` solo acepta los modos del menú MODO.

**El despachador.** `run_application(request)` (`app/core/start.py`) prepara el
`ConfigManager` con la clave operacional (y la voz elegida, en la ruta estándar)
y el `ProjectManager` del proyecto, y entrega la ruta a su coordinador:

| Tipo de ruta | Coordinador |
|---|---|
| `StandardExecutionRequest` | `StandardExecutionCoordinator` (`app/modules/standard/execution_coordinator.py`) |
| `StudioExecutionRequest` | `StudioExecutionCoordinator` (`app/modules/studio/execution_coordinator.py`) |
| `DesignExecutionRequest` | `DesignExecutionCoordinator` (`app/modules/design/execution_coordinator.py`) |

**Los resúmenes.** Al terminar, la terminal muestra un resumen con los tiempos
de cada etapa:

- En la ruta estándar y en la ruta DISEÑO lo imprime `PipelineTelemetry.complete()`
  (`app/core/pipeline_telemetry.py`). El resumen estándar (`PipelineSummary`) se
  crea al **empezar** la ejecución, porque recoge avisos mientras se ejecuta: el
  coordinador pasa `summary.warnings` a `VideoBuilder`. Por eso no está en
  `app/cli/`: sacarlo de ahí cambiaría lo que devuelve la ruta estándar sin
  ningún cambio visible.
- En STUDIO, cada modo devuelve un resultado y `main.py` lo imprime con
  `print_studio_summary()` (`app/cli/studio_summary.py`), que elige el resumen
  por el modo de entrada (`StudioInputMode`).

**Los errores.** `main.py` es la única frontera: un `OperationalError` se
presenta con `ErrorPresenter` (`app/cli/error_presenter.py`); los errores de
entrada de STUDIO se muestran como `ERROR: …`; cualquier otro error se presenta
como error interno. Códigos de salida: `0` (correcto o cancelado), `1` (error) y
`130` (interrumpido con Ctrl+C).

---

## 4. Formatos

Un **formato** es el tamaño y la orientación del vídeo final. Hay dos:

| Formato (id) | En el menú | Orientación | Para qué redes sirve |
|---|---|---|---|
| `vertical` | Vertical 9:16 | `portrait` | Instagram Reels, TikTok, YouTube Shorts |
| `horizontal` | Horizontal 16:9 | `landscape` | YouTube (vídeo normal) |

La terminal no nombra ninguna red: solo «Vertical 9:16» y «Horizontal 16:9».

Cómo se declaran:

- **Las carpetas deciden qué formatos existen:** cada carpeta
  `config/profiles/<componente>/<formato>/` es un formato de ese componente.
- **`config/formats.json` describe cada formato** (`FormatCatalog`,
  `app/shared/format_catalog.py`):

  | Clave | Para qué sirve |
  |---|---|
  | `display_name` | Texto del menú FORMATO |
  | `order` | Posición en el menú (Vertical primero) |
  | `orientation` | `portrait` o `landscape`: al cargar un perfil, `ProfileResolver` rechaza un `video_style` cuyo ancho y alto contradigan la orientación |
  | `image_guidance` | Texto de formato que se añade al prompt de cada imagen |

- Al arrancar, `main.py` comprueba que cada formato declarado tenga su carpeta
  de perfiles; si el catálogo está mal, el programa se para antes del primer
  menú.
- **El tamaño en píxeles no lo da el formato, sino cada perfil:**
  `video_style.width`/`height` en GUION, IMAGEN y VIDEO, y `studio.output` en
  STUDIO.
- Un formato nuevo que use capacidades existentes se añade con configuración:
  sus carpetas de perfiles, su entrada en `config/formats.json`, su texto en
  `prompts/formats/<formato>.txt` y, para VIDEO, su documento de Wan
  (`"kind": "video_component"`, como `wan_i2v_<formato>.json`). No hace falta
  tocar Python.

---

## 5. Ruta estándar: GUION, IMAGEN y VIDEO

`StandardExecutionCoordinator` ejecuta siempre las mismas etapas, en este orden,
y se detiene en la última que pide el modo elegido ([apartado 6](#6-modos-de-ejecución)):

| Etapa | Qué hace | Herramienta |
|---|---|---|
| Guion | GUION lee `input/guion.txt` tal cual; IMAGEN y VIDEO escriben un guion a partir de `input/tema.txt` | Ollama (solo IMAGEN y VIDEO) |
| Voz y audio | Locución y mezcla con la música elegida | Piper ([VOICEOVER.md](VOICEOVER.md)) y FFmpeg |
| Subtítulos | Transcribe la locución y ajusta el SRT al texto del guion y al perfil de subtítulos | Whisper ([SUBTITLES.md](SUBTITLES.md)) |
| Storyboard | Divide el guion en escenas visuales: tantas como la duración del audio entre `video_style.storyboard.seconds_per_image` del perfil, redondeando hacia arriba | Ollama |
| Imágenes | Una imagen por escena | ComfyUI + Flux |
| Vídeo | IMAGEN compone el vídeo con las imágenes; VIDEO genera antes un clip por imagen | FFmpeg; VIDEO también ComfyUI + Wan |

- **Qué perfil se usa.** Cada componente usa su perfil operacional del formato
  elegido. En **GUION → Video** se usa el perfil de GUION para todo salvo los
  clips, que salen del único perfil operacional de VIDEO de ese formato; si en
  ese formato hubiera más de uno o ninguno, la ejecución se para con un error.
  Los subtítulos de GUION salen de los perfiles de subtítulos de GUION.
- **Duración.** Con un tema, la IA escribe un guion para la duración (`duration`)
  del perfil de IMAGEN o VIDEO. Con `input/guion.txt`, la duración la marca el
  propio texto. El cálculo está en [VOICEOVER.md](VOICEOVER.md).
- **Vídeo final.** Los modos «Proyecto completo» publican un único MP4 en
  `output/<proyecto>/video/<proyecto>.mp4`. Si se eligió INTRO / OUTRO, se añade
  sobre ese vídeo ya validado.

---

## 6. Modos de ejecución

El menú MODO de la ruta estándar ofrece:

| Modo (en el menú) | Id | Hasta qué etapa llega | Subtítulos | Pide OVERLAYS e INTRO / OUTRO |
|---|---|---|---|---|
| Proyecto completo | `full` | Vídeo | Sí | Sí |
| Solo audio | `audio` | Voz y audio | No | No |
| Audio + subtítulos | `subtitles` | Subtítulos | Sí | No |
| Audio + subtítulos + storyboard | `storyboard` | Storyboard | Sí | No |
| Proyecto completo sin subtítulos | `full_without_subtitles` | Vídeo | No | Sí |

- «Proyecto completo sin subtítulos» solo aparece en **GUION**. Hace lo mismo
  que «Proyecto completo», pero sin generar ni pintar subtítulos: un único MP4
  sin texto, no una segunda versión del vídeo.
- Los modos sin subtítulos no muestran el menú de subtítulos (FAMILIA → PERFIL)
  y su petición lleva `subtitle_profile_key = None`.

---

## 7. Ruta DISEÑO

La ruta DISEÑO parte de una descripción visual directa escrita por el usuario,
no de un guion narrado. Se entra por GUION → DESTINO → Diseño → Imagen o Video.

| Destino | Entrada | Etapas | Resultado |
|---|---|---|---|
| Diseño → Imagen | `input/guion_imagen.txt` | Interpreta la descripción (Ollama) → una escena → una imagen (ComfyUI + Flux) | Una sola imagen |
| Diseño → Video | `input/guion_video.txt` | Interpreta la descripción (Ollama) → una escena → una imagen → un clip (ComfyUI + Wan) | Un solo clip |

- `DesignExecutionCoordinator` comprueba que la descripción produzca
  **exactamente una escena**, y después una sola imagen o un solo clip.
- La ruta DISEÑO **no** genera voz, música ni subtítulos, y **no** compone un
  vídeo final: por eso solo pregunta el FORMATO, el PROYECTO y ELIMINAR OUTPUT.
- Reutiliza la generación de imágenes y de clips de la ruta estándar; no tiene
  una arquitectura de generación propia.

---

## 8. STUDIO

STUDIO termina material que el usuario ya tiene. No usa Ollama, ComfyUI, Flux
ni Wan, ni genera voz o storyboard. Whisper solo interviene en SOLO VIDEO y en
EXPORTAR SRT → TRANSCRIBIR. Todos sus modos, salvo TRANSCRIBIR (que no pide
formato), usan el perfil operacional STUDIO del formato elegido
(`OperationalProfileKey` con `component=studio`) y, cuando llevan subtítulos,
un perfil de subtítulos STUDIO (`SubtitleProfileKey`).

El menú ENTRADA ofrece seis modos (textos tal cual en la terminal):

| Modo | Carpeta de entrada | Qué hace |
|---|---|---|
| `SOLO VIDEO` | `input/studio/video/` | Whisper transcribe el audio del vídeo y el SRT se adapta al perfil de subtítulos elegido antes de pintarlo. El vídeo tiene que tener audio |
| `SRT + VIDEO` | `input/studio/srt_video/` | Pinta el SRT del usuario **tal cual** (siempre ORIGINAL): ni Whisper ni cambios de texto o de tiempos |
| `INTRO / OUTRO` | `input/studio/intro_outro/` | Añade una intro, un outro o ambos al vídeo |
| `MONTAJE VÍDEOS` | `input/studio/montaje_videos/` | Une varios vídeos en el orden que se elige, con o sin transiciones, y sin subtítulos |
| `VIDEO + AUDIO \| SRT` | `input/studio/video_audio_srt/` | Sustituye el audio del vídeo por uno nuevo y, si hay SRT, lo pinta tal cual |
| `EXPORTAR SRT ➜  VIDEO` | `input/studio/exportar_srt/transcribir/` y `…/convertir/` | No genera vídeo: TRANSCRIBIR saca un SRT de un MP4 o MP3 con Whisper; CONVERTIR adapta un SRT al perfil de subtítulos elegido |

Qué archivos van en cada carpeta y cómo se eligen está en [START.md](START.md).

### Cómo se tratan los subtítulos en STUDIO

- **SRT + VIDEO pinta siempre el SRT tal cual.** No es una opción del menú: el
  perfil de subtítulos elegido solo aporta el aspecto (`render_style`) y, si lo
  declara, las mayúsculas (`cue_policy.uppercase`). El orden, el texto y los
  tiempos de las líneas no cambian. Es así a propósito: si SOLO VIDEO transcribe
  mal una palabra, el usuario corrige el SRT y lo vuelve a pintar con SRT + VIDEO
  ([AGENTS.md](../AGENTS.md) §8). Los efectos por palabra reparten tiempos
  aproximados **dentro** de cada línea, sin tocar los tiempos del SRT
  ([SUBTITLES.md](SUBTITLES.md)).
- **VIDEO + AUDIO | SRT** trata su SRT igual que SRT + VIDEO.
- **SOLO VIDEO** guarda el SRT de Whisper y genera otro adaptado al modo de cue
  del perfil, que es el que se pinta.

Archivos de subtítulos que quedan en `output/<proyecto>/subtitles/`:

| Archivo | Cuándo |
|---|---|
| `<proyecto>.srt` | Siempre que hay subtítulos: copia del SRT de partida (el de Whisper en SOLO VIDEO, el del usuario en SRT + VIDEO) |
| `<proyecto>_<modo>.srt` | SOLO VIDEO: el SRT adaptado al modo de cue del perfil (`<modo>` es su `cue_policy.mode`, p. ej. `single_line`); **es el que se pinta** |
| `<proyecto>_original.srt` | SRT + VIDEO y VIDEO + AUDIO \| SRT, solo si el perfil cambia el texto a mayúsculas; si no, se pinta `<proyecto>.srt` |

Para corregir un vídeo de SOLO VIDEO se corrige `<proyecto>_<modo>.srt` (el que
se pintó), no `<proyecto>.srt`, y se pinta con SRT + VIDEO.

### Cada modo por dentro

- **Render base** (`StudioRenderService`, `app/modules/studio/render_service.py`):
  escala el vídeo al tamaño del perfil conservando su proporción (`scale` +
  `pad`, con bandas si no coincide), con el FPS, el códec y el audio del perfil.
  El audio original se queda a su volumen; la música, si se elige, se mezcla con
  el volumen y el limitador de `studio.music`.
- **INTRO / OUTRO:** los recursos salen de
  `assets/videos/intro_outro/<formato>/intro/` y `…/<formato>/outro/` (carpeta
  local, fuera de Git). Solo se normalizan los que no son compatibles; después se
  unen con el vídeo principal sin volver a codificarlo (`-c copy`). Es el mismo
  catálogo que usa la ruta estándar.
- **MONTAJE VÍDEOS:** los clips que no encajan con el perfil se normalizan
  primero. Sin transiciones, se unen uno detrás de otro (`concat`); con
  transiciones, se encadenan con `xfade`, cuya duración es
  `studio.montage.transition_duration` del perfil. El audio de los clips sigue
  uno detrás de otro (sin fundido). Cada clip tiene que durar más que la
  transición.
- **VIDEO + AUDIO | SRT:** manda la duración del **vídeo**. El audio original
  desaparece y suena el nuevo; si el audio nuevo es más corto que el vídeo, el
  menú AUDIO MÁS CORTO QUE EL VÍDEO ofrece rellenar el final con silencio o con
  música.
- **EXPORTAR SRT:** TRANSCRIBIR guarda `<proyecto>.srt`; CONVERTIR guarda
  `<proyecto>_<modo>.srt`. El SRT de partida no se modifica.

---

## 9. Entradas

| Entrada | La lee | Contenido |
|---|---|---|
| `input/guion.txt` | GUION | El texto completo que se va a narrar |
| `input/tema.txt` | IMAGEN y VIDEO | Un tema o una idea; la IA escribe el guion |
| `input/guion_imagen.txt` | Ruta DISEÑO → Imagen | La descripción visual de una imagen |
| `input/guion_video.txt` | Ruta DISEÑO → Video | La descripción visual de un clip |
| `input/studio/<modo>/` | STUDIO | Vídeos, audios y SRT de cada modo ([apartado 8](#8-studio)) |

- Los cuatro `.txt` están en el repositorio vacíos: el usuario escribe en ellos.
  Cómo evitar que sus cambios salgan en Git está en [INSTALL.md](INSTALL.md).
- STUDIO descubre sus archivos por extensión, no por nombre: si hay un solo
  candidato válido lo usa directamente; si hay varios, pregunta cuál. El
  contenido de `input/studio/` no se versiona.

---

## 10. Salida

Cada ejecución escribe en `output/<proyecto>/`, donde `<proyecto>` es el nombre
dado en el menú PROYECTO (obligatorio). Si se elige ELIMINAR
OUTPUT = Sí, antes de empezar se vacía `output/` entero; si algún archivo está
abierto en otro programa, la ejecución se para y lo avisa.

| Ruta | Contenido |
|---|---|
| `scripts/guion.txt` | Guion usado |
| `audio/voz.mp3`, `audio/audio_final.mp3` | Locución y audio mezclado |
| `subtitles/` | SRT de la ruta estándar (`subtitulos.srt`) o de STUDIO ([apartado 8](#8-studio)) |
| `storyboard/storyboard.json` | Escenas |
| `images/images_manifest.json` e `images/` | Imágenes generadas y su manifiesto (con su carpeta `evidence/`) |
| `video_clips/video_clips_manifest.json` | Clips I2V (VIDEO y Diseño → Video) |
| `video/<proyecto>.mp4` | Vídeo final |

La ruta estándar crea siempre las seis carpetas (`scripts/`, `audio/`,
`subtitles/`, `storyboard/`, `images/` y `video/`); cada etapa llena la suya.
`video_clips/` solo aparece cuando se generan clips. `output/` está fuera de
Git: es espacio de trabajo y se puede borrar o regenerar.

---

## 11. Identidad y perfiles

Hay dos tipos de perfil, con claves separadas
(`app/shared/profile_identity.py`, `app/shared/subtitle_profile_identity.py`):

| Clave | Campos | Qué identifica |
|---|---|---|
| `OperationalProfileKey` | `component`, `format`, `profile_id` | Cómo produce un componente en un formato (voz, imágenes, vídeo, render STUDIO…) |
| `SubtitleProfileKey` | `component`, `format`, `profile_id`, `family` | Cómo se cortan y se ven los subtítulos |

- La familia pertenece solo a los subtítulos: no forma parte de la identidad del
  perfil operacional.
- Los perfiles operacionales viven en
  `config/profiles/<componente>/<formato>/`; los de subtítulos, en
  `config/profiles/<componente>/<formato>/<familia>/subtitulos/`.
- El menú pide primero el FORMATO (y con él el perfil operacional) y después,
  si el modo lleva subtítulos, FAMILIA → PERFIL.
- Cómo se cargan y validan los perfiles: apartado 31. Familias, modos de cue y
  estilos: [SUBTITLES.md](SUBTITLES.md).

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
- neutral timing adaptation when a backend provides real word timings;
- music integration when enabled;
- audio preparation;
- final audio mixing.

Voice synthesis follows the technical boundary:

```text
Declarative voice configuration
        ↓
backend_key
        ↓
TtsBackendRegistry
        ↓
Provider / TtsBackend
        ↓
VoiceBuilder.build(text, output_path=None) -> Path
```

The registry resolves exact technical keys and does not select a backend from a
display name, label, component, or controller. Piper ONNX is the current
declarative provider. The shared voice documents resolve
`backend_key="piper_onnx"` to Davefx and Carlfm technical identities.
GUIÓN, IMAGEN, and VIDEO depend only on the VoiceBuilder facade, not on the
provider implementation.

Piper currently returns no real word-level alignment. `TtsWordTiming` remains
the neutral seconds-based contract for a backend that can provide it, while the
active subtitle route is Whisper usable timing or `None`.

Audio generation remains logically separated from subtitle presentation.

---

# 14. SUBTITLE LAYER

The subtitle layer is implemented under:

```text
app/modules/subtitles/
```

AI Visual Composer uses a provider-neutral timing architecture designed to use
real word timing whenever a backend provides it.

## Active Timing Resolution

```text
Whisper JSON Word Timestamps
        ↓
None
```

`SubtitleTimingResolver` uses usable Whisper word timestamps. When no usable
Whisper metadata exists, it returns `None`; no provider-specific WordBoundary
codec, ticks, or `*_word_boundaries.jsonl` sidecar participates in the active
route.

## Responsibilities

The subtitle layer can:

- generate subtitle files from real audio;
- request and preserve Whisper word timestamps;
- resolve usable Whisper timing or a clean absence of timing;
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
WhisperTimingParser
SingleLineModel
WordByWordModel
MicroCuePolicy
```

## Timing Resolution

The timing resolver follows:

```text
1. Whisper word timestamps, when usable
2. None
```

This allows subtitle models to use real timing evidence without introducing a
provider-specific timing format into runtime.

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

For every component and platform, ESTÁNDAR profiles live under
`config/profiles/<component>/<platform>/estandar/`; self-contained DISEÑO JSON
profiles live under `config/profiles/<component>/<platform>/design/`. Families
are discovered dynamically from the filesystem. DISEÑO is a profile family, not
a product component; an empty YouTube `design/` directory does not expose it.

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

## Piper ONNX

Used for:

- local declarative voice synthesis through the neutral TTS registry.

The current shared voice catalog resolves Davefx and Carlfm through
`backend_key="piper_onnx"`. Piper does not fabricate word timings.

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

## 36. Documentación

Cada documento tiene una responsabilidad; los demás lo enlazan en vez de
repetirlo.

| Documento | Responsabilidad |
|---|---|
| [README.md](../README.md) | Qué es el producto y por dónde empezar |
| [INSTALL.md](INSTALL.md) | Instalación y requisitos |
| [START.md](START.md) | Uso: arranque, menús, entradas y resultados |
| ARCHITECTURE.md (este) | Arquitectura interna |
| [SUBTITLES.md](SUBTITLES.md) | Referencia de los perfiles de subtítulos |
| [VOICEOVER.md](VOICEOVER.md) | Voz y duración de la locución |
| [ROADMAP.md](ROADMAP.md) | Estado actual y próximos pasos |
| [CHANGELOG.md](../CHANGELOG.md) | Historia de cambios |
| [AGENTS.md](../AGENTS.md) | Reglas para los agentes de IA que trabajan en el proyecto |

---

## 37. Estado de versión

- **Última versión cerrada:** `v2.0.0` (tag de Git).
- **En desarrollo:** la V3, abierta hasta la validación final del propietario.
  Sus cambios se anotan en el bloque [Unreleased] de
  [CHANGELOG.md](../CHANGELOG.md) y se publicará como `v3.0.0`.

---

## 38. Resumen

```text
AI VISUAL COMPOSER
│
├── GUION / IMAGEN / VIDEO      ruta estándar (StandardExecutionCoordinator)
│     guion → voz y audio → subtítulos → storyboard → imágenes → vídeo
│     └── GUION → Diseño        ruta DISEÑO (DesignExecutionCoordinator)
│           una descripción visual → una imagen o un clip
│
└── STUDIO                      material propio (StudioExecutionCoordinator)
      SOLO VIDEO · SRT + VIDEO · INTRO / OUTRO · MONTAJE VÍDEOS
      VIDEO + AUDIO | SRT · EXPORTAR SRT ➜  VIDEO

menús → ApplicationExecutionRequest → run_application() → coordinador
formatos: vertical (9:16) y horizontal (16:9), declarados en config/formats.json
perfiles: OperationalProfileKey + SubtitleProfileKey, descubiertos en config/profiles/
```

---

Copyright © 2026 Juan Bautista Galisteo Marqués.

AI Visual Composer es obra de Juan Bautista Galisteo Marqués, que lo creó y lo
mantiene.
