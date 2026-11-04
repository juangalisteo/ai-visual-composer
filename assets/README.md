# Assets oficiales

Esta carpeta contiene los assets oficiales del producto AI Visual Composer.

Estos assets se versionan a propósito cuando forman parte del comportamiento
actual del producto. No son dependencias locales de ejecución, resultado
generado, archivos de modelo, checkpoints ni recursos privados de
desarrollo.

## Gobierno de los assets

- Un asset oficial del producto puede subirse al repositorio cuando lo
  necesita el producto.
- El tamaño de un asset, por sí solo, no es motivo para quitarlo mientras el
  tamaño del repositorio siga siendo razonable para el proyecto.
- Los assets solo de desarrollo, los experimentos locales, el contenido
  generado, los modelos de IA, los checkpoints, las LoRA, los archivos VAE,
  los embeddings, los recursos de ControlNet, los runtimes externos, los
  logs y los resultados locales se quedan fuera del repositorio público.
- Todo asset nuevo debe tener confirmada su procedencia y sus condiciones de
  uso antes de subirse.
- Cada asset oficial nuevo que se añada al proyecto debe documentar su
  procedencia, su licencia o sus condiciones de uso en el momento en que se
  sube al repositorio.

## Propiedad intelectual

La música, los overlays y los efectos visuales de esta carpeta son
propiedad de Juan Bautista Galisteo Marqués.

Copiar, redistribuir, reutilizar, modificar o usar estos assets sin su
autorización expresa está prohibido. Que estén incluidos en el repositorio
no transfiere ningún derecho de propiedad intelectual sobre ellos.

Las 4 fuentes de `assets/fonts/` (ver inventario) son una excepción: no son
propiedad del propietario del proyecto. Cada una se rige por su propia
licencia de origen, documentada en el inventario de abajo. Anton y Oswald se
pueden repartir con el proyecto porque su licencia (SIL Open Font License) lo
permite; Gotham Narrow Bold y Uni Sans Heavy están incluidas hoy en el
repositorio, pero su licencia no permite repartir el archivo.

Todo asset oficial nuevo que se incorpore al proyecto (música, overlays,
efectos visuales u otro recurso propio) pasa a formar parte de la propiedad
intelectual de Juan Bautista Galisteo Marqués y debe documentar su
procedencia, su licencia o sus condiciones de uso en el momento en que se
incorpora al repositorio. Esto no aplica a una fuente u otro recurso de
terceros, que se rige siempre por su propia licencia.

## Inventario

`assets/fonts/` contiene 4 archivos: 2 OTF (`Gotham Narrow Bold.otf`,
`Uni Sans Heavy.otf`) y 2 TTF (`Anton-Regular.ttf`,
`Oswald-VariableFont_wght.ttf`).

| Ruta | Tipo | Función en el producto | Estado en Git | Asset oficial | Procedencia o documentación de licencia |
| --- | --- | --- | --- | --- | --- |
| `assets/fonts/Anton-Regular.ttf` | Fuente TTF | Renderizado de fuente de subtítulos | Versionado | Sí | SIL Open Font License, versión 1.1 (verificada en los metadatos del propio archivo). De los autores del proyecto Anton en Google Fonts; se descarga desde la página oficial de Google Fonts (`fonts.google.com/specimen/Anton`). Esta licencia permite repartir el archivo. |
| `assets/fonts/Oswald-VariableFont_wght.ttf` | Fuente TTF variable | Renderizado de fuente de subtítulos | Versionado | Sí | SIL Open Font License, versión 1.1 (verificada en los metadatos del propio archivo). De los autores del proyecto Oswald en Google Fonts; se descarga desde la página oficial de Google Fonts (`fonts.google.com/specimen/Oswald`). Esta licencia permite repartir el archivo. |
| `assets/fonts/Gotham Narrow Bold.otf` | Fuente OTF | Renderizado de fuente de subtítulos | Versionado | Sí, con licencia propia | Acuerdo de licencia de usuario final de Hoefler & Co (verificado en los metadatos del propio archivo, que remiten a `typography.com/support/eula.html`). Comprada por el propietario del proyecto. Se descarga/compra desde la página oficial de Hoefler & Co (`typography.com`). Esta licencia no permite repartir el archivo. |
| `assets/fonts/Uni Sans Heavy.otf` | Fuente OTF | Renderizado de fuente de subtítulos | Versionado | Sí, con licencia propia | Los metadatos del propio archivo no incluyen el nombre de la licencia ni una URL de licencia, y en `assets/fonts/` no hay ningún archivo de licencia que lo acompañe: **el nombre exacto de la licencia no se ha podido confirmar desde el archivo**. La URL del diseñador en sus metadatos es la de Fontfabric (`fontfabric.com`), que es su fabricante y su página oficial de descarga. El propietario decide que esta licencia no permite repartir el archivo. |
| `assets/music/action/` | Música MP3 | Categoría de música de acción | Versionado | Sí | Música original del propietario, creada con Suno (plan Pro) para MODO CONCIENCIA STUDIO. Es suya. |
| `assets/music/ambient/` | Música MP3 | Categoría de música ambiental | Versionado | Sí | Música original del propietario, creada con Suno (plan Pro) para MODO CONCIENCIA STUDIO. Es suya. |
| `assets/music/calm/` | Música MP3 | Categoría de música tranquila | Versionado | Sí | Música original del propietario, creada con Suno (plan Pro) para MODO CONCIENCIA STUDIO. Es suya. |
| `assets/music/cinematic/` | Música MP3 | Categoría de música cinematográfica | Versionado | Sí | Música original del propietario, creada con Suno (plan Pro) para MODO CONCIENCIA STUDIO. Es suya. |
| `assets/music/documentary/` | Música MP3 | Categoría de música documental | Versionado | Sí | Música original del propietario, creada con Suno (plan Pro) para MODO CONCIENCIA STUDIO. Es suya. |
| `assets/music/electronic/` | Música MP3 | Categoría de música electrónica | Versionado | Sí | Música original del propietario, creada con Suno (plan Pro) para MODO CONCIENCIA STUDIO. Es suya. |
| `assets/music/emotional/` | Música MP3 | Categoría de música emotiva | Versionado | Sí | Música original del propietario, creada con Suno (plan Pro) para MODO CONCIENCIA STUDIO. Es suya. |
| `assets/music/epic/` | Música MP3 | Categoría de música épica | Versionado | Sí | Música original del propietario, creada con Suno (plan Pro) para MODO CONCIENCIA STUDIO. Es suya. |
| `assets/music/meditation/` | Música MP3 | Categoría de música de meditación | Versionado | Sí | Música original del propietario, creada con Suno (plan Pro) para MODO CONCIENCIA STUDIO. Es suya. |
| `assets/music/mystery/` | Música MP3 | Categoría de música de misterio | Versionado | Sí | Música original del propietario, creada con Suno (plan Pro) para MODO CONCIENCIA STUDIO. Es suya. |
| `assets/videos/overlays/Electricity/` | Overlays MP4 | Categoría temática de overlay inteligente | Versionado | Sí | Propiedad de Juan Bautista Galisteo Marqués; su uso requiere autorización expresa. |
| `assets/videos/overlays/Light Leaks/` | Overlays MP4 | Overlay inteligente neutro de reserva y separador | Versionado | Sí | Propiedad de Juan Bautista Galisteo Marqués; su uso requiere autorización expresa. |
| `assets/videos/visual_effects/LightLeak/` | Efectos visuales MOV | Efectos visuales LightLeak | Versionado | Sí | Propiedad de Juan Bautista Galisteo Marqués; su uso requiere autorización expresa. |

Esta tabla no da el número de pistas de música ni el tamaño en disco de cada
carpeta porque son cifras que cambian con el tiempo; el recuento y el
tamaño reales están en el propio directorio.
