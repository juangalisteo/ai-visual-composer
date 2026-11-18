# Assets

Qué viene con el proyecto en `assets/` y qué tiene que poner cada persona.
Lo que no viene se queda fuera de Git (`.gitignore`): quien lo tenga en su
equipo lo conserva, y nunca se sube.

## Qué viene con el proyecto

| Ruta | Qué es | Licencia |
| --- | --- | --- |
| `assets/fonts/Anton-Regular.ttf` | Fuente de subtítulos y fuente de reserva | SIL Open Font License 1.1 (en los metadatos del archivo). Del proyecto Anton de Google Fonts (`fonts.google.com/specimen/Anton`). Se puede repartir. |
| `assets/fonts/Oswald-VariableFont_wght.ttf` | Fuente de subtítulos | SIL Open Font License 1.1 (en los metadatos del archivo). Del proyecto Oswald de Google Fonts (`fonts.google.com/specimen/Oswald`). Se puede repartir. |

El catálogo de fuentes (nombre, alias, archivo y reserva) está en
`config/fonts.json`.

## Qué no viene y pone cada persona

### Fuentes Gotham Narrow Bold y Uni Sans Heavy (opcionales)

Muchos perfiles de subtítulos las piden, pero su licencia no permite
repartir los archivos:

| Archivo | Licencia | Dónde conseguirla |
| --- | --- | --- |
| `Gotham Narrow Bold.otf` | Comercial: acuerdo de licencia de usuario final de Hoefler & Co. (`typography.com/support/eula.html`). | Se compra en `typography.com`. |
| `Uni Sans Heavy.otf` | Fontfabric Free Font EULA 2.1: descarga gratuita y uso comercial permitido, pero no se puede repartir sin permiso escrito de Fontfabric. | Se descarga en `fontfabric.com`. |

Son opcionales: si falta una, los subtítulos usan su fuente de reserva,
Anton (declarada en `config/fonts.json`), y la terminal avisa una vez por
fuente. Para usar la original, pon el archivo en `assets/fonts/` con el
nombre exacto de la tabla.

### Música: `assets/music/<categoría>/`

No se reparte: es la música del autor (creada con Suno para su canal).
Cada persona pone la suya en subcarpetas de categoría, por ejemplo
`assets/music/calm/`. Formatos: `.mp3`, `.wav`, `.m4a`, `.aac` y `.flac`.
Los archivos sueltos en `assets/music/`, fuera de una subcarpeta, no se usan.
El nombre de la categoría es libre.

MÚSICA «Aleatoria» (o «Sí» en STUDIO) elige una pista al azar entre todas
las categorías. Sin pistas, elige «Sin música» (o «No»); si eliges música
y no hay ninguna, la terminal lo dice y remite a este archivo.

### Overlays: `assets/videos/overlays/<categoría>/`

No se reparten: los del autor salen de packs gratuitos de terceros cuya
licencia no se puede comprobar. Cada persona pone los suyos (`.mp4` o
`.mov`) en subcarpetas de categoría; el nombre de la categoría es libre y
OVERLAYS «Sí» elige entre todas.

Sin overlays, elige «No» en OVERLAYS; si eliges «Sí» y falta la carpeta, la
terminal lo dice y remite a este archivo.

### Efectos visuales: `assets/videos/visual_effects/LightLeak/`

No se reparten, por el mismo motivo que los overlays. Están desactivados
en todos los perfiles (`video_style.visual_effects.enabled: false`); solo
hacen falta si los activas. Formato: `.mov`.

### Intro y outro: `assets/videos/intro_outro/<formato>/intro/` y `…/outro/`

Siempre han estado fuera de Git: son los vídeos de cada canal. `<formato>`
es `vertical` u `horizontal`. Cómo se eligen: `docs/START.md`.

## Reglas para añadir un asset al repositorio

- Solo entra lo que se pueda repartir: con su procedencia y su licencia
  comprobadas y apuntadas en la tabla «Qué viene con el proyecto».
- Nunca entran: contenido generado, modelos de IA, checkpoints, LoRA, VAE,
  embeddings, recursos de ControlNet, runtimes externos, logs ni resultados
  locales.

## Propiedad intelectual

La música del autor es de Juan Bautista Galisteo Marqués y no se reparte con
el proyecto. Los overlays y efectos del autor son de terceros y tampoco se
reparten. Cada fuente se rige por su propia licencia (tablas de arriba), no
por la del proyecto (`LICENSE`).
