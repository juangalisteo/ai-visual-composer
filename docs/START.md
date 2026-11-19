# Guía de uso de AI Visual Composer

Este documento explica cómo se usa el programa en el día a día: cómo se arranca
y se para, qué pregunta cada menú, qué archivo va en cada carpeta de `input/` y
dónde sale el resultado.

Otros documentos:

| Para saber… | Documento |
|---|---|
| Cómo se instala (Python, FFmpeg, Ollama, ComfyUI, modelos) | [INSTALL.md](INSTALL.md) |
| Cómo está construido por dentro | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Qué familias y perfiles de subtítulos hay y cómo se ven | [SUBTITLES.md](SUBTITLES.md) |
| Cómo se genera la voz y cuánto dura un guion | [VOICEOVER.md](VOICEOVER.md) |

---

## 1. Antes de empezar

El programa tiene que estar instalado y comprobado: [INSTALL.md](INSTALL.md).

No todas las rutas necesitan los mismos programas. Piper (voz), Whisper
(transcripción) y FFmpeg se usan sin arrancar nada aparte; Ollama y ComfyUI
tienen que estar en marcha antes de lanzar las rutas que los usan:

| Qué vas a hacer | Ollama | ComfyUI |
|---|---|---|
| GUION: «Solo audio» o «Audio + subtítulos» | No | No |
| GUION: «Audio + subtítulos + storyboard» | Sí | No |
| GUION: «Proyecto completo» o «Proyecto completo sin subtítulos» | Sí | Sí |
| IMAGEN o VIDEO: «Solo audio», «Audio + subtítulos» o «Audio + subtítulos + storyboard» | Sí (escribe el guion) | No |
| IMAGEN o VIDEO: «Proyecto completo» | Sí | Sí |
| DISEÑO | Sí | Sí |
| STUDIO | No | No |

---

## 2. Arranque

Orden normal:

```text
1. Ollama
2. ComfyUI
3. AI Visual Composer
```

**Ollama.** Abre la aplicación de Ollama. Si no la usas, arráncalo desde una
terminal y déjala abierta:

```powershell
ollama serve
```

**ComfyUI.** En otra terminal, desde la raíz del proyecto (ComfyUI está en la
carpeta local `ComfyUI/`, fuera de Git):

```powershell
cd ComfyUI
.\run_nvidia_gpu.bat
```

Déjala abierta. El programa lo busca en `http://127.0.0.1:8188`.

**AI Visual Composer.** En otra terminal, desde la raíz del proyecto:

```powershell
python main.py
```

Antes del primer menú, el programa comprueba la configuración de formatos; si
está mal, se para con un error y no muestra ningún menú.

---

## 3. Parada

- **Salir desde un menú:** escribe `0` en cualquier menú (también en
  «Nombre:» y en «Introduce el orden de montaje:»). La terminal muestra:

  ```text
  CANCELADO
  La operación fue cancelada por el usuario.
  ```
- **Cortar una ejecución en marcha:** Ctrl+C («La operación fue interrumpida
  por el usuario.»). Lo que estuviera a medias en `output/<proyecto>/` queda
  incompleto.
- **Al terminar:** cierra la terminal de AI Visual Composer, después la de
  ComfyUI y por último Ollama, si ya no los necesitas. No los cierres mientras
  haya una generación en marcha.
- **Las generaciones de Ollama y de los clips de vídeo (Wan) no tienen tiempo
  límite:** una que tarda mucho no es un fallo, solo hay que esperar.

---

## 4. Menú principal y preguntas comunes

```text
AI VISUAL COMPOSER

1. Guion
2. Imagen
3. Video
4. Studio
```

| Opción | Para qué sirve | Apartado |
|---|---|---|
| Guion | Narrar un texto escrito por ti y hacer con él un proyecto de Imagen o de Video; también abre DISEÑO | [5](#5-guion-imagen-y-video) y [6](#6-diseño) |
| Imagen | Escribir un tema; la IA escribe el guion y el vídeo se hace con imágenes generadas | [5](#5-guion-imagen-y-video) |
| Video | Como Imagen, pero cada imagen se convierte en un clip de vídeo | [5](#5-guion-imagen-y-video) |
| Studio | Terminar vídeos, audios y SRT que ya tienes | [7](#7-studio) |

Tres preguntas salen en casi todas las rutas:

- **FORMATO** («1. Vertical 9:16», «2. Horizontal 16:9»): tamaño y orientación
  del vídeo. Para qué redes sirve cada uno:
  [ARCHITECTURE.md, apartado 4](ARCHITECTURE.md#4-formatos).
- **PROYECTO** («Nombre:»): obligatorio. Es el nombre de la carpeta
  `output/<proyecto>/` y del vídeo final. Los caracteres `< > : " / \ | ? *` se
  quitan del nombre.
- **ELIMINAR OUTPUT** («1. Sí», «2. No»): con «Sí», antes de empezar se borra
  **toda** la carpeta `output/`, con todos los proyectos, no solo el de este
  nombre.

---

## 5. GUION, IMAGEN y VIDEO

### Qué escribir antes de lanzar

| Componente | Archivo | Qué escribir |
|---|---|---|
| Guion | `input/guion.txt` | El texto completo que se va a narrar |
| Imagen y Video | `input/tema.txt` | Un tema o una idea; la IA escribe el guion |

**Guion escrito por ti.** GUION narra el texto de `input/guion.txt` tal cual:
manda el texto, no se recorta ni se alarga, y la duración del vídeo es la que
dure su lectura. Una línea en blanco entre párrafos hace una pausa en la voz, y
tras cada frase hay otra; los valores están en
[VOICEOVER.md, apartado 5](VOICEOVER.md#5-pausas).

Con un tema, la duración la marca el perfil de Imagen o Video
([VOICEOVER.md, apartado 3](VOICEOVER.md#3-cuánto-dura-un-guion)).

Los cuatro `.txt` de `input/` están vacíos en el repositorio; cómo evitar que
lo que escribas salga en Git: [INSTALL.md](INSTALL.md).

### Menús

GUION pregunta primero el destino:

```text
DESTINO

1. Imagen
2. Video
3. Diseño
```

«Diseño» abre DISEÑO ([apartado 6](#6-diseño)). Con «Imagen» o
«Video», y directamente en Imagen y en Video, siguen estos menús (los que no
corresponden al modo elegido no salen):

```text
MODO → FORMATO → SUBTÍTULOS (FAMILIA → PERFIL) → VOZ → MÚSICA → OVERLAYS → INTRO / OUTRO → PROYECTO → ELIMINAR OUTPUT
```

### Modos

| Modo (menú MODO) | Qué obtienes | Pide subtítulos | Pide OVERLAYS e INTRO / OUTRO |
|---|---|---|---|
| Proyecto completo | El vídeo final con subtítulos | Sí | Sí |
| Solo audio | La locución y el audio con música | No | No |
| Audio + subtítulos | Lo anterior y el SRT | Sí | No |
| Audio + subtítulos + storyboard | Lo anterior y las escenas del vídeo | Sí | No |
| Proyecto completo sin subtítulos | El vídeo final sin texto (solo en GUION) | No | Sí |

Hasta qué etapa llega cada modo: [ARCHITECTURE.md, apartado 6](ARCHITECTURE.md#6-modos-de-ejecución).

### Qué pregunta cada menú

- **SUBTÍTULOS → FAMILIA → PERFIL:** el estilo de los subtítulos. Las familias y
  los perfiles de cada componente y formato están en
  [SUBTITLES.md](SUBTITLES.md#3-perfiles-por-componente-y-formato).
- **VOZ:** «1. Carlfm» o «2. Davefx» ([VOICEOVER.md](VOICEOVER.md#1-voces)).
- **MÚSICA:** «1. Aleatoria» (una pista al azar de `assets/music/`, por debajo
  de la voz) o «2. Sin música».
- **OVERLAYS:** «1. Sí» superpone vídeos de `assets/videos/overlays/` sobre el
  vídeo final; «2. No», sin ellos.
- La música y los overlays no vienen con el proyecto: pon los tuyos
  ([assets/README.md](../assets/README.md)).
- **INTRO / OUTRO:** «1. NINGUNO», «2. SOLO INTRO», «3. SOLO OUTRO» o
  «4. INTRO + OUTRO». Después, SELECCIONAR INTRO y SELECCIONAR OUTRO listan los
  `.mp4` de `assets/videos/intro_outro/<formato>/intro/` y
  `assets/videos/intro_outro/<formato>/outro/`, donde `<formato>` es `vertical`
  o `horizontal`. Esa carpeta es local (fuera de Git): pon ahí tus intros y
  outros.

---

## 6. DISEÑO

Genera **una sola** imagen o **un solo** clip a partir de una descripción
visual escrita por ti. No hace voz, música, subtítulos ni vídeo final.

```text
Guion → DESTINO: Diseño → DISEÑO: Imagen o Video → FORMATO → PROYECTO → ELIMINAR OUTPUT
```

| Destino | Archivo | Resultado |
|---|---|---|
| Diseño → Imagen | `input/guion_imagen.txt` | Una imagen en `output/<proyecto>/images/` |
| Diseño → Video | `input/guion_video.txt` | Un clip en `output/<proyecto>/video_clips/` |

La descripción tiene que dar una sola escena; si no, la ejecución se para con
un error. Cómo funciona: [ARCHITECTURE.md, apartado 7](ARCHITECTURE.md#7-diseño).

---

## 7. STUDIO

STUDIO termina material que ya tienes. No usa la IA generativa, así que no
necesita Ollama ni ComfyUI.

```text
ENTRADA

1. SOLO VIDEO
2. SRT + VIDEO
3. INTRO / OUTRO
4. MONTAJE VÍDEOS
5. VIDEO + AUDIO | SRT
6. EXPORTAR SRT ➜  VIDEO
```

### Qué archivo va en cada carpeta

| Modo | Carpeta | Qué poner |
|---|---|---|
| SOLO VIDEO | `input/studio/video/` | Un vídeo `.mp4` con audio |
| SRT + VIDEO | `input/studio/srt_video/` | Un vídeo `.mp4` y un `.srt` |
| INTRO / OUTRO | `input/studio/intro_outro/` | El vídeo `.mp4` al que se añade la intro, el outro o los dos |
| MONTAJE VÍDEOS | `input/studio/montaje_videos/` | Dos o más vídeos `.mp4` |
| VIDEO + AUDIO \| SRT | `input/studio/video_audio_srt/` | Un vídeo `.mp4`, un audio (`.mp3`, `.wav`, `.m4a`, `.aac` o `.flac`) y, si quieres subtítulos, un `.srt` |
| EXPORTAR SRT ➜  VIDEO, TRANSCRIBIR | `input/studio/exportar_srt/transcribir/` | Un `.mp4` o un `.mp3` |
| EXPORTAR SRT ➜  VIDEO, CONVERTIR | `input/studio/exportar_srt/convertir/` | Un `.srt` |

- STUDIO busca los archivos **por extensión**, no por nombre. Si hay uno solo
  del tipo que necesita, lo usa sin preguntar; si hay varios, muestra un menú
  con sus nombres (VIDEO, SRT, AUDIO o MEDIA).
- Un `.srt` tiene que estar en UTF-8 y tener al menos un bloque válido (número,
  tiempos `00:00:01,000 --> 00:00:02,000` y texto).
- Los archivos de entrada no se modifican. El contenido de `input/studio/` no
  se versiona; solo lo están los `README_*.md` de cada carpeta.

### Dónde sale el resultado

- Los modos que hacen vídeo lo dejan en `output/<proyecto>/video/<proyecto>.mp4`.
- Los SRT quedan en `output/<proyecto>/subtitles/`. Qué archivo sale en cada
  modo: [ARCHITECTURE.md, apartado 8](ARCHITECTURE.md#cómo-se-tratan-los-subtítulos-en-studio).
- Al terminar, la terminal muestra un resumen con la entrada, el resultado y
  los tiempos.

### 7.1 SOLO VIDEO

```text
ENTRADA → FORMATO → SUBTÍTULOS (FAMILIA → PERFIL) → VIDEO (si hay varios) → MÚSICA → INTRO / OUTRO → PROYECTO → ELIMINAR OUTPUT
```

Whisper transcribe el audio del vídeo y el texto se corta en líneas según el
perfil de subtítulos elegido antes de pintarlo. El vídeo tiene que tener audio.
MÚSICA («1. Sí», «2. No») añade una pista al azar por debajo del audio
original. INTRO / OUTRO funciona como en el [apartado 5](#qué-pregunta-cada-menú).

### 7.2 SRT + VIDEO

```text
ENTRADA → FORMATO → SUBTÍTULOS (FAMILIA → PERFIL) → VIDEO y SRT (si hay varios) → MÚSICA → INTRO / OUTRO → PROYECTO → ELIMINAR OUTPUT
```

Pinta tu SRT **tal cual**: mismo texto, mismas líneas y mismos tiempos. No es
una opción del menú. Del perfil elegido solo se toma el aspecto y, si lo
declara, el paso a mayúsculas. Por qué es así:
[ARCHITECTURE.md, apartado 8](ARCHITECTURE.md#cómo-se-tratan-los-subtítulos-en-studio).

**Corregir los subtítulos de un vídeo hecho con SOLO VIDEO.** Si Whisper
escribió mal una palabra:

1. Abre `output/<proyecto>/subtitles/<proyecto>_<modo>.srt`, el SRT que se
   pintó (`<modo>` es el modo de corte del perfil, por ejemplo
   `<proyecto>_single_line.srt`). **No** corrijas `<proyecto>.srt`: es la
   transcripción de Whisper antes de cortarla en líneas.
2. Corrige la palabra y guarda en UTF-8.
3. Pon ese `.srt` y el vídeo original en `input/studio/srt_video/`.
4. Lanza SRT + VIDEO con el mismo perfil de subtítulos.

### 7.3 INTRO / OUTRO

```text
ENTRADA → FORMATO → VIDEO (si hay varios) → INTRO / OUTRO → SELECCIONAR INTRO / SELECCIONAR OUTRO → PROYECTO → ELIMINAR OUTPUT
```

El vídeo va directamente en `input/studio/intro_outro/`, sin subcarpetas. El
menú INTRO / OUTRO ofrece «1. SOLO INTRO», «2. SOLO OUTRO» y
«3. INTRO + OUTRO». Las intros y los outros salen de
`assets/videos/intro_outro/vertical/` o `assets/videos/intro_outro/horizontal/`,
según el FORMATO elegido, cada uno con sus carpetas `intro/` y `outro/`.

### 7.4 MONTAJE VÍDEOS

```text
ENTRADA → FORMATO → VÍDEOS ENCONTRADOS → Introduce el orden de montaje: → TRANSICIONES → MÚSICA → INTRO / OUTRO → PROYECTO → ELIMINAR OUTPUT
```

VÍDEOS ENCONTRADOS numera los `.mp4` de la carpeta (`[1] nombre.mp4`,
`[2] …`). En «Introduce el orden de montaje:» se escriben los números
separados por espacios, por ejemplo `2 1 3`: al menos dos, sin repetir; los
que no se escriben no entran. TRANSICIONES («1. Sí», «2. No») une los clips con
un fundido corto o uno detrás de otro. El montaje no lleva subtítulos.

### 7.5 VIDEO + AUDIO | SRT

```text
ENTRADA → FORMATO → VIDEO y AUDIO (si hay varios) → SUBTÍTULOS (1. Sí / 2. No) → con «Sí»: SRT y FAMILIA → PERFIL → AUDIO MÁS CORTO QUE EL VÍDEO (solo si lo es) → PROYECTO → ELIMINAR OUTPUT
```

Cambia el audio del vídeo por el nuevo. Manda la duración del **vídeo**. Si el
audio nuevo es más corto, el menú AUDIO MÁS CORTO QUE EL VÍDEO ofrece rellenar
el final con «1. SIN MÚSICA» (silencio) o «2. CON MÚSICA». Con subtítulos, pinta
el SRT **tal cual**, igual que [SRT + VIDEO](#72-srt--video).

### 7.6 EXPORTAR SRT ➜  VIDEO

No hace ningún vídeo: solo un SRT. El menú MODO ofrece:

| Modo | Menús | Qué hace | Resultado |
|---|---|---|---|
| TRANSCRIBIR | MEDIA (si hay varios) → PROYECTO → ELIMINAR OUTPUT | Whisper transcribe el `.mp4` o el `.mp3` | `output/<proyecto>/subtitles/<proyecto>.srt` |
| CONVERTIR | SRT (si hay varios) → FORMATO → SUBTÍTULOS (FAMILIA → PERFIL) → PROYECTO → ELIMINAR OUTPUT | Corta tu SRT en líneas según el perfil elegido | `output/<proyecto>/subtitles/<proyecto>_<modo>.srt` |

---

## 8. Dónde sale el resultado

Todo se escribe en `output/<proyecto>/`. Lo principal de cada ruta:

| Ruta | Resultado principal |
|---|---|
| «Proyecto completo» y «Proyecto completo sin subtítulos» | `video/<proyecto>.mp4` |
| «Solo audio» | `audio/voz.mp3` (locución) y `audio/audio_final.mp3` (con música) |
| «Audio + subtítulos» | Lo anterior y `subtitles/subtitulos.srt` |
| «Audio + subtítulos + storyboard» | Lo anterior y `storyboard/storyboard.json` |
| DISEÑO | Una imagen en `images/` o un clip en `video_clips/` |
| STUDIO | `video/<proyecto>.mp4` y, si hay subtítulos, los SRT de `subtitles/` ([apartado 7](#dónde-sale-el-resultado)) |

Lista completa de carpetas y archivos:
[ARCHITECTURE.md, apartado 10](ARCHITECTURE.md#10-salida). `output/` está fuera
de Git: se puede borrar cuando quieras.

---

## 9. Problemas frecuentes

Cuando algo falla, la terminal muestra siempre el mismo bloque: `ERROR`, qué
pasa, la operación y qué hacer. Por ejemplo, en MONTAJE VÍDEOS sin vídeos:

```text
ERROR
No se encontró ningún archivo MP4 en input\studio\montaje_videos.
Operación: STUDIO/montaje_videos
Acción recomendada: Pon en esa carpeta dos o más vídeos .mp4 y vuelve a intentarlo.
```

La tabla recoge los mensajes más frecuentes:

| Lo que ves | Qué hacer |
|---|---|
| «No se pudo completar la solicitud a Ollama.» | Arranca Ollama y comprueba que el modelo esté descargado ([INSTALL.md](INSTALL.md)) |
| «ComfyUI no pudo generar la imagen solicitada.» o «… el clip de video solicitado.» | Comprueba que ComfyUI esté abierto en `http://127.0.0.1:8188` |
| «No se puede eliminar OUTPUT porque uno de sus archivos está siendo utilizado por otro programa.» | Cierra el programa que tiene abierto ese archivo (reproductor, editor de vídeo…) y vuelve a lanzar |
| «El archivo input/guion.txt está vacío.» o «No existe input/guion.txt.» (lo mismo con `input/tema.txt`) | Escribe el guion en `input/guion.txt` (Guion) o el tema en `input/tema.txt` (Imagen y Video) y vuelve a lanzar |
| «El diseño visual manual está vacío: input/guion_imagen.txt.», «El diseño visual de vídeo está vacío: input/guion_video.txt.» o «No existe el diseño visual …» | Escribe el diseño en ese archivo ([apartado 6](#6-diseño)) y vuelve a lanzar |
| «No hay archivos MP4 disponibles para INTRO en assets/videos/intro_outro/vertical/intro/.» (o para OUTRO, o en `horizontal/`) | Pon al menos un `.mp4` en esa carpeta o elige otra opción en INTRO / OUTRO |
| «No existe la carpeta de música: assets\music», «No se encontraron pistas musicales válidas en: assets\music» o «No existe la carpeta de overlays: assets\videos\overlays» | La música y los overlays no vienen con el proyecto: pon los tuyos ([assets/README.md](../assets/README.md)) o elige «Sin música» u OVERLAYS «No» |
| «No existe la carpeta de entrada STUDIO: input\studio\montaje_videos» (o «… para INTRO / OUTRO: input\studio\intro_outro.», «… VIDEO + AUDIO \| SRT: input\studio\video_audio_srt.», «… EXPORTAR SRT ➜  VIDEO: input\studio\exportar_srt\transcribir») | Crea esa carpeta y pon en ella los archivos del modo ([apartado 7](#qué-archivo-va-en-cada-carpeta)) |
| «No se encontró ningún archivo … en input\studio\…» | Pon el archivo con la extensión correcta en la carpeta del modo ([apartado 7](#qué-archivo-va-en-cada-carpeta)) |
| «El archivo SRT de STUDIO debe estar codificado en UTF-8», «… está vacío» o «… no contiene cues utilizables» | Guarda el `.srt` en UTF-8 y revisa el formato de sus bloques |
| «No se pudo sacar el audio de input\studio\exportar_srt\transcribir\… para transcribirlo.» | El `.mp4` no es un vídeo válido o no tiene sonido: usa otro |
| «Solo se encontró un archivo MP4 en input\studio\montaje_videos.» | Pon en esa carpeta dos o más vídeos `.mp4` y vuelve a lanzar |
| «Selecciona al menos dos clips para MONTAJE VÍDEOS.» | Escribe dos o más números de clip separados por espacios |
| «ERROR INTERNO / Se produjo un error interno inesperado. / Operación: Ejecución principal / Diagnóstico técnico: logs/error_interno_….txt» | Es un fallo del programa, no de tus archivos. El detalle queda en ese archivo de `logs/`: avisa, adjunta el archivo (puede incluir rutas de tu equipo) y di qué ruta y qué opciones elegiste. Si no sale la línea «Diagnóstico técnico», el archivo no se pudo guardar: copia las líneas de la terminal |
| Una generación tarda mucho | Es normal: Ollama y Wan no tienen tiempo límite. Espera o córtala con Ctrl+C |
| Falta una dependencia o un programa externo | [INSTALL.md](INSTALL.md) |

---

Copyright © 2026 Juan Bautista Galisteo Marqués.

AI Visual Composer es obra de Juan Bautista Galisteo Marqués, que lo creó y lo
mantiene.
