# Voz de AI Visual Composer

Este documento es la referencia de la voz: qué voces hay, cómo se declara cada
una, cuántas palabras se piden al guion generado, a qué ritmo lee de verdad
Piper, cómo hace las pausas, cómo repetir el mismo audio (semilla), cómo
funciona Chatterbox y qué licencia tiene cada voz.

Otros documentos:

| Para saber… | Documento |
|---|---|
| Cómo se genera y se mezcla el audio (Piper, música, `audio_final.mp3`) | [ARCHITECTURE.md, apartado 13](ARCHITECTURE.md#13-voz-y-música) |
| Cómo se escribe el guion y cómo se valida | [ARCHITECTURE.md, apartado 12](ARCHITECTURE.md#12-guion) |
| Cómo se instalan Piper y sus modelos, y el entorno de Chatterbox | [INSTALL.md, apartado 10](INSTALL.md#10-voz-piper-onnx-y-chatterbox) |
| Subtítulos | [SUBTITLES.md](SUBTITLES.md) |

---

## 1. Voces

| Documento | En el menú VOZ | Modelo | Idioma |
|---|---|---|---|
| `config/voice_configs/chatterbox_multilingual.json` | Chatterbox (natural, GPU) | Chatterbox Multilingual, su voz de serie: `models/tts/chatterbox/weights/` (apartado 7) | `es-ES` |
| `config/voice_configs/piper_carlfm.json` | Carlfm | `models/audio/piper/es_ES_carlfm/es_ES-carlfm-x_low.onnx` | `es-ES` |
| `config/voice_configs/piper_davefx.json` | Davefx | `models/audio/piper/es_ES_davefx/es_ES-davefx-medium.onnx` | `es-ES` |

- El menú VOZ lista los documentos de `config/voice_configs/` por orden de
  nombre de archivo y muestra su `display_name`:

  ```text
  VOZ

  1. Chatterbox (natural, GPU)
  2. Carlfm
  3. Davefx
  ```

- Si una ejecución no trae una voz elegida, `ConfigManager` usa
  `piper_davefx`: es la voz por defecto.
- Las dos voces de Piper van algo más lentas que el modelo, a propósito
  (elección del propietario): las dos llevan
  `backend_options.synthesis.length_scale` 1,10 (el modelo trae 1). En la
  práctica la lectura se alarga menos de un 10 %, porque Piper redondea la
  duración de cada sonido: un 4 % con Davefx y un 2 % con Carlfm, cuyo modelo
  (`x_low`) es más basto (apartado 4). El volumen es el del modelo
  (`volume_gain_db` 0.0); `speaking_rate` sigue en 1.0, pero `length_scale`
  manda sobre él (apartado 2).
- Las dos de Piper hacen una pausa de 0,5 s tras cada frase y de 0,35 s entre
  párrafos (apartado 5).
- Chatterbox lee en la GPU con su propio entorno de Python, en un proceso
  aparte (apartado 7). Es más natural, pero más lento que Piper.
- Los modelos (`.onnx` y su `.onnx.json`, y los pesos y el entorno de
  Chatterbox) no están en el repositorio: se descargan al instalar
  ([INSTALL.md](INSTALL.md)).
- Si la voz elegida falla, el programa para con un error que dice qué voz
  falló y por qué; nunca cambia de voz por su cuenta. Se puede elegir otra
  voz en el menú VOZ.

---

## 2. Documento de voz

Cada voz es un JSON en `config/voice_configs/`. Lo lee
`load_tts_voice_configuration` (`app/modules/audio/voice_configuration.py`),
que rechaza las claves que no conoce.

| Clave | Para qué sirve |
|---|---|
| `kind` | Siempre `tts_voice` |
| `voice_id` | Identidad técnica de la voz |
| `display_name` | Nombre en el menú VOZ; es solo presentación |
| `backend_key` | Qué programa sintetiza la voz: `piper_onnx` (Piper) o `chatterbox_multilingual` (Chatterbox, apartado 7) |
| `language` | Idioma de la voz. Con Piper tiene que coincidir con el del modelo (`espeak.voice` de su `.onnx.json`); Chatterbox usa su primera parte (`es`) |
| `prosody.speaking_rate` | Velocidad: 1.0 es la del modelo; con otro valor, Piper divide entre él el `length_scale` del modelo |
| `prosody.volume_gain_db` | Volumen en dB: 0.0 deja el del modelo |
| `prosody.sentence_pause_seconds` | Silencio extra, en segundos, tras cada final de frase. Opcional: sin la clave, 0 (sin pausa extra). Apartado 5 |
| `prosody.paragraph_pause_seconds` | Silencio extra, en segundos, entre párrafos (una o más líneas en blanco). Opcional: sin la clave, 0. Apartado 5 |
| `backend_options.model.onnx_path` | Piper: ruta del modelo `.onnx`, dentro de `models/audio/piper/`; su `.onnx.json` tiene que estar al lado. Las opciones de Chatterbox están en el apartado 7 |
| `backend_options.synthesis` | Piper: ajustes opcionales `length_scale`, `noise_scale`, `noise_w_scale`, `normalize_audio` y `volume`. `length_scale` y `volume` mandan sobre `prosody` |
| `seed` | Semilla, opcional: un número entero de 0 a 4294967295. Con ella, el mismo texto da siempre el mismo audio; sin la clave, cada ejecución da un audio un poco distinto. Apartado 6 |

`prosody` solo admite esas cuatro claves. Un valor que no vale (o una clave
mal escrita) detiene la generación de la voz con un error de configuración
(CONFIG) que nombra el documento y la clave, por ejemplo:

```text
La configuración de la voz no es válida: en «config/voice_configs/piper_davefx.json», prosody.paragraph_pause_seconds debe ser un número de segundos mayor o igual que 0 (0 = sin pausa extra); se recibió -1.
```

El menú VOZ lee todos los documentos para mostrar sus nombres, así que un
valor que no vale en cualquiera de ellos da ese mismo error al abrir el menú.

Añadir una voz de Piper es copiar su modelo y su `.onnx.json` en una carpeta de
`models/audio/piper/` y escribir su documento en `config/voice_configs/`:
aparece en el menú VOZ sin tocar Python.

---

## 3. Cuánto dura un guion

- **Guion generado (IMAGEN y VIDEO).** El prompt pide a Ollama un número de
  palabras según la duración (`duration`, en segundos) del perfil operacional
  (`PromptEngine`, `app/core/prompt_engine.py`):

  ```text
  palabras objetivo = parte entera de (duration × 2,6)
  mínimo            = parte entera de (objetivo × 0,9)   (al menos 1)
  máximo            = parte entera de (objetivo × 1,1)
  ```

  | `duration` | Objetivo | Rango aceptado |
  |---|---|---|
  | 10 s | 26 palabras | 23–28 |
  | 30 s | 78 palabras | 70–85 |
  | 60 s | 156 palabras | 140–171 |

  Las palabras se cuentan con `count_script_words`
  (`app/modules/script/validator.py`): cada secuencia de letras o cifras es una
  palabra. Qué pasa si la respuesta se sale del rango:
  [ARCHITECTURE.md, apartado 12](ARCHITECTURE.md#12-guion).
- **Guion escrito a mano (GUION, `input/guion.txt`).** No hay rango: la voz lee
  el texto tal cual y la duración del vídeo la marca la voz.

---

## 4. Ritmo real de Piper

El cálculo del apartado 3 supone 2,6 palabras por segundo. Medido con las dos
voces, Piper lee más deprisa:

| Voz | Texto | Palabras | Duración | Palabras/s |
|---|---|---|---|---|
| Davefx | corto | 61 | 20,5 s | 2,98 |
| Davefx | medio | 139 | 44,2 s | 3,14 |
| Davefx | largo | 228 | 71,0 s | 3,21 |
| **Davefx** | **total** | **428** | **135,7 s** | **3,15** |
| Carlfm | corto | 61 | 20,7 s | 2,95 |
| Carlfm | medio | 139 | 44,4 s | 3,13 |
| Carlfm | largo | 228 | 69,7 s | 3,27 |
| **Carlfm** | **total** | **428** | **134,8 s** | **3,18** |

Con la voz por defecto (Davefx) son unas 3,15 palabras por segundo (unas 190
por minuto), un 21 % más que las 2,6 del cálculo. Por eso un guion generado
dura menos que su `duration`: con 30 s se piden 70–85 palabras, que Davefx lee
en unos 22–27 s.

**Cómo se midió** (31-10-2026): desde la raíz del repositorio, con el
`VoiceBuilder` del programa y cada voz
(`VoiceBuilder(config_manager=ConfigManager(voice_config_id="piper_davefx"))`
y lo mismo con `piper_carlfm`), se generó el MP3 de tres textos en español
de 61, 139 y 228 palabras (contadas con `count_script_words`): una reflexión
corta, una biografía y una práctica de atención. La duración de cada MP3 se
leyó con `ffprobe`; `silencedetect` de FFmpeg (−45 dB) no encontró silencio al
principio ni al final, así que la duración es toda voz. Para repetirla con
otras voces o modelos basta con el mismo procedimiento.

La medida es de antes de las pausas del apartado 5 (31-10-2026, voces sin
pausas): es el ritmo de la lectura. Con las pausas, cada audio dura además lo
que sumen sus pausas.

También es de antes de `length_scale` 1,10 (apartado 1), con la velocidad del
modelo. Con 1,10, medido el 01-11-2026 de la misma forma pero con las pausas a
0 y un texto narrativo de 300 palabras:

| Voz | `length_scale` del modelo (1) | 1,10 | Más lenta |
|---|---|---|---|
| Davefx | 96,0 s (3,12 palabras/s) | 100,1 s (3,00 palabras/s) | 4,2 % |
| Carlfm | 92,9 s (3,23 palabras/s) | 94,5 s (3,18 palabras/s) | 1,7 % |

Así, con Davefx las 70–85 palabras de un guion de 30 s se leen en unos
23–28 s, más sus pausas.

---

## 5. Pausas

La voz hace dos pausas, que declara cada documento de voz en `prosody`:

| Clave | Dónde | Valor en las dos voces |
|---|---|---|
| `sentence_pause_seconds` | Tras cada final de frase (`.`, `?`, `!`, `…`) | 0,5 s |
| `paragraph_pause_seconds` | Entre párrafos: una o más líneas en blanco | 0,35 s |

- **0 = sin pausa extra.** Las dos claves son opcionales; sin ellas, 0.
- El valor es silencio **añadido** al que el modelo ya deja al final de cada
  frase (hasta unos 0,25 s con Davefx).
- Un cambio de párrafo lleva solo la pausa de párrafo (no se suman las dos).
  Por eso, con estos valores, el silencio entre párrafos es algo más corto
  que el de tras frase (elección del propietario).
- **Silencio medido** (02-11-2026, las dos voces, cuatro textos, `silencedetect`
  de FFmpeg a −45 dB): tras frase, 0,55–0,86 s; entre párrafos, 0,37–0,66 s
  (unos 0,55 s de media; con la pausa de párrafo de 1,5 s anterior eran
  1,52–1,81 s).
  No se añade silencio al principio ni al final del audio.
- **Un salto de línea simple no hace nada especial:** las dos líneas se leen
  seguidas, como una sola frase si no hay punto entre ellas. Un texto sin
  líneas en blanco solo lleva las pausas de frase.
- Es la misma regla para el guion escrito a mano (`input/guion.txt`) y para el
  generado. Las pausas solo cambian el audio: el guion guardado
  (`scripts/guion.txt`) y el texto de los subtítulos son los mismos.

**Cómo se hacen (Piper).** `PiperBackend`
(`app/modules/audio/piper_backend.py`):

1. Parte el texto en párrafos por las líneas en blanco (vale con finales de
   línea de Windows).
2. Parte cada párrafo tras unos puntos suspensivos (`…` o `...`) seguidos de
   espacio: el lector fonético de Piper (espeak-ng) no los toma como final de
   frase y, sin este corte, pega las palabras de alrededor.
3. Lee cada trozo con Piper, que ya devuelve el audio frase a frase (corta en
   `.`, `?` y `!`), y escribe entre frases la pausa de frase y entre párrafos la
   de párrafo.

Leer cada párrafo por separado tiene además otro efecto: Piper ya no pierde el
punto de la última frase de cada párrafo (le pasaba con una línea en blanco
detrás) y esa frase se lee con entonación de final.

Lo que decide dónde acaba una frase es Piper: tras una abreviatura con punto
(«Sr. García») también hace pausa. Si molesta, se escribe la palabra entera.

Los subtítulos siguen la voz: Whisper da los tiempos de cada palabra y en las
pausas no hay texto ([SUBTITLES.md](SUBTITLES.md)).

---

## 6. Repetir el mismo audio (semilla)

Piper añade un poco de azar al leer: con el mismo texto, cada ejecución del programa da un audio algo distinto (unas décimas de segundo
de diferencia en 30 s) y Whisper puede transcribir distinto alguna palabra.
Dentro de una misma ejecución sí repite.

Para rehacer un vídeo idéntico, o para comparar dos versiones del programa, el
documento de la voz puede declarar una semilla:

```json
{
  "kind": "tts_voice",
  "voice_id": "piper_voice_davefx",
  "...": "...",
  "seed": 1234
}
```

- **Con `seed`**, el mismo texto da el mismo audio byte a byte en cualquier
  ejecución. Otra semilla da otra lectura igual de válida.
- **Sin `seed`** (como vienen las dos voces), todo funciona como siempre.
- El valor tiene que ser un número entero de 0 a 4294967295; con otra cosa
  (texto, decimales, `true`, `null`, negativos…) la voz no se genera y el error
  CONFIG nombra el documento (apartado 2):

  ```text
  La configuración de la voz no es válida: en «config/voice_configs/piper_davefx.json», seed debe ser un número entero entre 0 y 4294967295 (sin «seed», la voz no repite el mismo audio); se recibió '1234'.
  ```

**Cómo se hace (Piper).** El azar de Piper lo pone ONNX Runtime al crear la
sesión del modelo. `PiperBackend` fija la semilla de ONNX Runtime
(`onnxruntime.set_seed`) justo antes de cargar el modelo, en cada voz que se
genera. Esa semilla vale para todo el proceso: si en la misma ejecución se
genera después otra voz sin `seed`, también parte de ella.

**Cómo se hace (Chatterbox).** El proceso de la voz fija con ella las semillas
de Python, NumPy y torch (también en la GPU) antes de cargar el modelo. Como
cada voz se genera en su propio proceso, no afecta a nada más.

---

## 7. Chatterbox Multilingual

Chatterbox Multilingual (Resemble AI) lee con una entonación más viva que
Piper. Se usa su voz de serie (no se clona ninguna). Necesita su propio Python
con torch para CUDA, así que no corre dentro del programa: `ChatterboxBackend`
(`app/modules/audio/chatterbox_backend.py`) lo lanza como un **proceso aparte**
con el Python de su entorno:

1. Parte el texto en trozos de frases enteras (apartado «Trozos y pausas»).
2. Escribe la petición en la carpeta de trabajo privada de la voz y lanza
   `app/modules/audio/workers/chatterbox_worker.py` con el Python declarado.
3. El proceso carga el modelo, lee cada trozo, escribe un WAV por trozo y su
   resultado, y **termina**: la GPU queda libre para Whisper, Ollama y ComfyUI.
   No tiene tiempo límite (como Ollama y Wan).
4. El programa une los WAV con las pausas declaradas y publica `voz.mp3` como
   con Piper.

La terminal muestra la carga y cada trozo:

```text
GENERANDO VOCES...
Cargando Chatterbox (cuda) en su propio proceso…
  Parte 1 de 2
  Parte 2 de 2
Finalizado (1 min 33.26 s)
```

El proceso no descarga nada (Hugging Face sin conexión) y guarda sus cachés en
la carpeta declarada, dentro del proyecto. La capacidad de lanzar una voz en su
propio proceso (`app/modules/audio/external_tts_process.py`) es común: otra voz
que necesite su propio entorno solo añade su script y sus opciones.

### Opciones (`backend_options`)

| Clave | Para qué sirve | Valor |
|---|---|---|
| `runtime.python_path` | Python del entorno de la voz | `models/tts/chatterbox/env/Scripts/python.exe` |
| `runtime.cache_dir` | Carpeta de las cachés del proceso (Hugging Face, torch) | `models/tts/_cache` |
| `runtime.device` | `cuda` (GPU) o `cpu` | `cuda` |
| `model.checkpoint_dir` | Carpeta con los pesos (`ve.pt`, `t3_mtl23ls_v2.safetensors`, `s3gen.pt`, `grapheme_mtl_merged_expanded_v1.json`, `conds.pt`) | `models/tts/chatterbox/weights` |
| `segmentation.max_characters` | Máximo de caracteres de un trozo | 300 |
| `synthesis` | Ajustes de Chatterbox, opcionales (números ≥ 0): `exaggeration` (expresividad), `cfg_weight` (cuánto sigue a su voz de referencia; con 0, en I6, se inventó palabras), `temperature`, `repetition_penalty`, `min_p` y `top_p` | `exaggeration` 0,5 y `cfg_weight` 0,5 (los de serie) |

- Las rutas son relativas a la carpeta del proyecto y no pueden salir de ella.
- El idioma sale de `language` (`es-ES` → `es`).
- Chatterbox no tiene ajuste de velocidad ni de volumen: `prosody.speaking_rate`
  tiene que ser 1.0 y `prosody.volume_gain_db` 0.0.
- Si falta algo, la voz no se genera y el error CONFIG dice qué ruta falta, por
  ejemplo:

  ```text
  La configuración de la voz no es válida: no existe «models/tts/chatterbox/env/Scripts/python.exe» (backend_options.runtime.python_path). Monta el entorno de la voz (docs/INSTALL.md, apartado 10) o corrige la ruta en el documento de la voz.
  ```

- Si el proceso falla (por ejemplo, sin memoria en la GPU), el error dice qué
  pasó; el programa para y no cambia de voz.

### Trozos y pausas

Cada llamada a Chatterbox lee como mucho unos 40 s de audio. Por eso el texto se
parte en trozos de frases enteras (cortes en `.`, `?`, `!` y `…`) de hasta
`segmentation.max_characters` caracteres (300 ≈ 15–20 s), sin juntar nunca dos
párrafos. Leer varias frases seguidas suena como la muestra que se eligió de
oído en I6; leyendo frase a frase, Chatterbox va más despacio, mete pausas
dentro de las frases y tarda casi el doble.

| Clave | Dónde | Valor |
|---|---|---|
| `sentence_pause_seconds` | Entre dos trozos de un mismo párrafo (dentro de un trozo, Chatterbox hace su propia pausa) | 0,2 s |
| `paragraph_pause_seconds` | Entre párrafos | 0,35 s |

### Ritmo, tiempo y memoria

Ritmo declarado en su `pacing` (sirve para calcular cuánto texto pedir a
Ollama en un guion por tema): **15,71 letras/s y 3,17 palabras/s**, medido el
23-11-2026 con el `VoiceBuilder` del programa, sin semilla, con 8 guiones reales
de Ollama (los de I2: 4 de 30 s y 4 de 60 s), la configuración de arriba y la
duración del `voz.mp3` publicado (pausas incluidas):

| Guion | Palabras | Letras | Duración | Tiempo de la voz |
|---|---:|---:|---:|---:|
| Tesla, 30 s | 85 | 405 | 23,64 s | 73 s |
| Neuroplasticidad, 30 s | 82 | 449 | 29,72 s | 80 s |
| Estoicismo, 30 s | 95 | 445 | 29,76 s | 75 s |
| Neuroplasticidad, 30 s (otro) | 67 | 381 | 23,72 s | 83 s |
| Tesla, 60 s | 164 | 825 | 52,40 s | 139 s |
| Neuroplasticidad, 60 s | 139 | 714 | 46,28 s | 136 s |
| Estoicismo, 60 s | 176 | 819 | 52,48 s | 122 s |
| Tesla, 60 s (otro) | 172 | 826 | 51,52 s | 148 s |

- Estimando cada guion con los otros siete, las letras aciertan con un error
  medio del 3,4 % (ninguno fuera de ±10 %) y las palabras, del 7,8 % (3 de 8
  fuera): como con Piper, la unidad buena son las letras.
- Lee más deprisa que Piper (Davefx: 13,14 letras/s): un guion de las mismas
  palabras dura un 16 % menos.
- **Tiempo:** de 73 a 83 s para un guion de 30 s y de 122 a 148 s para uno de
  60 s (unos 25 s son de cargar el modelo). Piper tarda unos 3 s.
- **Memoria de la GPU:** unos 4–5 GB mientras dura el proceso; al terminar
  queda libre.

### Repetir el mismo audio

Con `seed`, el mismo texto da el mismo audio byte a byte (apartado 6). Sin
ella, cada ejecución da una lectura distinta y su duración varía más que con
Piper (con el mismo guion de 30 s, de 23,6 a 25,3 s).

---

## 8. Licencias de las voces

| Voz | Programa | Modelo | Notas |
|---|---|---|---|
| Carlfm y Davefx | `piper-tts` 1.8.0: GPL-3.0 o posterior | Davefx: CC0; Carlfm: dominio público (fichas de `rhasspy/piper-voices`) | — |
| Chatterbox | `chatterbox-tts` 0.1.7: MIT | `ResembleAI/chatterbox` (checkpoint multilingüe v2): MIT | Permite uso comercial. **Proyecto retirado:** desde agosto de 2026 es un archivo de investigación sin mantenimiento ni arreglos. **Marca de agua:** cada audio lleva una marca de agua inaudible (Perth, de Resemble AI) que identifica la voz como generada por IA |

Los modelos y los entornos no se reparten con el proyecto: cada persona los
descarga al instalar ([INSTALL.md](INSTALL.md)).
