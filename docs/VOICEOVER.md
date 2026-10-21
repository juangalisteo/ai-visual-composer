# AI VISUAL COMPOSER — VOICEOVER

## REFERENCIA DE DURACIÓN DE LOCUCIÓN

### DATOS DE REFERENCIA

135 palabras = 1:00 minuto
Velocidad aproximada: 135 palabras/minuto

91 palabras = 0:42 segundos
Velocidad aproximada: 130 palabras/minuto

### CÁLCULO DE REFERENCIA

Rango real observado: 130–135 palabras/minuto.

### TIEMPO ESTIPULADO PARA LOS GUIONES

30 segundos → 65–70 palabras
40 segundos → 87–93 palabras
45 segundos → 98–105 palabras
50 segundos → 108–117 palabras
60 segundos → 130–140 palabras

## SUBTÍTULOS

SYSTEM es la autoridad audiovisual: formato, resolución, vídeo, audio y demás
valores de la pieza. STANDARD y DESIGN son perfiles especializados de estilo
visual de subtítulos. DESIGN no sustituye SYSTEM.

La composición real es:

```text
SRT → tratamiento funcional → estilo visual → renderer
```

ORIGINAL toma el SRT humano como autoridad. Conserva cues, índices, orden,
timestamps y segmentación. Sólo puede aplicar la transformación textual
explícita `uppercase` del perfil.

Línea única reutiliza el tratamiento existente que prepara cues de lectura
continua a partir del SRT. Palabra por palabra reutiliza el tratamiento
existente que genera cues por palabra con su política de duración y micro-cues.
Ambos se aplican antes del estilo visual y no tienen variantes separadas para
STANDARD o DESIGN.

El backend de render se decide después del tratamiento funcional. Sin dinámica,
`render_style.dynamic` ausente o `false` conserva SRT, el filtro `subtitles` de
FFmpeg, `fontsdir` y `force_style`. SRT sigue siendo la autoridad temporal.

Con `dynamic: true`, ASS es una representación temporal de render: se construye
a partir del SRT final, usa `PlayResX/Y` derivados de SYSTEM, Styles V4+, Events
y Dialogue, y FFmpeg aplica el filtro `ass`. El temporal no sobrescribe el SRT
del usuario, se limpia tras el render y también ante error.

### Propiedades estáticas implementadas

Todas se declaran en `render_style` del perfil especializado, se validan con
`SubtitleConfigLoader`, llegan a `SubtitleStyleBuilder` y se serializan en
`force_style` para libass.

#### font

Finalidad: familia tipográfica. Tipo: texto no vacío. Consumidor: `FontManager`
y `SubtitleStyleBuilder`. Ejemplo: `"font": "oswald"`.

#### font_size

Finalidad: tamaño visual. Tipo: entero mayor que cero. Consumidor: `FontSize`.
Ejemplo: `"font_size": 22`.

#### bold, italic, underline y strikeout

Finalidad: peso y decoraciones tipográficas. Tipo: booleano. Consumidor:
`Bold`, `Italic`, `Underline` y `StrikeOut`. `bold` es obligatorio; los otros
tres son opcionales y, si faltan, no alteran el baseline. Ejemplo:
`"italic": true`.

#### primary_colour, outline_colour, back_colour y secondary_colour

Finalidad: colores ASS. Tipo: texto `&HAABBGGRR`. Consumidor: las propiedades
ASS homónimas, incluida `SecondaryColour` si se declara. Ejemplo:
`"primary_colour": "&H00FFFFFF"`.

#### border_style, outline y shadow

Finalidad: borde y sombra. `border_style` admite `1` o `3`; `outline` y
`shadow` son enteros no negativos. Consumidor: `BorderStyle`, `Outline` y
`Shadow`. Ejemplo: `"shadow": 1`.

#### alignment, margin_v, margin_l y margin_r

Finalidad: posición estática y márgenes. `alignment` es entero de 1 a 9;
`margin_v`, `margin_l` y `margin_r` son enteros no negativos. Los dos últimos
son opcionales. Consumidor: `Alignment`, `MarginV`, `MarginL` y `MarginR`.
Ejemplo: `"alignment": 2`.

#### scale_x, scale_y y spacing

Finalidad: escala horizontal, escala vertical y espaciado. Tipo: número finito;
son opcionales. Consumidor: `ScaleX`, `ScaleY` y `Spacing`. Ejemplo:
`"spacing": 1.5`.

#### uppercase

Finalidad: política textual de `cue_policy`, no propiedad ASS. Tipo: booleano.
Consumidor: `TextCasePolicy`. En ORIGINAL cambia sólo texto y conserva toda la
estructura temporal. Ejemplo: `"uppercase": true`.

### Disponible pero no activado por perfiles oficiales

`italic`, `underline`, `strikeout`, `secondary_colour`, `margin_l`, `margin_r`,
`scale_x`, `scale_y` y `spacing` están implementados y validados, pero no se
declaran en los perfiles oficiales actuales. Su ausencia conserva la apariencia
aprobada, incluido Modo Conciencia | Reels.

### No son propiedades visuales estáticas

`offset` se valida en `render_style`, pero es un desplazamiento temporal de SRT
y no se serializa en `force_style`. STUDIO exige `offset = 0` para preservar
los timestamps humanos.

### Dinámica ASS declarativa

`render_style.effects` admite un único efecto por cue y requiere `dynamic:
true`: `fade` (`\fad`), `pop` y `zoom` (`\fscx`, `\fscy`, `\t`), o `slide`
(`\move`). Sus ventanas son internas al Dialogue, con clamp determinista para
cues cortos; no cambian Start/End, texto, orden ni segmentación.

`render_style.word_effects` admite un único efecto por palabra y también
requiere `dynamic: true`: `karaoke` (`\kf`), `highlight` (`\1c` con color ASS
declarado) o `progressive_reveal` (`\1a` y `\t`). `effects` y `word_effects`
son incompatibles en una misma representación.

Los efectos por palabra usan exclusivamente los tiempos de los cues finales de
Palabra por palabra. Requieren un cue final de una sola palabra; ORIGINAL y
Línea única multifrase no se resegmentan para ASS y fallan de forma controlada
si se intenta aplicarles un word effect. Karaoke convierte milisegundos a
centésimas ASS de forma determinista, sin timestamps inventados.

Los tags ASS los genera exclusivamente el sistema. El texto humano sigue
escapando barras, llaves y saltos para impedir que se convierta en comandos.
No hay Whisper, retranscripción, forced alignment ni análisis de audio nuevo.

Los perfiles oficiales actuales no declaran `dynamic`, `effects` ni
`word_effects`: mantienen el backend SRT aprobado. Modo Conciencia | Reels
continúa actualmente en SRT.
