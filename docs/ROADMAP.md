# Hoja de ruta de AI Visual Composer

## 1. Estado actual

AI Visual Composer genera hoy proyectos audiovisuales completos a partir de un
guion, un tema o una descripción visual, y también termina material propio ya
grabado. El menú principal ofrece cuatro componentes:

- **GUION, IMAGEN y VIDEO** comparten la ruta estándar: a partir de un texto o
  de un tema, generan voz, subtítulos, storyboard, imágenes o clips de vídeo
  (imagen a vídeo) y componen el vídeo final.
- Dentro de GUION, el destino «Diseño» abre **DISEÑO**: genera una sola
  imagen o un solo clip a partir de una descripción visual directa, sin voz,
  música ni subtítulos.
- **STUDIO** termina material que el usuario ya tiene grabado (vídeo, audio o
  SRT): transcribe, pinta subtítulos, cambia el audio, añade intro/outro,
  monta varios vídeos o exporta un SRT.

Cómo se usa cada ruta está en [START.md](START.md); cómo están construidas por
dentro, en [ARCHITECTURE.md](ARCHITECTURE.md); la referencia de subtítulos
(familias, perfiles y efectos), en [SUBTITLES.md](SUBTITLES.md).

## 2. Próximas etapas

En este orden:

1. **Herramientas de calidad.** Formato de código automático y tests que se
   ejecuten solos en cada cambio.
2. **Flujo profesional en GitHub.** Trabajar con ramas y Pull Request por
   cambio, en lugar de subir directamente.
3. **Optimizar la generación con IA.** Mejorar los prompts, la calidad de las
   imágenes y los clips generados, el ritmo con el que habla la voz, y añadir
   un segundo motor de voz más natural.
4. **Traductor de guiones.** Traducir un guion y generar el proyecto en otro
   idioma. Con esta función llega la versión `3.0.0`.
5. **Clonación de voz.** El usuario aporta un audio de su propia voz (o de
   alguien que le haya dado permiso) y el sistema genera el guion leído con
   ella; solo se admiten voces propias o autorizadas por su dueño. Llega con
   la versión `3.1.0`.
6. **Ajuste visual de los subtítulos.** Afinar su posición, color, tamaño y
   demás detalles de aspecto.

La historia de cambios ya hechos está en [CHANGELOG.md](../CHANGELOG.md).

---

Copyright © 2026 Juan Bautista Galisteo Marqués.

AI Visual Composer es obra de Juan Bautista Galisteo Marqués, que lo creó y lo
mantiene.
