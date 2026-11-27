# Changelog

Aquí se registran los cambios importantes de AI Visual Composer.

---

## [Unreleased]

### Añadido

- Insignia con el estado de las pruebas automáticas.
- STUDIO como cuarto componente del producto, con sus modos actuales: SOLO
  VIDEO, SRT + VIDEO, INTRO / OUTRO, MONTAJE VÍDEOS, VIDEO + AUDIO | SRT y
  EXPORTAR SRT ➜  VIDEO.
- Perfiles de subtítulos declarados por componente (GUION, IMAGEN, VIDEO,
  STUDIO) y formato, agrupados en 5 familias con 8 modos de presentación
  (cue). Detalle completo en [SUBTITLES.md](docs/SUBTITLES.md).
- Efectos por palabra en los subtítulos: Palabra en color, Palabra en
  recuadro, Palabra aumentada, Revelado progresivo, Máquina de escribir y
  Karaoke continuo. Ver [SUBTITLES.md](docs/SUBTITLES.md).
- Formatos declarados en `config/formats.json`: vertical (9:16) y horizontal
  (16:9), cada uno con sus propios perfiles. Ver
  [ARCHITECTURE.md §4](docs/ARCHITECTURE.md#4-formatos).
- Pausas configurables en la voz, tras cada frase y entre párrafos. Ver
  [VOICEOVER.md](docs/VOICEOVER.md).
- Registro del error interno en `logs/` cuando el programa falla de verdad:
  guarda la fecha, la operación, el tipo, el mensaje y el detalle técnico
  (traceback), y la terminal dice en qué archivo está.
- README en cada carpeta de entrada de STUDIO (`input/studio/*/`).
- Identidad visual propia: logo AIVC, icono, banner y paleta azul.
- Progreso de los clips de vídeo (Wan) en la terminal: «Clip 2/3 · 1 min 30 s»
  cada 30 s y «Clip 2/3 listo» al acabar cada uno.
- Ajustes de Ollama en `config/ai.json`: `keep_alive`, modelo y razonamiento
  (`think`) del guion y opciones del storyboard, como el contexto (`num_ctx`).
  Ver [ARCHITECTURE.md §19](docs/ARCHITECTURE.md#19-perfiles-y-configuración).
- Semilla opcional en cada voz (`seed` en `config/voice_configs/*.json`): con
  ella, Piper da el mismo audio byte a byte en cada ejecución, para rehacer un
  vídeo idéntico. Sin ella, todo sigue igual. Ver
  [VOICEOVER.md §6](docs/VOICEOVER.md#6-repetir-el-mismo-audio-semilla).
- Voz Chatterbox Multilingual (`config/voice_configs/chatterbox_multilingual.json`),
  más natural que Piper: se genera en la GPU con su propio entorno de Python,
  en un proceso aparte que termina al acabar y deja la GPU libre. Su entorno y
  sus pesos van en `models/tts/`, dentro del proyecto; rutas y ajustes en su
  documento de voz; admite la semilla (`seed`). Ver
  [VOICEOVER.md §7](docs/VOICEOVER.md#7-chatterbox-multilingual) e
  [INSTALL.md §10](docs/INSTALL.md#10-voz-piper-onnx-chatterbox-y-kokoro).
- VIDEO + AUDIO | SRT: nueva opción «3. CORTAR EL VÍDEO DONDE ACABA EL AUDIO»
  en el menú AUDIO MÁS CORTO QUE EL VÍDEO, además de rellenar con silencio o
  con música: el vídeo dura lo que el audio. Ver
  [START.md, VIDEO + AUDIO | SRT](docs/START.md#75-video--audio--srt).
- Voces Kokoro Alex y Kokoro Dora (`config/voice_configs/kokoro_alex.json` y
  `kokoro_dora.json`; Kokoro 0.9.4, Apache-2.0): naturales y ligeras, en un
  proceso aparte como Chatterbox, con su entorno y sus pesos en `models/tts/`;
  rutas, idioma (`lang_code`), voz y velocidad (`speed`) en su documento de voz;
  admiten la semilla (`seed`). Ver
  [VOICEOVER.md §8](docs/VOICEOVER.md#8-kokoro).

### Cambiado

- La voz se genera con Piper (voces `piper_davefx` y `piper_carlfm`) en vez
  de Edge TTS.
- Las dos voces de Piper leen algo más despacio que la velocidad normal de su
  modelo. Ver [VOICEOVER.md](docs/VOICEOVER.md).
- Un valor no válido en el documento de una voz es un error de configuración
  que nombra ese documento (`config/voice_configs/…`), también al abrir el
  menú VOZ (antes, en el menú, era un error inesperado).
- Las voces que van en su propio proceso (Chatterbox y Kokoro) guardan la
  caché de CUDA y sus archivos temporales (los de torch también) en carpetas
  del proyecto declaradas en su documento (`backend_options.runtime`:
  `cuda_cache_dir`, `models/tts/_cache/cuda`, y `temp_dir`, `tmp/tts`), y no
  en `%APPDATA%\NVIDIA\ComputeCache` ni en el `%TEMP%` del sistema. Si falta una
  de las dos claves, la voz no se genera y el error CONFIG dice cuál. Ver
  [VOICEOVER.md §7](docs/VOICEOVER.md#7-chatterbox-multilingual).
- La carpeta de trabajo de cada síntesis de voz (todas las voces, Piper
  incluido) se crea dentro del proyecto, en `workspace_dir` de
  `config/voice.json` (`tmp/voice`), y no en el `%TEMP%` del sistema. Sin el
  archivo o la clave, error CONFIG. Ver
  [VOICEOVER.md §2](docs/VOICEOVER.md#2-documento-de-voz).
- Menú VOZ en este orden: «Chatterbox (natural, GPU)», «Piper Carlfm (rápida,
  CPU)», «Piper Davefx (rápida, CPU)», «Kokoro Alex» y «Kokoro Dora». El orden lo declara cada documento de
  voz (`menu_order`), no el nombre del archivo.
- Si la voz elegida falla, el error dice qué voz falló, qué pasó y que se puede
  elegir otra en el menú VOZ (antes: «No se pudo generar la voz.»). El
  programa sigue sin cambiar de voz por su cuenta.
- Los subtítulos usan siempre el texto del guion —también en los efectos por
  palabra— y no muestran texto en las pausas de la voz.
- Los MP3 de la voz y de la mezcla final se exportan a 44 100 Hz, para que
  editores como Sony Vegas lean bien su duración.
- La ejecución construye una única petición tipada que resuelven los
  coordinadores (estándar, STUDIO y DISEÑO), en vez de pasar opciones
  sueltas. Ver [ARCHITECTURE.md](docs/ARCHITECTURE.md).
- La terminal y la documentación están en español; el código se mantiene en
  inglés.
- La documentación de referencia, antes en la raíz, vive ahora en `docs/`.
- Licencia cambiada de MIT a GPL-3.0 o posterior; las versiones anteriores siguen con MIT.
- Ollama descarga el modelo de la GPU en cuanto responde (`keep_alive: 0`):
  Whisper y ComfyUI ya no comparten la tarjeta con él.
- El storyboard pide a Ollama un contexto de 8192 tokens, suficiente para unas
  25 escenas (antes, 4096: al límite con 3).
- El guion por tema se pide a Ollama sin razonamiento previo (`think: false`
  en `config/ai.json`): sale unas 4 veces más rápido y más cerca de la
  duración pedida.
- Guion por tema: solo se ajusta si queda corto. El margen está en
  `config/ai.json` (`script.duration_margin`: `below` 0.10, hasta un 10 % menos
  de lo pedido, y `above` null, sin tope por arriba); antes era un ±10 % fijo en
  el código. Se pide a Ollama una sola corrección de extensión (antes de la voz
  o, si no hizo falta, tras medirla); si sigue corto, se queda el mejor de los
  dos guiones y la terminal lo avisa en una línea, sin parar. Sin la clave, error
  CONFIG. Ver [ARCHITECTURE.md §12](docs/ARCHITECTURE.md#12-guion).
- Las escenas del storyboard terminan siempre al final de una frase, con los
  tiempos de la voz (Whisper), y duran lo que digan sus frases dentro de los
  límites `scene_seconds` de cada formato en `config/formats.json`; el vídeo
  final da a cada imagen la duración de su escena. Sustituye a
  `seconds_per_image` de los perfiles (una imagen cada 20 o 30 s, que cambiaba
  a mitad de frase). Ver [ARCHITECTURE.md §15](docs/ARCHITECTURE.md#15-storyboard).
- Escenas de unos 6 s: `scene_seconds` pasa de 4 · 6–8 · 10 a `min` 4,
  `target_min` 5, `target_max` 7 y `max` 8 en los dos formatos; se sigue
  cortando al final de frase.
- Los perfiles de IMAGEN y VIDEO piden 50 s de guion por tema (`duration`;
  antes 10, que eran de prueba).
- El primer prompt del guion por tema pide «unas N palabras; mejor algo más que
  menos» en vez de «N palabras como máximo; es un límite estricto», que llevaba
  a guiones cortos ahora que el margen no tiene tope por arriba. Cambia el texto
  que llega a Ollama (marcador `{palabras}` en `prompts/templates/script.txt`).
- Todos los textos que se envían a Ollama, Flux y Wan están en `prompts/`:
  las plantillas de cada petición (`templates/`, con `{marcadores}` para los
  datos), los criterios del storyboard (`criteria/`), la identidad visual y
  las reglas de la imagen (`image/`) y el prompt y negativo de Wan (`video/`).
  Los que dependen del tono tienen un archivo por tono y uno común. Si falta
  un archivo o un marcador, error de configuración con la ruta. Lo que llega a
  cada modelo no cambia. Ver
  [ARCHITECTURE.md §19](docs/ARCHITECTURE.md#19-perfiles-y-configuración).
- El prompt de cada imagen va en inglés y sin repeticiones: el storyboard
  escribe sus campos en inglés y la escena entra entera, desde la plantilla
  `prompts/image/scene.txt`, en vez de trozos de todos los campos partidos
  por las comas y recortados. La identidad visual no repite lo que ya dice la
  escena. Ver [ARCHITECTURE.md §16](docs/ARCHITECTURE.md#16-imágenes).
- El storyboard ya no propone objetos con letras (libros abiertos, periódicos,
  carteles, pantallas…); si alguno llega al prompt de la imagen, se cambia por
  su sustituto de `prompts/image/text_free_objects.json`.
- Cada escena tiene su propia semilla en la imagen (`images.seed` del perfil
  + número de escena) y se puede repetir; antes todas usaban la del workflow.
- Los clips de vídeo (Wan) duran 81 fotogramas a 12 fps (6,75 s) en vez de 49
  (4,08 s), en `frames` de `wan_i2v_<formato>.json`: casi no se repiten en las
  escenas de 6–8 s, a cambio de ~45 s más por clip.
- El movimiento de los clips de Wan (texto de cada nivel, palabras clave que
  lo eligen y restricciones de conservar y evitar) pasa de
  `motion_intent_builder.py` a `prompts/video/motion.json` y
  `motion_storyboard_field.txt`; lo que llega a Wan no cambia. Si falta un
  archivo, un texto o un marcador, error de configuración con la ruta. Ver
  [ARCHITECTURE.md §17](docs/ARCHITECTURE.md#17-clips-de-vídeo-i2v).
- Las restricciones de estabilidad de la imagen de origen de cada clip de Wan
  (conservar composición, geometría e identidad) pasan de
  `source_image_analysis.py` a `prompts/video/motion.json`
  (`source_stability_constraints`); lo que llega a Wan no cambia.
- El modelo, el dispositivo y el idioma de Whisper (`medium`, `cuda` y
  `Spanish`) se declaran en `config/whisper.json` en vez de estar en el
  código; la transcripción no cambia. Si falta una clave, error de
  configuración con la ruta. Ver
  [ARCHITECTURE.md §19](docs/ARCHITECTURE.md#19-perfiles-y-configuración).

- El programa borra de ComfyUI lo que deja en él (cada imagen de Flux, la
  copia de la imagen de cada clip y sus fotogramas) en cuanto lo ha copiado al
  proyecto, y nada más: cada trabajo usa su propia carpeta. Se desactiva con
  `cleanup_after_copy` en `config/comfyui.json`, que declara también las
  carpetas `input/` y `output/` de ComfyUI. Si un borrado falla, la terminal lo
  avisa y la ejecución sigue (antes, un fallo al limpiar la copia de la imagen
  paraba el clip). Ver [ARCHITECTURE.md §19](docs/ARCHITECTURE.md#19-perfiles-y-configuración).

### Corregido

- Los mensajes de error de entrada dicen qué falta y qué hacer, en vez de
  mostrarse como un fallo interno.
- El orden de montaje de MONTAJE VÍDEOS acepta `0` para cancelar, como el
  resto de entradas.
- Cada reintento de generación de imagen usa una semilla distinta, en vez de
  repetir siempre la misma imagen.
- Los nombres de los modos de STUDIO son los mismos en el menú, los
  resúmenes y los mensajes de error.
- Whisper ya no añade al SRT frases que no se dijeron en voz (repeticiones
  al final del audio o sobre la música).
- Un error de redondeo en los tiempos de Whisper (una palabra que acaba en
  27,720000000000002 s y la siguiente que empieza en 27,72 s) ya no descarta
  toda la transcripción: un solape de hasta 1 ms
  (`word_overlap_tolerance_seconds` en `config/whisper.json`) se toma como
  redondeo. Antes, los subtítulos de ese vídeo salían sin tiempos por palabra,
  el storyboard estimaba los cortes y SOLO VIDEO de STUDIO se paraba. Ver
  [ARCHITECTURE.md §14](docs/ARCHITECTURE.md#14-subtítulos).
- Los overlays y los efectos visuales ya no tiñen de morado el vídeo: los modos
  de mezcla `screen`, `add`, `lighten` y `overlay` se aplican en RGB y no sobre
  los planos YUV (que también mezclaban el color). El formato de la mezcla y
  las opciones de la conversión están en `config/video.json` (`layer_blend`);
  sin el archivo o una clave, error CONFIG con la ruta. Ver
  [ARCHITECTURE.md §18](docs/ARCHITECTURE.md#18-composición-del-vídeo-final).
- Un proyecto que ya existe no se sobrescribe sin avisar: si
  `output/<proyecto>/` ya existe, el menú PROYECTO pregunta «1. Sobrescribir»
  (se borra solo esa carpeta) o «2. Poner otro nombre»; si el nombre es nuevo,
  no pregunta nada. En todas las rutas (GUION, IMAGEN, VIDEO, DISEÑO y STUDIO).
- Sin pausas largas entre los trozos de Chatterbox (1–2,5 s, con ruido de
  fondo): antes de unirlos se recorta el silencio, el ruido bajo y los golpes
  cortos del principio y del final de cada trozo, según `segment_trim` de su
  documento de voz (−40 dB, obligatorio en Chatterbox). Con el guion de
  prueba, los huecos pasan a 0,3–0,4 s. Piper y Kokoro no cambian. Ver
  [VOICEOVER.md §7](docs/VOICEOVER.md#7-chatterbox-multilingual).
- VIDEO + AUDIO | SRT ya no pregunta «AUDIO MÁS CORTO QUE EL VÍDEO» ni rellena
  el final por unos milisegundos: si el audio es más corto por menos de
  `video_audio_srt.audio_tail_margin_seconds` de `config/studio.json` (0,1 s),
  cuenta como igual. Sin el archivo o la clave, error CONFIG con la ruta.
- CONVERTIR (y cualquier SRT sin tiempos por palabra) reparte el tiempo de cada
  bloque entre sus palabras por letras, no a partes iguales, en «Palabra única»
  y en la ventana deslizante; el resumen de CONVERTIR dice que los tiempos son
  estimados. Ver [SUBTITLES.md §4](docs/SUBTITLES.md).
- MONTAJE VÍDEOS e INTRO / OUTRO ya no codifican dos veces: si no hay
  subtítulos ni música y el vídeo ya tiene el formato de salida del perfil, se
  copia sin volver a codificarlo (más rápido y sin otra pérdida de calidad). Ver
  [ARCHITECTURE.md §8](docs/ARCHITECTURE.md#8-studio).

### Retirado

- El menú ELIMINAR OUTPUT, que con «1» borraba **toda** la carpeta `output/`
  (todos los proyectos) sin pedir confirmación. Los proyectos viejos se borran
  a mano.
- Las variables de entorno `MC_*` (identidad operacional, configuración de
  voz y overlays) y el modo «Solo guion».
- `validation/` y `AGENT_AI/` dejan de versionarse en Git (la evidencia de
  validación y la información privada de los asistentes siguen en el disco).
- TRADUCTOR deja de anunciarse en el README como componente del producto
  (sus archivos nunca llegaron a versionarse).
- La clave `provider` de `config/ai.json`: nadie la leía (el único proveedor es
  Ollama).
- El zoom y el paneo (`video_style.motion`) de los perfiles de vídeo
  (`perfil_video_<formato>.json`): ese perfil solo monta clips de Wan, que no
  llevan movimiento añadido. `video_style.motion` solo se lee cuando el montaje
  lleva imágenes fijas (perfiles de guion e imagen, que lo conservan).
- El modo «smart» de los overlays, en el que la IA elegía las carpetas y una
  regla por escena usaba dos nombres de carpeta escritos en el código: no se
  podía elegir desde el menú. Los overlays siguen con «Sí» / «No» y eligen
  igual que antes.
- Código y datos que ninguna ruta cargaba: las biblias visuales
  (`config/visual_bibles/`, `app/visual_bibles/`), las intenciones y lecturas
  narrativas (`app/intentions/`, `app/narrative_readings/`, `data/`), el lector
  `app/shared/simple_yaml.py` y el banco de pruebas OVB-001 (`app/benchmarks/`),
  con sus tests, y después sus modelos de dominio (`app/domain/visual_bible.py`,
  `intention.py` y `narrative_reading.py`), que solo usaban esos módulos.
- Dos datos que el montaje del vídeo recibía y ya nadie leía tras quitar el modo
  «smart»: el texto de cada escena que llegaba a los overlays y el registro de
  avisos que se pasaba a `VideoBuilder`. Los avisos del resumen siguen igual.

---

## [V2.0] - 2026-08

### Summary

AI Visual Composer V2.0 establishes the current stable architecture of the platform around three main product components:

```text
AI VISUAL COMPOSER

1. Guion
2. Imagen
3. Video
```

Diseño is maintained as an integrated capability and scalability path rather than a fourth main product component.

V2.0 consolidates the validated audiovisual generation architecture, permanent real-execution baselines, I2V video generation, Motion over generated clips, improved subtitle timing, and the current modular generation workflow.

### Added

- Added permanent V2.0 validation baselines for Guion, Imagen, and Video under `validation/01_VALIDACION_2026-08-24/`.
- Added complete baseline evidence including reports, JSON metrics, CSV metrics, inventories, sample manifests, representative samples, and charts.
- Added validated Video product routing with complete and partial execution modes.
- Added validated I2V clip generation and `video_clips_manifest.json`.
- Added validated Diseño -> Imagen and Diseño -> Video routes through dedicated manual visual inputs.
- Added ping-pong forward/reverse I2V temporal preparation using existing generated clips without regenerating Wan output.
- Added Motion support over generated I2V clips during FFmpeg composition.
- Added provider-neutral real subtitle timing support.
- Added Edge TTS `WordBoundary` metadata capture during voice generation.
- Added Whisper JSON word timestamp preservation during subtitle transcription.
- Added deterministic subtitle timing resolution using:

```text
Edge TTS WordBoundary
        ↓
Whisper Word Timestamps
        ↓
Whisper SRT Timing
```

- Added word-by-word subtitle micro-cue presentation handling for extremely short visual cues.
- Added focused automated tests for real subtitle timing, fallback behavior, word-by-word timing, and micro-cue presentation.

### Changed

- Consolidated the product architecture around Guion, Imagen, and Video.
- Defined Diseño as an integrated visual generation capability instead of an independent main product component.
- Updated the documented console structure to:

```text
AI VISUAL COMPOSER

1. Guion
2. Imagen
3. Video
```

- Updated baseline metadata so each main component has its own permanent validation evidence.
- Homogenized Video baseline metrics with Guion and Imagen for direct comparison.
- Integrated ping-pong/reverse I2V preparation into the validated Video architecture.
- Integrated Motion over generated I2V clips into the FFmpeg composition pipeline.
- Updated word-by-word subtitle rendering to use real word timing when available instead of relying exclusively on mathematical distribution inside Whisper segments.
- Preserved single-line subtitle behavior while allowing richer timing information to participate in subtitle optimization.
- Preserved fallback compatibility when real word timing metadata is unavailable.
- Separated permanent validation evidence from temporary runtime output.
- Reorganized official documentation by responsibility:

```text
README.md       -> Product overview
ARCHITECTURE.md -> Internal architecture
INSTALL.md      -> Initial installation
START.md        -> Daily startup and shutdown
ROADMAP.md      -> Development direction
CHANGELOG.md    -> Version history
validation/     -> Permanent validation evidence
```

### Subtitle Timing

The V2.0 subtitle architecture supports three timing levels:

```text
1. Edge TTS WordBoundary metadata
2. Whisper word timestamps
3. Whisper SRT segment timing
```

Real timing is used when available.

Legacy timing remains available as fallback.

The word-by-word presentation layer also includes micro-cue handling for extremely short subtitle events.

Micro-cue processing operates exclusively on subtitle presentation.

It does not modify:

- spoken words;
- source audio;
- script content;
- image generation;
- I2V generation;
- video generation logic.

### Video

V2.0 includes:

- image generation as source material for Video;
- ComfyUI I2V generation;
- Wan I2V support;
- generated video clip manifests;
- forward/reverse ping-pong temporal preparation;
- Motion over generated I2V clips;
- profile-driven FFmpeg composition;
- transitions;
- overlays;
- visual effects;
- fade;
- subtitles;
- final audiovisual composition.

The validated FFmpeg stage order remains:

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

### Diseño

V2.0 preserves Diseño as an integrated capability.

Supported direct visual routes:

```text
Diseño -> Imagen
Diseño -> Video
```

Dedicated inputs:

```text
input/guion_imagen.txt
input/guion_video.txt
```

Diseño -> Imagen produces standalone images.

Diseño -> Video produces standalone generated video clips.

These routes reuse the existing visual generation architecture and do not constitute a fourth main product component.

### Validation

Permanent V2.0 validation evidence contains:

```text
Guion    20 real executions
Imagen    8 real executions
Video     8 real executions
─────────────────────────
Total    36 real executions
```

Stored under:

```text
validation/01_VALIDACION_2026-08-24/guion/
validation/01_VALIDACION_2026-08-24/imagen/
validation/01_VALIDACION_2026-08-24/video/
```

The validation baselines preserve representative evidence from real system executions for future regression analysis and behavioral comparison.

### Automated Verification

Current recovered V2.0 state:

```text
864 automated tests passing
```

Additional verification:

- Python compilation over `app`, `tests`, and `certification`.
- `git diff --check`.
- Dedicated subtitle timing and micro-cue tests passing.

The historical V2.0 baseline was originally closed with:

```text
837 automated tests passing
```

The difference corresponds to the additional subtitle timing and presentation test coverage subsequently integrated into the current V2.0 state.

### Current Status

V2.0 is the current stable version and the reference state of AI Visual Composer.

The V2.0 Git checkpoint and full physical backup preserve this state before the next deep general validation. That later validation will determine real runtime behavior, not whether V2.0 should be preserved.

---

## [V.1] - 2026-08-13

### Summary

V.1 established the first stable general system version before the V2.0 product architecture and validation baseline.

### Changed

- Established AI Visual Composer `V.1` as the official stable general system version.
- Established `PR1` as the first official stable Git reference inside V.1.
- Normalized the public version-reference structure.
- Updated public documentation for the stable system.
- Documented the configured local Ollama model.
- Documented console modes, music selection, smart overlays, neutral overlay fallback, weighted overlay distribution, and category cooldown.
- Integrated Prompt Translator observability and evidence persistence.
- Integrated Visual Quality validation infrastructure.
- Reorganized technical reports and public documentation.
- Added required Edge TTS runtime dependency declaration.
- Updated public project-tree generation.
- Added structured Script Generation output validation.
- Corrected Prompt Translation with deterministic backend/model budget policy.
- Published Visual Intelligence Architecture v1.0.
- Retired transitional Visual Direction runtime components.
- Certified Visual Intelligence performance and runtime behavior.
- Integrated Visual Intelligence into the Image Runtime.
- Consolidated `EffectiveVisualBrief` as the canonical Visual Intelligence contract.
- Implemented Visual Analysis.
- Implemented Visual Reasoning.
- Implemented Visual Synthesis.
- Migrated storyboard generation toward Visual Truth 2.0.
- Migrated runtime narrative interpretation toward Visual Truth 2.0.
- Isolated legacy storyboard compatibility fields.
- Updated repository governance and private development boundaries.

### Visual Intelligence

V.1 established the architecture:

```text
Visual Truth
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
```

This architecture became the foundation of the later V2.0 visual generation system.

### Stable Git Reference

`PR1` was established as the first official stable Git reference of the V.1 system.

It served as a stable reference for:

- Git comparison;
- audits;
- optimizations;
- refactors;
- backend experiments;
- architectural evolution.

---

## [1.0.0] - Historical Planning Reference

### Summary

Historical planning reference for the first official AI Visual Composer baseline before adoption of the V.1 stable-version structure.

### Added

- Single cinematic Image Component runtime.
- Runtime adapters for storyboard scenes and generation results.
- Cinematic Direction orchestration.
- Prompt Translator.
- `BackendPrompt`.
- ComfyUI backend integration.
- Visual Quality contracts.
- Visual Quality gate.
- Image validation.
- Retry policy.
- Image Component certification infrastructure.
- Real certification campaign infrastructure.
- AI Visual Composer pipeline selector.

### Changed

- Project identity standardized as AI Visual Composer.
- Repository target standardized as `ai-visual-composer`.
- `ImageBuilder` became the coordinator of the certified Image Component runtime.
- Prompt construction moved toward backend-neutral contracts.
- Documentation was reorganized around official product documentation.
- Repository boundaries were strengthened for local AI models, generated output, logs, secrets, and external runtimes.

### Removed

- Legacy image runtime path.
- Legacy domain adapters.
- Legacy Visual Director runtime.
- Obsolete Visual Director tests.
- Obsolete legacy adapter tests.
- Duplicated temporary documentation.
- Temporary project structure documentation.
- Redundant frozen requirements.
- Generated output and debug logs from the working tree.

### Preserved

- Public video render facade.
- Profile-driven video configuration.
- FFmpeg video composition core.
- Motion.
- Transitions.
- Overlays.
- Visual Effects.
- Fade.
- Subtitles.
- Image manifest compatibility.
- Existing profile system.
- Existing ComfyUI workflow configuration.

### Validated

- Unit test suite.
- Python compilation.
- `git diff --check`.
- Image Component RC0 real smoke campaign.
- Product entry flow through the Image Pipeline.

---

## [0.1.0] - Motor Core Completed

### Summary

Initial stabilization of the modular FFmpeg video composition engine.

### Added

- Profile-driven video configuration.
- Modular video composition pipeline.
- Motion stage.
- Transition stage using FFmpeg `xfade`.
- Overlay stage.
- Visual Effects stage.
- Fade stage.
- Subtitle stage.
- FilterPipeline execution layer.
- CommandPlanBuilder.
- CommandBuilder.
- VideoBuilder public facade.
- Runner execution layer.
- VideoValidator output validation.
- Initial professional project documentation.

### Stabilized

- Visual Effects.
- Overlays.
- Motion.
- Transitions.
- CommandBuilder.
- VideoBuilder.
- FFmpeg input handling.
- `filter_complex` generation.
- Auxiliary input indexing.
- Horizontal rendering.
- Vertical rendering.
- Combined-layer rendering.

---

## Version History

```text
0.1.0
   ↓
1.0.0
   ↓
V.1
   ↓
V2.0
```

`V2.0` represents the current stable architecture of AI Visual Composer.

---

Copyright © 2026 Juan Bautista Galisteo Marqués.

AI Visual Composer was created and is maintained by Juan Bautista Galisteo Marqués.
