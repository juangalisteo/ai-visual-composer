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
  DISEÑO tienen cada uno su coordinador; el despachador solo elige cuál.
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
| **GUION** | Un texto completo escrito por el usuario (`input/guion.txt`) | Un proyecto de Imagen o de Video con ese texto tal cual, o DISEÑO |
| **IMAGEN** | Un tema o una idea (`input/tema.txt`); la IA escribe el guion | Un vídeo hecho con imágenes generadas |
| **VIDEO** | Un tema o una idea (`input/tema.txt`); la IA escribe el guion | Un vídeo hecho con clips generados a partir de esas imágenes (imagen a vídeo, I2V) |
| **STUDIO** | Material propio ya grabado (vídeo, audio, SRT) en `input/studio/` | El vídeo terminado (subtítulos, audio nuevo, montaje, intro/outro) o un SRT |

GUION, IMAGEN y VIDEO comparten la **ruta estándar** ([apartado 5](#5-ruta-estándar-guion-imagen-y-video)).
Dentro de GUION, el destino «Diseño» abre **DISEÑO**
([apartado 7](#7-diseño)), que no es un quinto componente. STUDIO tiene su
propia ruta ([apartado 8](#8-studio)) y no usa la IA generativa.

**DISEÑO no es la familia `design`.** La palabra aparece en dos sitios que no
tienen relación:

| Nombre | Qué es |
|---|---|
| **DISEÑO** | GUION → Diseño → Imagen o Video: genera una sola imagen o un solo clip a partir de una descripción visual directa |
| **Familia de subtítulos `design` (MODO CONCIENCIA)** | Una de las familias de perfiles de subtítulos; en el menú se llama «MODO CONCIENCIA» ([SUBTITLES.md](SUBTITLES.md#2-familias)) |

---

## 3. Flujo de ejecución

```text
python main.py
   ↓
main.py                      valida config/formats.json y config/fonts.json antes del primer menú
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

- En la ruta estándar y en DISEÑO lo imprime `PipelineTelemetry.complete()`
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

## 7. DISEÑO

DISEÑO parte de una descripción visual directa escrita por el usuario,
no de un guion narrado. Se entra por GUION → DESTINO → Diseño → Imagen o Video.

| Destino | Entrada | Etapas | Resultado |
|---|---|---|---|
| Diseño → Imagen | `input/guion_imagen.txt` | Interpreta la descripción (Ollama) → una escena → una imagen (ComfyUI + Flux) | Una sola imagen |
| Diseño → Video | `input/guion_video.txt` | Interpreta la descripción (Ollama) → una escena → una imagen → un clip (ComfyUI + Wan) | Un solo clip |

- `DesignExecutionCoordinator` comprueba que la descripción produzca
  **exactamente una escena**, y después una sola imagen o un solo clip.
- DISEÑO **no** genera voz, música ni subtítulos, y **no** compone un
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

El menú ENTRADA ofrece seis modos (textos tal cual en la terminal). Qué hace
cada uno por dentro:

| Modo | Qué hace |
|---|---|
| `SOLO VIDEO` | Whisper transcribe el audio del vídeo y el SRT se adapta al perfil de subtítulos elegido antes de pintarlo |
| `SRT + VIDEO` | Pinta el SRT del usuario **tal cual** (siempre ORIGINAL): ni Whisper ni cambios de texto o de tiempos |
| `INTRO / OUTRO` | Añade una intro, un outro o ambos al vídeo |
| `MONTAJE VÍDEOS` | Une varios vídeos en el orden que se elige, con o sin transiciones, y sin subtítulos |
| `VIDEO + AUDIO \| SRT` | Sustituye el audio del vídeo por uno nuevo y, si hay SRT, lo pinta tal cual |
| `EXPORTAR SRT ➜  VIDEO` | No genera vídeo: TRANSCRIBIR saca un SRT de un MP4 o MP3 con Whisper; CONVERTIR adapta un SRT al perfil de subtítulos elegido |

Qué archivo va en cada carpeta de `input/studio/`, cómo se eligen y qué
pregunta cada menú: [START.md, apartado 7](START.md#7-studio).

### Cómo se tratan los subtítulos en STUDIO

- **SRT + VIDEO pinta siempre el SRT tal cual.** No es una opción del menú: el
  perfil de subtítulos elegido solo aporta el aspecto (`render_style`) y, si lo
  declara, las mayúsculas (`cue_policy.text_case`). El orden, el texto y los
  tiempos de las líneas no cambian. Es así a propósito: si SOLO VIDEO transcribe
  mal una palabra, el usuario corrige el SRT y lo vuelve a pintar con SRT + VIDEO
  ([AGENTS.md](../AGENTS.md) §8). Los efectos por palabra reparten tiempos
  aproximados **dentro** de cada línea, sin tocar los tiempos del SRT
  ([SUBTITLES.md](SUBTITLES.md#8-tiempos-por-palabra-de-los-efectos)).
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
| `input/guion_imagen.txt` | DISEÑO → Imagen | La descripción visual de una imagen |
| `input/guion_video.txt` | DISEÑO → Video | La descripción visual de un clip |
| `input/studio/<modo>/` | STUDIO | Vídeos, audios y SRT de cada modo ([START.md, apartado 7](START.md#7-studio)) |

- Los cuatro `.txt` están en el repositorio vacíos: el usuario escribe en ellos.
  Cómo evitar que sus cambios salgan en Git está en [INSTALL.md](INSTALL.md).
- STUDIO descubre sus archivos por extensión, no por nombre; cómo los elige:
  [START.md, apartado 7](START.md#qué-archivo-va-en-cada-carpeta). El
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
- Cómo se cargan y validan los perfiles:
  [apartado 19](#19-perfiles-y-configuración). Familias, modos de cue y estilos:
  [SUBTITLES.md](SUBTITLES.md).

---

## 12. Guion

`ScriptOperation` llama a `ScriptPreparationService` (`app/modules/script/`),
que prepara el texto que se va a narrar y lo guarda en
`output/<proyecto>/scripts/guion.txt`. El origen del texto depende del
componente:

| Origen (`script_source`) | Componente | Qué hace |
|---|---|---|
| `manual` | GUION | Usa `input/guion.txt` tal cual. Si falta o está vacío, la ejecución se para con un error |
| `generated` | IMAGEN y VIDEO | Lee `input/tema.txt`, monta el prompt con `PromptEngine` (`app/core/prompt_engine.py`) y se lo pide a Ollama con `ScriptBuilder` |

- **El prompt** se compone con archivos de `prompts/`: el tono
  (`prompts/tones/<tone>.txt`, según la clave `tone` del perfil), la tarea
  (`prompts/tasks/script.txt`), el formato (`prompts/formats/<formato>.txt`) y
  las reglas de idioma y restricciones (`prompts/rules/`). Incluye además el
  rango de palabras que corresponde a la duración (`duration`) del perfil; el
  cálculo está en [VOICEOVER.md](VOICEOVER.md).
- **La respuesta se valida antes de usarla** (`ScriptOutputValidator`): se
  rechaza si trae Markdown, bloques de código, JSON, XML, encabezados del
  modelo, recuentos de palabras o comentarios, o si se sale del rango de
  palabras. En ese caso `ScriptBuilder` repite la petición una vez, indicando el
  motivo; si la segunda respuesta tampoco vale, la ejecución se para con
  `InvalidScriptOutputError`. El guion nunca se recorta.

---

## 13. Voz y música

```text
config/voice_configs/<voz>.json    documento de la voz (backend_key, modelo, idioma)
        ↓
TtsBackendRegistry                 elige el backend por su backend_key exacto
        ↓
PiperBackend                       sintetiza un WAV en una carpeta temporal
        ↓
VoiceBuilder                       lo publica como audio/voz.mp3
        ↓
AudioMixer                         mezcla la voz con la música → audio/audio_final.mp3
```

- **Voces.** El menú VOZ lista los documentos de `config/voice_configs/` por su
  `display_name` («Carlfm», «Davefx»). Qué declara cada documento y cómo se
  añade una voz: [VOICEOVER.md](VOICEOVER.md#2-documento-de-voz).
- **Backend.** `TtsBackendRegistry` (`app/modules/audio/`) solo resuelve claves
  técnicas exactas: nunca elige el backend por un nombre visible, un componente
  o un menú. Hoy el único registrado es Piper (`PiperBackend`), que se ejecuta
  en el propio proceso de Python. GUION, IMAGEN y VIDEO solo conocen
  `VoiceBuilder`.
- **Tiempos por palabra.** Piper no devuelve tiempos por palabra. El contrato
  neutro (`TtsWordTiming`) está preparado para un backend que sí los dé; hoy los
  tiempos de los subtítulos salen siempre de Whisper
  ([apartado 14](#14-subtítulos)).
- **Música.** El menú MÚSICA ofrece «Aleatoria» o «Sin música». Con
  «Aleatoria», `MusicSelector` elige al azar una categoría (cada subcarpeta de
  `assets/music/`) y una pista de ella. `AudioMixer` la pone en bucle por debajo
  de la voz, con entrada y salida suaves, y la corta a la duración de la voz;
  sin música, `audio_final.mp3` es una copia de `voz.mp3`.
- **Frecuencia de los MP3.** `voz.mp3` y `audio_final.mp3` se publican siempre
  a 44 100 Hz (`PUBLISHED_MP3_SAMPLE_RATE_HZ`, `app/modules/audio/`), sea cual
  sea la frecuencia de la voz de Piper, para que los editores de vídeo lean bien
  su duración.

Duración de la locución y ritmo de las voces: [VOICEOVER.md](VOICEOVER.md).

---

## 14. Subtítulos

La capa de subtítulos (`app/modules/subtitles/`) transcribe la voz, corta el
texto en líneas según el perfil de subtítulos elegido y prepara su pintado. La
referencia de familias, modos de cue, estilos y efectos está en
[SUBTITLES.md](SUBTITLES.md).

```text
audio/voz.mp3 + silencios que escribió la voz
    ↓
SubtitleBuilder            Whisper → SRT + JSON con los tiempos de cada palabra y esos silencios
    ↓
WhisperRepetitionFilter    quita las frases que Whisper inventa al final
    ↓
SrtOptimizer               texto del guion + tiempos de Whisper → líneas según cue_policy.mode
    ↓
subtitles/subtitulos.srt
    ↓
vídeo final                se pinta con el render_style del perfil (apartado 18)
```

- **Transcripción.** `SubtitleBuilder` lanza Whisper como proceso aparte
  (`python -m whisper`) con una configuración fija (`WhisperTranscriptionConfig`:
  modelo `medium`, idioma español, tiempos por palabra). En la ruta estándar
  transcribe la voz sin música (`voz.mp3`). En STUDIO, SOLO VIDEO y EXPORTAR SRT
  → TRANSCRIBIR usan el mismo `SubtitleBuilder`, tras sacar el audio del vídeo
  con FFmpeg (`ExternalMediaSubtitlePreparationService`).
- **Frases inventadas.** Al final de un audio, donde ya no hay voz, Whisper a
  veces repite una frase anterior. `WhisperRepetitionFilter` quita del SRT y del
  JSON un segmento solo si repite texto anterior y además se da una de estas
  dos situaciones: dura demasiado poco para haberse dicho (repetición en
  silencio), o va detrás de la última voz, en una zona que Whisper marca sin voz
  y con palabras de muy baja confianza (repetición sin voz). Lo avisa en la
  terminal y anota en el JSON cada segmento descartado con su motivo.
- **Pausas de la voz.** En la ruta estándar la voz sabe dónde puso cada pausa:
  `PiperBackend` devuelve el inicio y el fin de cada silencio que escribe
  (`TtsSynthesisResult.pauses`, en segundos de `voz.mp3`), `VoiceBuilder` los
  deja en `last_pauses` y `SubtitleBuilder` los anota en el JSON como
  `voice_pauses`, sin tocar los tiempos de Whisper. Al leer el JSON,
  `SubtitleTimingResolver` saca las palabras de esos silencios: la que empieza
  antes y acaba dentro termina donde empieza el silencio, la que empieza dentro
  empieza donde acaba (si cae entera dentro, queda de duración 0 en ese punto)
  y la que lo cruza entero se queda en el lado donde tiene más tiempo. Así
  ninguna línea sigue en pantalla durante una pausa de la voz, ni en el SRT ni
  en el ASS. Sin `voice_pauses` (STUDIO, o una voz sin pausas) los tiempos son
  los de Whisper.
- **Texto y tiempos.** En la ruta estándar manda el **texto del guion**: Whisper
  solo aporta los tiempos. `reconcile_timing_text` alinea palabra a palabra el
  guion con lo que oyó Whisper (`difflib.SequenceMatcher`, sin contar
  mayúsculas, tildes ni signos) y pone siempre las palabras del guion, con sus
  mayúsculas y signos. Una palabra igual, o cambiada por otra («quizás» por
  «quizá»), toma el tiempo de la de Whisper; un tramo con otro número de
  palabras («serie» por «ser y») reparte su tiempo entre las del guion en
  proporción a sus letras, solo en el tiempo con voz: se salta las pausas de la
  voz que caen dentro del tramo (`approximate_voiced_word_timings`,
  `policies/timing.py`); una palabra del guion que Whisper no oyó comparte el
  tiempo de la anterior (o de la siguiente, si la anterior cierra frase o
  párrafo), y una palabra que Whisper añade se quita. `SrtOptimizer` pasa el SRT por
  `SubtitleCueTransformer`, que crea el modelo de corte con `CueModelRegistry`
  según `cue_policy.mode` del perfil y aplica las mayúsculas si el perfil las
  pide. Los tiempos por palabra los lee `SubtitleTimingResolver` del JSON de
  Whisper (`subtitulos_whisper.json`); si no hay tiempos utilizables, el modelo
  trabaja solo con el SRT. Cómo corta cada modo:
  [SUBTITLES.md](SUBTITLES.md#4-cue_policy-cómo-se-corta-el-texto).
- **Pintado.** Según su `render_style`, un perfil se pinta de forma estática
  (filtro `subtitles` de FFmpeg con un estilo fijo) o dinámica (un ASS temporal
  con efectos, filtro `ass`):
  [SUBTITLES.md](SUBTITLES.md#6-pintado-estático-y-dinámico). Las fuentes salen
  de `assets/fonts/` y se declaran en `config/fonts.json` (nombre, alias,
  archivo y reserva).
- **STUDIO** trata los subtítulos a su manera (SRT + VIDEO y VIDEO + AUDIO | SRT
  pintan el SRT tal cual): [apartado 8](#8-studio).
- Un modo de cue nuevo es una capacidad nueva: una clase en
  `app/modules/subtitles/modes/` y su entrada en `CueModelRegistry`. Un perfil o
  una familia nuevos que usen modos existentes son solo configuración
  ([apartado 19](#19-perfiles-y-configuración)).

---

## 15. Storyboard

`StoryboardBuilder` (`app/modules/storyboard/`) convierte el guion en escenas
visuales y las guarda en `output/<proyecto>/storyboard/storyboard.json`.

| Paso | Qué hace | Quién |
|---|---|---|
| Número de escenas | Duración del audio entre `video_style.storyboard.seconds_per_image` del perfil, redondeando hacia arriba | `StoryboardBuilder` |
| Reparto del texto | Divide el guion en ese número de fragmentos; cada escena dura lo mismo (la duración del audio entre el número de escenas) | `SceneSplitter` |
| Descripción visual | Pide a Ollama, con respuesta JSON de esquema fijo, qué se ve en cada escena | `StoryboardAIBuilder` |
| Comprobación | Lee la respuesta y exige una descripción por escena | `StoryboardResponseParser`, `StoryboardValidator` |
| Unión | Junta el texto, la duración y la descripción de cada escena | `StoryboardComposer` |

La descripción visual de cada escena se llama **Visual Truth**: lo que tiene que
verse, sin instrucciones para ningún backend. Sus campos son
`visible_subject`, `visible_action`, `visible_environment`, `time_context`,
`key_objects`, `spatial_relationships`, `continuity_links`, `abstract_source`,
`filmable_interpretation`, `visual_constraints` y `visual_truth_status`. El
prompt sale de `prompts/tasks/storyboard.txt`, con el tono y el formato del
perfil.

---

## 16. Imágenes

`ImageBuilder` (`app/modules/images/`) genera una imagen por escena del
storyboard, del tamaño `video_style.width` × `video_style.height` del perfil.
Cada escena recorre esta cadena:

```text
escena del storyboard (Visual Truth)
    ↓  StoryboardSceneAdapter            + el image_guidance del formato (config/formats.json)
Visual Intelligence                      análisis → razonamiento → síntesis
    ↓
EffectiveVisualBrief
    ↓  CinematicDirectionOrchestrator    composición, fotografía, luz, color, movimiento, continuidad
Prompt Translation                       prompt final dentro del presupuesto del modelo
    ↓  ComfyUIAdapter + ImagePromptSystem
ComfyUI + Flux                           config/comfyui_flux_workflow_api.json
    ↓
control de calidad                       ImageQualityFlowCoordinator
    ↓
images/scene_*.png + images/images_manifest.json
```

| Etapa | Dónde | Qué hace |
|---|---|---|
| Visual Intelligence | `app/visual_intelligence/` (`analysis/`, `reasoning/`, `synthesis/`) | Interpreta la escena: qué es importante, qué intención tiene, qué la une a las demás y qué conflictos hay. El resultado es un `EffectiveVisualBrief` |
| Dirección cinematográfica | `app/cinematic_direction/` y los directores de `app/*_direction/` | Convierte el brief en decisiones de composición, fotografía, luz, color, movimiento y continuidad |
| Traducción a prompt | `app/prompt_translation/` | Escoge y ordena la información visual, quita duplicados y ajusta el prompt al presupuesto de tokens del modelo; no reinterpreta la escena |
| Backend | `app/backend_adapters/`, `app/modules/images/backends/comfyui_backend.py` | Adapta el prompt a ComfyUI y lanza el workflow de Flux |

- Ollama no interviene en estas etapas: la imagen parte solo de la Visual
  Truth del storyboard.
- **Control de calidad.** Cada imagen pasa por `ImageQualityFlowCoordinator`
  (`app/visual_quality/`). Comprueba que el archivo exista y no esté vacío y,
  con NudeNet en local (modelo en `models/`), que no haya desnudos; las demás
  comprobaciones de `default_product_quality_checks()` solo fallan si reciben
  una señal explícita. Si una imagen falla, se vuelve a generar; si tras los
  intentos sigue fallando, la ejecución se para y pide revisión manual.
  Ningún resultado rechazado llega al manifiesto.
- **Evidencias.** Cada etapa deja su resultado por escena en
  `images/evidence/`, para poder rastrear de dónde sale cada prompt.
- Las biblias visuales (`config/visual_bibles/`, `app/visual_bibles/`) y los
  datos de `data/` existen como capacidad, pero hoy ninguna ruta del menú los
  carga.

---

## 17. Clips de vídeo (I2V)

En VIDEO (y en GUION → Video) cada imagen se convierte en un clip con Wan
(imagen a vídeo, I2V). Lo hace `generate_video_clips()`
(`app/modules/video_component/clip_batch.py`) con `VideoComponentBuilder`:

```text
imagen de la escena + su Visual Truth
    ↓  SourceImageAnalyzer        qué hay en la imagen
    ↓  MotionIntentBuilder        qué movimiento pide la escena
    ↓  VideoPromptTranslator      prompt de vídeo
    ↓  ComfyUIVideoAdapter        workflow config/comfyui_wan22_ti2v_i2v_workflow_api.json
ComfyUI + Wan
    ↓
video_clips/scene_NNN.mkv + video_clips/video_clips_manifest.json
```

- **Parámetros.** Salen del documento Wan del formato
  (`config/profiles/video/<formato>/wan_i2v_<formato>.json`,
  `"kind": "video_component"`): tamaño de generación, número de fotogramas, FPS,
  semilla y muestreo. Si en un formato hay más de uno o ninguno, la ejecución se
  para con un error.
- **Salida sin pérdida.** Con `delivery.intermediate_output` = `lossless_ffv1`,
  los fotogramas que devuelve ComfyUI se guardan como un clip FFV1 (`.mkv`). Esos
  clips son intermedios: se borran cuando el vídeo final se ha publicado bien.
- DISEÑO → Video usa el mismo `VideoComponentBuilder` para su único
  clip ([apartado 7](#7-diseño)).
- La llamada a Wan no tiene tiempo límite, a propósito
  ([AGENTS.md](../AGENTS.md) §8).

---

## 18. Composición del vídeo final

`VideoBuilder` (`app/modules/video/`) monta el MP4 final con un único comando
FFmpeg. Usa `audio/audio_final.mp3` y reparte su duración a partes iguales
entre las escenas. El grafo de filtros se construye por etapas, siempre en este
orden:

| Etapa | Qué hace | Clave del perfil (`video_style`) |
|---|---|---|
| Movimiento | Imagen fija: zoom o desplazamiento (`zoompan`). Clip I2V: se alarga hasta la duración de la escena (ver abajo); no lleva movimiento añadido | `motion` |
| Transiciones | Une las escenas con una transición (`xfade`) del tipo y la duración del perfil | `transitions` |
| Overlays | Superpone vídeos de `assets/videos/overlays/<categoría>/` con mezcla y opacidad | `overlays` |
| Efectos visuales | Otra capa de vídeos superpuestos, de `assets/videos/visual_effects/` | `visual_effects` |
| Fundido | Fundido de entrada y de salida del vídeo completo | `fade` |
| Subtítulos | Pinta el SRT con el perfil de subtítulos ([apartado 14](#14-subtítulos)); no existe en «Proyecto completo sin subtítulos» | — |

- **Clips I2V.** Un clip de Wan dura menos que su escena. Dentro del mismo
  grafo, `I2VClipTransform` lo reproduce hacia delante y hacia atrás sin repetir
  los fotogramas de los extremos, lo repite lo necesario, lo corta a la duración
  exacta de la escena y lo ajusta al tamaño del perfil. No se vuelve a generar.
- **Overlays.** El menú OVERLAYS («Sí» / «No») decide si la etapa se aplica.
  Con «Sí», `OverlaySelector` elige carpeta (categoría) y archivo según el
  perfil: al azar, con pesos y, si hay alternativa, sin repetir el archivo ni la
  categoría de la escena anterior.
- **Efectos visuales.** Tienen la misma forma que los overlays, pero se activan
  solo con `visual_effects.enabled` del perfil.
- **Validación.** El render se escribe primero en un archivo temporal; después
  `VideoValidator` comprueba que su duración no se aleje de la del audio más de
  `validation.max_duration_difference` del perfil. Solo entonces se publica como
  `video/<proyecto>.mp4`.
- **INTRO / OUTRO.** Si se eligió, `IntroOutroComposer` añade la intro y el
  outro al vídeo ya validado.
- **Diagnóstico.** Cada render deja `video/ffmpeg_diagnostics.json` con el
  comando y el resultado; si FFmpeg falla, el error remite a ese archivo.

---

## 19. Perfiles y configuración

Todo lo que cambia entre ejecuciones está en `config/` y `prompts/`:

| Ruta | Contenido |
|---|---|
| `config/formats.json` | Los formatos ([apartado 4](#4-formatos)) |
| `config/fonts.json` | Las fuentes de los subtítulos: por cada una, su archivo en `assets/fonts/`, sus alias y, si la tiene, su reserva (otra fuente del catálogo, un solo nivel) |
| `config/ai.json` | Proveedor y modelo de Ollama |
| `config/voice_configs/*.json` | Una voz por documento ([apartado 13](#13-voz-y-música)) |
| `config/comfyui_flux_workflow_api.json`, `config/comfyui_wan22_ti2v_i2v_workflow_api.json` | Workflows de ComfyUI para imágenes (Flux) y clips (Wan) |
| `config/profiles/<componente>/<formato>/*.json` | Perfil operacional; en VIDEO, también el documento Wan |
| `config/profiles/<componente>/<formato>/<familia>/subtitulos/*.json` | Perfiles de subtítulos |
| `prompts/` | Textos de los prompts: `tones/`, `tasks/`, `formats/` y `rules/` |

**Perfil operacional** (`OperationalProfileKey`). En GUION, IMAGEN y VIDEO
declara:

| Clave | Para qué sirve |
|---|---|
| `component`, `format`, `profile_id` | Identidad: tienen que coincidir con la carpeta |
| `tone` | Archivo de `prompts/tones/` |
| `duration` | Duración pedida al guion generado (IMAGEN y VIDEO; GUION no la lleva) |
| `builders` | Qué etapas puede ejecutar el componente |
| `video_style` | Tamaño, FPS y las etapas del vídeo final ([apartado 18](#18-composición-del-vídeo-final)); `storyboard.seconds_per_image` |
| `validation` | Diferencia de duración que se tolera en el vídeo final |
| `video`, `audio` | Códecs y calidad del MP4 final |

El control de calidad de las imágenes no tiene clave en el perfil: se aplica
siempre ([apartado 16](#16-imágenes)).

En STUDIO, el perfil operacional solo tiene la identidad y el bloque `studio`
(`input`, `output`, `montage` y `music`; [apartado 8](#8-studio)).

**Cómo se cargan:**

- `ProfileResolver` (`app/shared/profile_resolver.py`) descubre los perfiles
  operacionales leyendo `config/profiles/<componente>/<formato>/`. Reconoce un
  perfil por su contenido, no por el nombre del archivo, y exige que
  `component`, `format` y `profile_id` coincidan con la ruta; un `profile_id`
  repetido es un error. Al cargarlo comprueba además que el tamaño de
  `video_style` cuadre con la orientación del formato.
- `SubtitleProfileResolver` (`app/shared/subtitle_profile_resolver.py`)
  descubre las familias como subcarpetas del formato (una familia sin perfiles no
  aparece) y valida cada perfil al descubrirlo: identidad, `cue_policy` con un
  modo conocido y `render_style` completo.
- `ConfigManager` (`app/shared/config_manager.py`) recibe la clave
  operacional y la voz que viajan en la petición y da a cada etapa su
  configuración. No lee variables de entorno.
- Un perfil o una familia nuevos son solo archivos: aparecen en el menú sin
  tocar Python.

---

## 20. Programas externos

Todos se ejecutan en el propio equipo. Su instalación y sus modelos están en
[INSTALL.md](INSTALL.md).

| Programa | Para qué | Cómo se usa |
|---|---|---|
| **Ollama** | Guion (IMAGEN y VIDEO), descripción visual del storyboard e interpretación de DISEÑO | HTTP local (`OllamaProvider`, `app/providers/`); el modelo está en `config/ai.json`. Sin tiempo límite |
| **ComfyUI + Flux** | Imágenes | HTTP local (`http://127.0.0.1:8188`) con el workflow de Flux |
| **ComfyUI + Wan** | Clips I2V | El mismo servidor, con el workflow de Wan. Sin tiempo límite |
| **Piper** | Voz | Librería de Python, en el mismo proceso, con el modelo ONNX de cada voz |
| **Whisper** (OpenAI) | Transcripción y tiempos por palabra | Proceso aparte (`python -m whisper`) |
| **NudeNet** | Control de desnudos en las imágenes | Librería de Python, con su modelo ONNX |
| **FFmpeg** | Mezcla de audio, vídeo final, render de STUDIO, intro/outro y extracción de audio para Whisper | Proceso aparte (`ffmpeg`, `ffprobe`) |

Que Ollama y Wan no tengan tiempo límite es intencionado: con límites se
cortaban generaciones válidas ([AGENTS.md](../AGENTS.md) §8).

---

## 21. Qué está en el repositorio

**En Git:**

- El código: `main.py`, `app/`, `certification/` (campaña de certificación de
  la generación de imágenes) y `tools/`.
- La configuración: `config/`, `prompts/` y `data/`.
- `tests/`.
- `assets/`: las fuentes Anton y Oswald y `assets/README.md`.
- Los `.txt` de `input/` (vacíos) y las carpetas de `input/studio/` (con su
  `.gitkeep`).
- La documentación (`docs/`, README, CHANGELOG, LICENSE), `requirements.txt`,
  `.env.example` y las reglas para agentes de IA (`AGENTS.md`).

**Fuera de Git (solo en el equipo):**

- `output/` (proyectos generados) y `logs/`.
- `models/` y `ComfyUI/`: programas y modelos de IA.
- El contenido de `input/studio/` y de `assets/videos/intro_outro/`.
- La música, los overlays, los efectos visuales y las fuentes Gotham Narrow
  Bold y Uni Sans Heavy ([assets/README.md](../assets/README.md)).
- Secretos (`.env`), entornos virtuales, cachés y archivos temporales.
- Los espacios privados de trabajo de los agentes ([AGENTS.md](../AGENTS.md)).

La documentación y la configuración compartida no llevan rutas personales del
equipo.

---

## 22. Documentación

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

## 23. Estado de versión

- **Última versión cerrada:** `v2.0.0` (tag de Git).
- **En desarrollo:** la V3, abierta hasta la validación final del propietario.
  Sus cambios se anotan en el bloque [Unreleased] de
  [CHANGELOG.md](../CHANGELOG.md) y se publicará como `v3.0.0`.

---

## 24. Resumen

```text
AI VISUAL COMPOSER
│
├── GUION / IMAGEN / VIDEO      ruta estándar (StandardExecutionCoordinator)
│     guion → voz y audio → subtítulos → storyboard → imágenes → vídeo
│     └── GUION → Diseño        DISEÑO (DesignExecutionCoordinator)
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
