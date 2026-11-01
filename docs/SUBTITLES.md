# Subtítulos de AI Visual Composer

Este documento es la referencia de los perfiles de subtítulos: qué familias y
perfiles hay, cómo corta cada uno el texto en líneas (`cue_policy`), cómo se ve
(`render_style`) y qué efectos puede llevar.

Otros documentos:

| Para saber… | Documento |
|---|---|
| Qué modos piden subtítulos y cómo viaja una ejecución | [ARCHITECTURE.md](ARCHITECTURE.md), apartados [6](ARCHITECTURE.md#6-modos-de-ejecución) y [8](ARCHITECTURE.md#8-studio) |
| Cómo se transcribe con Whisper y qué frases inventadas se quitan | [ARCHITECTURE.md, apartado 14](ARCHITECTURE.md#14-subtítulos) |
| Cómo se usa el programa | [START.md](START.md) |
| Cómo se genera la voz | [VOICEOVER.md](VOICEOVER.md) |

---

## 1. Perfil de subtítulos

Un perfil de subtítulos es un JSON con su identidad, un bloque `cue_policy`
(cómo se corta el texto en líneas) y un bloque `render_style` (cómo se ve):

```text
config/profiles/<componente>/<formato>/<familia>/subtitulos/<archivo>.json
```

| Clave | Para qué sirve |
|---|---|
| `component`, `format`, `family`, `profile_id` | Identidad (`SubtitleProfileKey`): tienen que coincidir con la carpeta |
| `display_name` | Nombre del perfil en el menú PERFIL; es solo presentación |
| `cue_policy` | Corte del texto en líneas ([apartado 4](#4-cue_policy-cómo-se-corta-el-texto)) |
| `render_style` | Aspecto y efectos ([apartados 5 a 7](#5-render_style-cómo-se-ve)) |

- **Descubrimiento.** `SubtitleProfileResolver`
  (`app/shared/subtitle_profile_resolver.py`) lee las carpetas: cada subcarpeta
  del formato con al menos un perfil es una familia, y cada JSON de su carpeta
  `subtitulos/` es un perfil. Valida cada perfil al descubrirlo (identidad,
  `display_name`, un modo de cue conocido, `text_case` y `render_style`); si uno
  no cumple, o si dos repiten `profile_id`, la ejecución se para con un error.
- **Menú.** Los modos que llevan subtítulos piden:

  ```text
  SUBTÍTULOS

  FAMILIA

  1. MODO CONCIENCIA
  2. ESTILO ESTÁNDAR
  …

  PERFIL

  1. …
  ```

  Las familias salen en este orden: MODO CONCIENCIA, ESTILO ESTÁNDAR, MODO
  MINIMALISTA, ESTILO KARAOKE y PRIMADO NEGATIVO (`app/controllers/interaction/labels.py`);
  una familia nueva sale después, con el nombre de su carpeta en mayúsculas.
  Los perfiles salen por orden alfabético de `display_name`. En VIDEO + AUDIO |
  SRT, el menú SUBTÍTULOS pregunta antes «1. Sí / 2. No». Qué modos piden
  subtítulos: [ARCHITECTURE.md](ARCHITECTURE.md#6-modos-de-ejecución) (ruta
  estándar) y [ARCHITECTURE.md](ARCHITECTURE.md#8-studio) (STUDIO).
- **Añadir un perfil o una familia** es añadir archivos con modos y efectos que
  ya existen: aparecen en el menú sin tocar Python. Un modo de cue o un efecto
  nuevos son una capacidad nueva
  ([ARCHITECTURE.md, apartado 14](ARCHITECTURE.md#14-subtítulos)).

---

## 2. Familias

| Familia (carpeta) | En el menú | Formatos |
|---|---|---|
| `design` | MODO CONCIENCIA | vertical y horizontal |
| `estandar` | ESTILO ESTÁNDAR | vertical y horizontal |
| `minimalista` | MODO MINIMALISTA | vertical |
| `karaoke` | ESTILO KARAOKE | vertical |
| `primado_negativo` | PRIMADO NEGATIVO | vertical, solo STUDIO |

La familia `design` (MODO CONCIENCIA) es solo una familia de subtítulos: no
tiene nada que ver con la ruta DISEÑO
([ARCHITECTURE.md, apartado 2](ARCHITECTURE.md#2-componentes-y-rutas)).

---

## 3. Perfiles por componente y formato

Cada componente tiene sus propios perfiles. Un perfil con el mismo nombre en
dos componentes tiene el mismo modo de cue y el mismo efecto (salvo «Línea
única» de STUDIO vertical), pero puede tener otros valores (tamaño de letra,
letras por línea…): manda el JSON de cada uno.

**vertical**

| Familia | Perfil | Modo de cue | Efecto | Pintado | Componentes |
|---|---|---|---|---|---|
| MODO CONCIENCIA | Modo Conciencia \| Palabra única | `word_by_word` | — | estático | GUION, IMAGEN, VIDEO, STUDIO |
| MODO CONCIENCIA | Modo Conciencia \| Podcast | `three_two_words` | — | estático | STUDIO |
| ESTILO ESTÁNDAR | Doble línea | `two_lines` | — | estático | GUION, IMAGEN, VIDEO, STUDIO |
| ESTILO ESTÁNDAR | Dos palabras | `three_two_words` | — | estático | GUION, IMAGEN, VIDEO, STUDIO |
| ESTILO ESTÁNDAR | Línea única | `single_line` | — | estático | GUION, IMAGEN, VIDEO |
| ESTILO ESTÁNDAR | Línea única | `three_two_words` | — | estático | STUDIO |
| ESTILO ESTÁNDAR | Palabra única | `word_by_word` | — | estático | GUION, IMAGEN, VIDEO, STUDIO |
| ESTILO ESTÁNDAR | Tres palabras | `three_two_words` | — | estático | GUION, IMAGEN, VIDEO, STUDIO |
| MODO MINIMALISTA | Caída de palabras | `word_by_word` | `gravity_drop` | dinámico | GUION, IMAGEN, VIDEO, STUDIO |
| MODO MINIMALISTA | Máquina de escribir | `single_line` | `typewriter` | dinámico | GUION, IMAGEN, VIDEO, STUDIO |
| MODO MINIMALISTA | Palabra aumentada | `single_line` | `pop_in_sentence` | dinámico | GUION, IMAGEN, VIDEO, STUDIO |
| MODO MINIMALISTA | Palabra en color | `single_line` | `highlight_in_sentence` | dinámico | GUION, IMAGEN, VIDEO, STUDIO |
| MODO MINIMALISTA | Palabra en recuadro | `single_line` | `active_pill` | dinámico | GUION, IMAGEN, VIDEO, STUDIO |
| MODO MINIMALISTA | Palabra por palabra | `cumulative_line` | — | estático | GUION, IMAGEN, VIDEO, STUDIO |
| MODO MINIMALISTA | Respiración Chunking | `acoustic_burst` | — | estático | GUION, IMAGEN, VIDEO, STUDIO |
| MODO MINIMALISTA | Revelado progresivo | `single_line` | `alpha_fade` | dinámico | GUION, IMAGEN, VIDEO, STUDIO |
| ESTILO KARAOKE | Desplazamiento vertical | `roll_up` | — | dinámico | GUION, IMAGEN, VIDEO, STUDIO |
| ESTILO KARAOKE | Karaoke continuo | `single_line` | `continuous_karaoke` | dinámico | GUION, IMAGEN, VIDEO, STUDIO |
| ESTILO KARAOKE | Ventana deslizante | `rolling_window` | — | estático | GUION, IMAGEN, VIDEO, STUDIO |
| PRIMADO NEGATIVO | Primado Negativo \| Marco | `three_two_words` | — | estático | STUDIO |
| PRIMADO NEGATIVO | Primado Negativo \| Tres palabras | `three_two_words` | — | estático | STUDIO |

**horizontal**

| Familia | Perfil | Modo de cue | Efecto | Pintado | Componentes |
|---|---|---|---|---|---|
| MODO CONCIENCIA | Modo Conciencia \| Línea única | `single_line` | — | estático | GUION, IMAGEN, VIDEO, STUDIO |
| ESTILO ESTÁNDAR | Línea única | `single_line` | — | estático | GUION, IMAGEN, VIDEO, STUDIO |
| ESTILO ESTÁNDAR | Palabra por palabra | `word_by_word` | — | estático | GUION, IMAGEN, VIDEO, STUDIO |

En total hay 83 perfiles: 71 verticales y 12 horizontales.

**Perfiles iguales a propósito.** En STUDIO vertical, «Línea única» y «Tres
palabras» (ESTILO ESTÁNDAR) tienen hoy la misma configuración, y también
«Primado Negativo | Marco» y «Primado Negativo | Tres palabras». Es
intencionado: son estilos distintos que se ajustarán por separado; no son
duplicados.

**Cómo regenerar la tabla** cuando cambien los perfiles: guardar este código en
un archivo fuera del repositorio y ejecutarlo desde la raíz con
`python -B <archivo>`. Lee los JSON de `config/profiles/` y las etiquetas y el
orden del menú de `labels.py`, e imprime las dos tablas en Markdown:

```python
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.stdout.reconfigure(encoding="utf-8")
from app.controllers.interaction.labels import family_label, presentation_families

COMPONENTS = ("guion", "imagen", "video", "studio")
rows = defaultdict(list)
for path in Path("config/profiles").glob("*/*/*/subtitulos/*.json"):
    profile = json.loads(path.read_text(encoding="utf-8"))
    style = profile["render_style"]
    effects = [style.get(key) for key in ("cue_effect", "word_effect")]
    effect = ", ".join(f"`{name}`" for name in effects if name not in (None, "none"))
    row = (profile["family"], profile["display_name"], profile["cue_policy"]["mode"],
           effect or "—", "dinámico" if style.get("dynamic") else "estático")
    rows[profile["format"], row].append(profile["component"])

for profile_format in sorted({key[0] for key in rows}, reverse=True):
    print(f"\n**{profile_format}**\n")
    print("| Familia | Perfil | Modo de cue | Efecto | Pintado | Componentes |")
    print("|---|---|---|---|---|---|")
    order = presentation_families(sorted({row[0] for fmt, row in rows if fmt == profile_format}))
    keys = sorted((row for fmt, row in rows if fmt == profile_format),
                  key=lambda row: (order.index(row[0]), row[1].casefold(), row[2]))
    for family, name, mode, effect, painting in keys:
        components = sorted(rows[profile_format, (family, name, mode, effect, painting)],
                            key=COMPONENTS.index)
        print(f"| {family_label(family)} | {name.replace('|', chr(92) + '|')} | `{mode}` "
              f"| {effect} | {painting} | {', '.join(c.upper() for c in components)} |")
```

El total sale de contar los archivos:
`git ls-files "config/profiles/*/subtitulos/*.json"`.

---

## 4. `cue_policy`: cómo se corta el texto

`SubtitleCueTransformer` (`app/modules/subtitles/pipeline/cue_transformer.py`)
crea el modelo de corte que pide `cue_policy.mode` a través de
`CueModelRegistry` y aplica después `text_case` a cada línea.

**Claves comunes:**

| Clave | Valores | Para qué sirve |
|---|---|---|
| `mode` | uno de los 8 modos de abajo | Cómo se agrupan las palabras en líneas |
| `text_case` | `original`, `uppercase`, `lowercase` | Mayúsculas o minúsculas del texto pintado |
| `punctuation` | 12 booleanos | Qué signos se quitan del texto pintado: `remove_commas`, `remove_periods`, `remove_colons`, `remove_semicolons`, `remove_question_marks`, `remove_exclamation_marks`, `remove_ellipsis`, `remove_hyphens`, `remove_em_dashes`, `remove_double_quotes`, `remove_single_quotes`, `remove_parentheses` |
| `significant_gap_threshold` | segundos (> 0) | Una pausa de al menos este tiempo entre dos palabras abre un grupo nuevo |
| `max_chars_per_line` | entero (> 0) | Letras que caben en una línea |
| `min_duration`, `max_duration` | segundos | Límites de duración de cada línea cuando el tiempo de una línea del SRT se reparte sin tiempos por palabra |

**Los 8 modos** (`app/modules/subtitles/modes/`):

| Modo | Qué muestra | Claves propias, además de las comunes |
|---|---|---|
| `single_line` | Una línea cada vez, cortada por sentido: corta en las pausas, prefiere cortar en la puntuación y evita acabar una línea en una preposición, un artículo o una conjunción, o dejar una palabra sola al final | `max_chars_per_line`, `min_duration`, `max_duration`; `syllabify` (solo con `continuous_karaoke`) |
| `cumulative_line` | Una línea que crece palabra a palabra dentro de cada frase; solo se ve una línea a la vez | Las de `single_line` |
| `three_two_words` | Grupos de 3 y 2 palabras alternos o, con `fixed_chunk_size`, grupos de ese número de palabras. La puntuación cierra el grupo y una palabra acabada en «-mente» va sola | `max_chars_per_line`, `min_duration`, `max_duration`, `fixed_chunk_size` (opcional) |
| `two_lines` | Hasta dos líneas equilibradas en largo | Las de `three_two_words` sin `fixed_chunk_size`; `max_lines` (tiene que ser 2) y `balance_ratio_threshold` (0,5–1,0; si falta, 0,75) |
| `word_by_word` | Una palabra cada vez | `min_duration`, `max_duration`, `micro_cues` |
| `rolling_window` | Una ventana de hasta `window_size` palabras que avanza una palabra cada vez; empieza por la palabra que suena y, si no cabe en `max_chars_per_line`, pierde palabras por el final | `window_size` (≥ 2), `max_chars_per_line` |
| `roll_up` | Líneas sucesivas de ancho fijo; con pintado dinámico, las últimas `visible_lines` suben como en un rótulo ([apartado 6](#6-pintado-estático-y-dinámico)) | `max_chars_per_line`, `visible_lines` (2, 3 o 4) |
| `acoustic_burst` | Un bloque por cada tramo de voz entre pausas, con un tope de letras | `hard_max_chars` |

`micro_cues` (solo `word_by_word`): `enabled`, `min_frames`,
`min_display_seconds` y `merge_preference` (`next` o `previous`). Con
`enabled: true`, una palabra que se vería menos de `min_frames` fotogramas o de
`min_display_seconds` segundos se alarga o se une a su vecina, sin quitar
palabras. Los fotogramas por segundo salen del perfil operacional
(`video_style.fps`, o `studio.output.fps` en STUDIO).

**Con y sin tiempos por palabra.** Si hay tiempos de Whisper utilizables, el
modo agrupa las palabras con ellos. En GUION, IMAGEN y VIDEO esos tiempos
llegan ya fuera de las pausas que escribió la voz, así que en ellas no queda
texto en pantalla
([ARCHITECTURE.md, apartado 14](ARCHITECTURE.md#14-subtítulos)). Si no los hay (EXPORTAR SRT ➜  VIDEO →
CONVERTIR, o la ruta estándar cuando Whisper no da tiempos por palabra), cada
línea del SRT se corta en trozos y su tiempo se reparte entre ellos. Una
palabra de duración 0 se alarga hasta que empieza la línea siguiente, como
mucho `significant_gap_threshold` segundos; las líneas nunca se solapan.

---

## 5. `render_style`: cómo se ve

`SubtitleConfigLoader` (`app/modules/video/config/loaders/subtitle_loader.py`)
valida el bloque al descubrir el perfil.

**Obligatorias:**

| Clave | Valores | Para qué sirve |
|---|---|---|
| `font` | texto | Fuente. `FontManager` traduce `anton`, `gotham`, `oswald` y `unisans` a las fuentes de `assets/fonts/`; otro nombre se pasa tal cual |
| `font_size` | entero (> 0) | Tamaño de letra |
| `bold` | booleano | Negrita |
| `primary_colour`, `outline_colour`, `back_colour` | color ASS `&HAABBGGRR` | Texto, contorno y sombra o caja |
| `border_style` | `1` o `3` | 1: contorno y sombra; 3: caja detrás del texto |
| `outline`, `shadow` | entero (≥ 0) | Grosor del contorno y de la sombra |
| `alignment` | 1–9 | Posición, como el teclado numérico (2: abajo en el centro) |
| `margin_v` | entero (≥ 0) | Distancia al borde de arriba o de abajo |
| `offset` | segundos | En la ruta estándar desplaza todos los tiempos del SRT antes de pintarlo. STUDIO exige `0` para no tocar los tiempos del SRT |

**Opcionales** (si faltan, no cambian el aspecto):

| Clave | Valores | Para qué sirve |
|---|---|---|
| `italic`, `underline`, `strikeout` | booleano | Cursiva, subrayado y tachado |
| `secondary_colour` | color ASS | Color de las palabras que no están activas en los efectos por palabra |
| `margin_l`, `margin_r` | entero (≥ 0) | Márgenes izquierdo y derecho |
| `scale_x`, `scale_y` | número, en % (100 = normal) | Ancho y alto de la letra |
| `spacing` | número | Espacio entre letras |
| `dynamic` | booleano | Pintado dinámico ([apartado 6](#6-pintado-estático-y-dinámico)) |
| `cue_effect`, `word_effect` | nombre del efecto o `none` | Efecto de la línea o de la palabra ([apartado 7](#7-efectos-cue_effect-y-word_effect)) |
| `scroll_duration_ms` | entero (> 0) | Con `roll_up` y pintado dinámico: lo que tarda en subir una línea |

Los tamaños y márgenes se escriben en la rejilla de 384 × 288 que libass usa
para un SRT. Con pintado dinámico se escalan a la resolución real del vídeo
(`AssVisualScaleNormalizer`), así que el mismo valor se ve igual con los dos
pintados.

---

## 6. Pintado estático y dinámico

| | Estático | Dinámico |
|---|---|---|
| Cuándo | `dynamic` falta o es `false` | `dynamic: true` |
| Qué se pinta | El SRT, con el filtro `subtitles` de FFmpeg y un estilo fijo (`force_style`, `SubtitleStyleBuilder`) | Un ASS temporal hecho a partir del SRT final (`AssSubtitleBuilder`), con el filtro `ass` |
| Efectos | No | `cue_effect`, `word_effect` y la subida de `roll_up` |

En los dos casos las fuentes salen de `assets/fonts/`. El ASS dinámico usa como
`PlayResX`/`PlayResY` la resolución del vídeo; no sustituye al SRT, que queda
igual, y se borra al terminar el render, también si falla. Las etiquetas ASS
las escribe solo el programa: en el texto se escapan las barras, las llaves y
los saltos de línea para que nunca se lean como órdenes.

Con `roll_up`, `dynamic: true` y `scroll_duration_ms`, se ven a la vez las
últimas `visible_lines` líneas y cada línea nueva entra por abajo empujando a
las anteriores; tras una pausa de al menos `significant_gap_threshold`, el
bloque empieza vacío.

---

## 7. Efectos: `cue_effect` y `word_effect`

- Un perfil lleva como mucho un efecto: `cue_effect` (de la línea entera) o
  `word_effect` (de cada palabra dentro de la línea), no los dos. `none` o la
  clave ausente es sin efecto.
- Cualquier efecto exige `dynamic: true`; si no, el perfil no pasa la
  validación.
- Las claves de ajuste de cada efecto van también en `render_style`; entre
  paréntesis, el valor si falta.

**`cue_effect`:**

| Efecto | Qué hace | Ajustes |
|---|---|---|
| `gravity_drop` | La línea cae desde arriba y rebota antes de quedarse en su sitio. Una línea de menos de 0,25 s sale sin caída | `drop_height_px` (100), `bounce_elasticity` (0,30; entre 0 y 1) |

**`word_effect`:**

| Efecto | Qué hace | Ajustes |
|---|---|---|
| `highlight_in_sentence` | La palabra que suena va en `primary_colour`; las demás, en `secondary_colour` (o en `primary_colour` si falta) | — |
| `active_pill` | Un recuadro de color detrás de la palabra que suena | `pill_colour` (obligatorio), `pill_padding` (6), `pill_radius` (4) |
| `pop_in_sentence` | La palabra que suena crece y vuelve a su tamaño | `word_pop_scale` (125; entre 100 y 300, en %) |
| `alpha_fade` | Las palabras aparecen una a una con un fundido | `fade_duration_ms` (150) |
| `typewriter` | Las letras aparecen una a una, como a máquina | `typewriter_cursor` (no), `cursor_char` (`_`, un solo carácter) |
| `continuous_karaoke` | La línea se rellena de color sílaba a sílaba | Exige `cue_policy.syllabify: true` |

---

## 8. Tiempos por palabra de los efectos

Los efectos de `word_effect` necesitan saber cuándo suena cada palabra de la
línea. Para cada línea, `AssSubtitleBuilder` usa los tiempos de Whisper si sus
palabras coinciden con las de la línea (mismo número y mismo texto, sin contar
mayúsculas ni signos). Si no, reparte la duración de la línea entre sus
palabras en proporción a sus letras (`approximate_word_timings`), sin cambiar
los tiempos ni el texto de la línea.

| Ruta | De dónde salen los tiempos por palabra |
|---|---|
| GUION, IMAGEN y VIDEO | Del JSON de Whisper (`subtitles/subtitulos_whisper.json`), fuera de las pausas de la voz; una línea que no coincide (una palabra del guion distinta de lo que oyó Whisper) se reparte por letras |
| STUDIO, SOLO VIDEO | De Whisper; una línea que no coincide se reparte por letras |
| STUDIO, SRT + VIDEO y VIDEO + AUDIO \| SRT | No hay Whisper: siempre se reparte por letras dentro de cada línea del SRT, que se pinta tal cual |

Cómo se transcribe con Whisper y cómo se quitan las frases que inventa:
[ARCHITECTURE.md, apartado 14](ARCHITECTURE.md#14-subtítulos).

---

## 9. STUDIO: qué SRT se pinta y cuál se corrige

SRT + VIDEO y VIDEO + AUDIO | SRT pintan el SRT tal cual: del perfil solo toman
el aspecto (`render_style`) y `text_case`. SOLO VIDEO pinta un SRT adaptado al
modo de cue del perfil, `<proyecto>_<modo>.srt`; para corregir una palabra se
corrige ese archivo y se pinta con SRT + VIDEO. Qué archivo queda en cada caso:
[ARCHITECTURE.md, apartado 8](ARCHITECTURE.md#cómo-se-tratan-los-subtítulos-en-studio).
