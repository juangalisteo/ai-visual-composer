# Voz de AI Visual Composer

Este documento es la referencia de la voz: qué voces hay, cómo se declara cada
una, cuántas palabras se piden al guion generado y a qué ritmo lee de verdad
Piper.

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
- Las dos voces son de Piper y no cambian la velocidad ni el volumen del
  modelo (`speaking_rate` 1.0 y `volume_gain_db` 0.0).
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
| `backend_options.model.onnx_path` | Ruta del modelo `.onnx`, dentro de `models/audio/piper/`; su `.onnx.json` tiene que estar al lado |
| `backend_options.synthesis` | Ajustes de Piper, opcionales: `length_scale`, `noise_scale`, `noise_w_scale`, `normalize_audio` y `volume`. `length_scale` y `volume` mandan sobre `prosody` |

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
