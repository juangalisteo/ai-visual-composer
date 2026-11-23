# Voz de AI Visual Composer

Este documento es la referencia de la voz: qué voces hay, cómo se declara cada
una, cuántas palabras se piden al guion generado, a qué ritmo lee de verdad
Piper, cómo hace las pausas y cómo repetir el mismo audio (semilla).

Otros documentos:

| Para saber… | Documento |
|---|---|
| Cómo se genera y se mezcla el audio (Piper, música, `audio_final.mp3`) | [ARCHITECTURE.md, apartado 13](ARCHITECTURE.md#13-voz-y-música) |
| Cómo se escribe el guion y cómo se valida | [ARCHITECTURE.md, apartado 12](ARCHITECTURE.md#12-guion) |
| Cómo se instalan Piper y sus modelos | [INSTALL.md](INSTALL.md) |
| Subtítulos | [SUBTITLES.md](SUBTITLES.md) |

---

## 1. Voces

| Documento | En el menú VOZ | Modelo ONNX | Idioma |
|---|---|---|---|
| `config/voice_configs/piper_carlfm.json` | Carlfm | `models/audio/piper/es_ES_carlfm/es_ES-carlfm-x_low.onnx` | `es-ES` |
| `config/voice_configs/piper_davefx.json` | Davefx | `models/audio/piper/es_ES_davefx/es_ES-davefx-medium.onnx` | `es-ES` |

- El menú VOZ lista los documentos de `config/voice_configs/` por orden de
  nombre de archivo y muestra su `display_name`:

  ```text
  VOZ

  1. Carlfm
  2. Davefx
  ```

- Si una ejecución no trae una voz elegida, `ConfigManager` usa
  `piper_davefx`: es la voz por defecto.
- Las dos voces son de Piper y van algo más lentas que el modelo, a propósito
  (elección del propietario): las dos llevan
  `backend_options.synthesis.length_scale` 1,10 (el modelo trae 1). En la
  práctica la lectura se alarga menos de un 10 %, porque Piper redondea la
  duración de cada sonido: un 4 % con Davefx y un 2 % con Carlfm, cuyo modelo
  (`x_low`) es más basto (apartado 4). El volumen es el del modelo
  (`volume_gain_db` 0.0); `speaking_rate` sigue en 1.0, pero `length_scale`
  manda sobre él (apartado 2).
- Las dos hacen una pausa de 0,5 s tras cada frase y de 0,35 s entre párrafos
  (apartado 5).
- Los modelos (`.onnx` y su `.onnx.json`) no están en el repositorio: se
  descargan al instalar ([INSTALL.md](INSTALL.md)).

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
| `backend_key` | Qué programa sintetiza la voz. Hoy solo existe `piper_onnx` (Piper) |
| `language` | Idioma de la voz. Tiene que coincidir con el del modelo (`espeak.voice` de su `.onnx.json`) |
| `prosody.speaking_rate` | Velocidad: 1.0 es la del modelo; con otro valor, Piper divide entre él el `length_scale` del modelo |
| `prosody.volume_gain_db` | Volumen en dB: 0.0 deja el del modelo |
| `prosody.sentence_pause_seconds` | Silencio extra, en segundos, tras cada final de frase. Opcional: sin la clave, 0 (sin pausa extra). Apartado 5 |
| `prosody.paragraph_pause_seconds` | Silencio extra, en segundos, entre párrafos (una o más líneas en blanco). Opcional: sin la clave, 0. Apartado 5 |
| `backend_options.model.onnx_path` | Ruta del modelo `.onnx`, dentro de `models/audio/piper/`; su `.onnx.json` tiene que estar al lado |
| `backend_options.synthesis` | Ajustes de Piper, opcionales: `length_scale`, `noise_scale`, `noise_w_scale`, `normalize_audio` y `volume`. `length_scale` y `volume` mandan sobre `prosody` |
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
