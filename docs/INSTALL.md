# Instalación de AI Visual Composer

Este documento explica la instalación y configuración inicial del entorno
necesario para ejecutar AI Visual Composer.

Para el uso normal una vez instalado, ver [START.md](START.md).

Otros documentos:

| Para saber… | Documento |
|---|---|
| Cómo se usa el programa (menús, carpetas de entrada, resultados) | [START.md](START.md) |
| Cómo está construido por dentro | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Qué familias y perfiles de subtítulos hay y cómo se ven | [SUBTITLES.md](SUBTITLES.md) |
| Cómo se genera la voz y cuánto dura un guion | [VOICEOVER.md](VOICEOVER.md) |

---

## 1. Requisitos del sistema

AI Visual Composer está pensado para ejecutarse en local.

Entorno recomendado:

```text
Sistema operativo: Windows
Python: entorno 3.x moderno
GPU: NVIDIA
Aceleración de GPU: entorno compatible con CUDA
```

El sistema necesita además suficiente:

- VRAM de GPU para la generación local de imagen e I2V;
- RAM del sistema;
- espacio en disco para los modelos de IA;
- espacio en disco para el contenido audiovisual generado.

Los requisitos de hardware reales dependen de los modelos y los perfiles de
generación que se usen.

---

## 2. Componentes necesarios

AI Visual Composer se apoya en los siguientes componentes externos principales:

```text
Python
FFmpeg
Ollama
ComfyUI
Piper ONNX
OpenAI Whisper
Modelos Flux
Modelos Wan I2V
```

Cada componente cumple una función distinta: no son dependencias
intercambiables entre sí.

---

## 3. Entorno Python

Abre una terminal en la raíz del proyecto.

Comprueba Python:

```powershell
python --version
```

Crea un entorno virtual:

```powershell
python -m venv .venv
```

Actívalo:

```powershell
.\.venv\Scripts\Activate.ps1
```

Actualiza pip:

```powershell
python -m pip install --upgrade pip
```

Instala las dependencias del proyecto:

```powershell
pip install -r requirements.txt
```

`requirements.txt` lista solo los paquetes de Python que usa directamente AI
Visual Composer:

- `requests`: peticiones HTTP al servicio local de Ollama;
- `Pillow`: métricas de fuente para el renderizado de subtítulos;
- `nudenet==3.4.2` y `onnxruntime==1.30.0`: control de calidad de imagen
  (filtro de desnudos); `onnxruntime` es también el runtime ONNX que necesita
  Piper;
- `piper-tts==1.8.0`: voz local (ver Piper ONNX);
- `openai-whisper`: transcripción y tiempos de subtítulos, invocado como el
  comando `whisper` (ver OpenAI Whisper);
- `pytest`: tests automáticos.

El resto de librerías se instalan como dependencias de estas.

Opcional, para desarrollo: `pre-commit` comprueba ruff y los formatos de archivo antes de cada commit (sin reescribir nada); se instala con `pip install pre-commit` y `pre-commit install`, y no forma parte de `requirements.txt`.

---

## 4. FFmpeg

AI Visual Composer usa FFmpeg para el procesado audiovisual y la composición
final.

FFmpeg se usa, entre otras, para:

- procesado de audio;
- preparación temporal de vídeo;
- movimiento;
- transiciones;
- overlays;
- efectos visuales;
- fundidos;
- subtítulos;
- codificación final del vídeo.

Comprueba la instalación:

```powershell
ffmpeg -version
```

Comprueba también FFprobe:

```powershell
ffprobe -version
```

Los dos comandos deben estar disponibles desde la terminal.

Se necesita FFmpeg 7.0 o posterior: el montaje de STUDIO usa la opción
`-/filter_complex <archivo>`, que no existe en versiones anteriores.

Si no se reconocen, instala FFmpeg y añade su carpeta de ejecutables al `PATH`
del sistema.

---

## 5. Ollama

AI Visual Composer usa Ollama para la ejecución local de modelos de lenguaje.

Instala Ollama para Windows con la distribución oficial.

Tras instalarlo, comprueba:

```powershell
ollama --version
```

Comprueba los modelos instalados:

```powershell
ollama list
```

La configuración actual del proyecto (`config/ai.json`) usa:

```text
qwen3:14b
```

Si el modelo configurado no está instalado:

```powershell
ollama pull qwen3:14b
```

El modelo configurado en AI Visual Composer y el modelo instalado en Ollama
tienen que coincidir. El guion puede usar otro modelo (`script.model`): también
tiene que estar instalado. Qué significa cada clave de `config/ai.json`:
[ARCHITECTURE.md §19](ARCHITECTURE.md#19-perfiles-y-configuración).

Con `keep_alive` a `0` (el valor del proyecto), Ollama descarga el modelo de la
GPU en cuanto responde, para que Whisper y ComfyUI la tengan entera.

Para el uso normal basta con abrir la aplicación de Ollama para Windows ya
instalada.

También se puede arrancar manualmente desde una terminal:

```powershell
ollama serve
```

Ollama no tiene tiempo límite de respuesta en AI Visual Composer: una
generación puede tardar sin que el programa la corte.

Ver [START.md](START.md) para el procedimiento de arranque normal.

---

## 6. ComfyUI

AI Visual Composer usa ComfyUI como runtime local de generación para:

```text
Generación de imagen
Generación de vídeo I2V
```

ComfyUI se mantiene como runtime externo local y no forma parte del
repositorio público.

La estructura local esperada del proyecto es:

```text
AI Visual Composer/
│
├── app/
├── config/
├── assets/
├── main.py
│
└── ComfyUI/
```

La carpeta `ComfyUI/` está excluida de Git.

Instala y configura ComfyUI aparte, dentro del entorno local del proyecto.

El comando normal de arranque en Windows con NVIDIA es:

```powershell
cd ComfyUI
.\run_nvidia_gpu.bat
```

El endpoint local esperado es:

```text
http://127.0.0.1:8188
```

Comprueba que ComfyUI arranca correctamente antes de intentar una generación
real de imagen o de I2V.

---

## 7. Generación de imagen con Flux

AI Visual Composer usa Flux a través de ComfyUI para la generación local de
imagen. El workflow configurado está en `config/comfyui_flux_workflow_api.json`.

Los modelos Flux necesarios deben instalarse en las carpetas de modelos
locales de ComfyUI que correspondan.

Responsabilidades típicas de los modelos:

```text
Modelo Flux
Codificador de texto
VAE
```

Los archivos de modelo quedan excluidos del repositorio público por su
tamaño y por sus condiciones de distribución externa.

Extensiones habituales de estos archivos:

```text
*.safetensors
*.ckpt
*.pt
*.pth
```

No subas archivos de modelo locales al repositorio público.

La configuración de AI Visual Composer y la instalación real de ComfyUI
deben apuntar a archivos de modelo compatibles entre sí.

### Control de calidad de imagen (NudeNet)

El control de calidad de las imágenes generadas incluye siempre un filtro de
desnudos (NudeNet), con independencia del perfil. Espera el modelo ONNX en:

```text
models/visual_safety/nudenet-320n.onnx
```

---

## 8. Wan I2V

AI Visual Composer usa Wan a través de ComfyUI para la generación de vídeo
Imagen-a-Vídeo (I2V). El workflow configurado está en
`config/comfyui_wan22_ti2v_i2v_workflow_api.json`.

El workflow configurado se mantiene dentro de la configuración del proyecto.

El modelo externo correspondiente debe instalarse en local, en la carpeta de
modelos de ComfyUI que corresponda.

Los archivos del modelo Wan no se guardan en el repositorio público.

Antes de ejecutar un flujo completo de Vídeo, comprueba que:

```text
ComfyUI arranca correctamente
El modelo Wan está disponible
Los nodos necesarios están disponibles
El workflow configurado se carga correctamente
La generación I2V se puede ejecutar
```

Wan tampoco tiene tiempo límite de respuesta en AI Visual Composer.

---

## 9. Workflows de ComfyUI

AI Visual Composer se comunica con ComfyUI a través de workflows de API
configurados.

La configuración relevante de los workflows se mantiene bajo:

```text
config/
```

Los workflows definen el grafo de generación que espera la aplicación.

No modifiques identificadores de nodo, referencias de modelo ni la estructura
del grafo sin entender cómo AI Visual Composer traduce sus parámetros en
tiempo de ejecución a ese workflow.

Que un workflow se abra correctamente en ComfyUI no demuestra por sí solo que
la integración con la aplicación siga siendo compatible.

La integración real debe comprobarse a través de AI Visual Composer.

---

## 10. Piper ONNX

AI Visual Composer usa Piper ONNX como proveedor de voz local declarativo.
Se instala a través de `requirements.txt` como `piper-tts==1.8.0`.

El proveedor necesita los siguientes recursos locales, provistos de forma
explícita:

```text
models/audio/piper/es_ES_davefx/es_ES-davefx-medium.onnx
models/audio/piper/es_ES_carlfm/es_ES-carlfm-x_low.onnx
```

El runtime comprueba que existen y son válidos antes de cargar el proveedor;
no los descarga durante la síntesis. El catálogo compartido ofrece hoy
Davefx y Carlfm a través de `backend_key="piper_onnx"`.

La síntesis de voz se resuelve con el límite técnico:

```text
Configuración declarativa de voz
→ backend_key
→ TtsBackendRegistry
→ proveedor Piper
→ VoiceBuilder
```

La generación de voz debe validarse finalmente con una ejecución real de AI
Visual Composer.

---

## 11. OpenAI Whisper

AI Visual Composer usa OpenAI Whisper para la transcripción y los tiempos de
los subtítulos, invocado como el comando `whisper`.

Whisper debe estar disponible en el entorno de Python que use AI Visual
Composer.

Comprueba:

```powershell
whisper --help
```

Si Whisper está bien instalado, el comando muestra sus opciones disponibles.

Whisper depende de FFmpeg, así que FFmpeg también debe estar disponible en el
`PATH` del sistema.

---

## 12. Entorno de referencia validado en Windows (Triton)

El entorno de Windows validado usa `triton-windows` para evitar los avisos de
Whisper sobre el fallback de Triton cuando PyTorch con CUDA ya funciona.

Instala el paquete de Triton para Windows compatible con:

```powershell
python -m pip install -U "triton-windows>=3.7,<3.8"
```

Entorno de referencia validado:

```text
Python: 3.13.12
PyTorch: 2.12.0.dev20260408+cu128
Runtime CUDA de PyTorch: 12.8
CUDA disponible: True
GPU: NVIDIA GeForce RTX 5070 Laptop GPU
triton-windows: 3.7.1.post27
Versión de Triton importada: 3.7.1
```

En este entorno validado, instalar `triton-windows` quitó los avisos de
Whisper sobre el fallo al lanzar el kernel de Triton y su fallback a las
implementaciones más lentas de mediana y DTW.

No fue necesaria una instalación completa del CUDA Toolkit porque PyTorch ya
traía un runtime de CUDA funcional en este entorno.

Estas versiones describen el entorno de referencia validado en Windows. No
son un requisito universal del proyecto.

---

## 13. Assets del proyecto

AI Visual Composer usa los assets locales del proyecto bajo:

```text
assets/
```

Con el proyecto solo vienen las fuentes Anton y Oswald (SIL OFL). La
música, los overlays, los efectos visuales y las fuentes Gotham Narrow Bold
y Uni Sans Heavy no se reparten: cada persona pone los suyos. Qué va en cada
carpeta, de dónde sacarlo y su licencia: [assets/README.md](../assets/README.md).

Si falta `Gotham Narrow Bold.otf` o `Uni Sans Heavy.otf`, los subtítulos
usan su fuente de reserva, Anton (declarada en `config/fonts.json`), y la
terminal avisa una vez por fuente; para usar la original, pon su archivo en
`assets/fonts/`.

Los assets locales quedan fuera de Git: la música, los overlays, los
efectos visuales, las dos fuentes de arriba y `assets/videos/intro_outro/`.

---

## 14. Configuración

La configuración del sistema se mantiene bajo:

```text
config/
```

Incluye el comportamiento guiado por perfiles y la configuración de
generación.

Familias de perfiles relevantes:

```text
config/profiles/guion/
config/profiles/imagen/
config/profiles/video/
config/profiles/studio/
```

Dentro de cada componente y formato, los perfiles de subtítulos se descubren
de forma genérica por familia (una carpeta por familia, por ejemplo
`estandar/` o `design/`); el código no tiene registrada de antemano una
lista cerrada de familias. El detalle de las familias y los perfiles está en
[SUBTITLES.md](SUBTITLES.md).

La configuración debe seguir siendo portable.

No introduzcas rutas absolutas personales en la configuración compartida.

Por ejemplo, evita una configuración pública como:

```text
C:\Users\USUARIO_PERSONAL\Desktop\...
```

La información específica de cada máquina debe quedar privada o fuera del
repositorio público.

---

## 15. Entradas y salidas locales

AI Visual Composer incluye cuatro archivos de entrada vacíos en tiempo de
ejecución:

```text
input/guion.txt
input/tema.txt
input/guion_imagen.txt
input/guion_video.txt
```

Estos archivos forman parte de la estructura pública del proyecto y están
incluidos al clonar o descargar el repositorio.

Están vacíos a propósito. El usuario escribe en ellos al preparar una
generación local.

Para que tus cambios locales en ellos no salgan en `git status` ni en los
commits, ejecuta `git update-index --skip-worktree input/guion.txt
input/guion_imagen.txt input/guion_video.txt input/tema.txt`; para deshacerlo,
usa `git update-index --no-skip-worktree` con los mismos archivos.

Los proyectos generados se guardan bajo:

```text
output/
```

El resultado generado en tiempo de ejecución queda fuera del repositorio
público.

No confundas `input/` y `output/`, que son estado local de usuario y
resultado que se puede regenerar o borrar, con la configuración versionada
del proyecto.

---

## 16. Estado privado de desarrollo

El estado privado de desarrollo y de los agentes de IA (`AGENT_AI/`,
`CODEX/`, `.agents/`, `.codex/`) se queda fuera del repositorio público; sus
reglas están en [AGENTS.md](../AGENTS.md).

---

## 17. Entorno y secretos

Los archivos de entorno locales quedan excluidos de Git:

```text
.env
.env.*
```

Se puede versionar una plantilla de ejemplo como:

```text
.env.example
```

Nunca subas al repositorio:

- contraseñas;
- claves de API;
- tokens de acceso;
- credenciales privadas;
- secretos específicos de una máquina.

Aunque AI Visual Composer está pensado sobre todo para ejecución local, la
higiene del repositorio debe seguir protegiendo las credenciales y el estado
privado de cada máquina.

---

## 18. Comprobación inicial

Tras instalar los componentes necesarios, comprueba el proyecto de Python
antes de hacer pruebas de generación reales, que son costosas.

### Compilación de Python

Ejecuta:

```powershell
python -m compileall app tests certification
```

El comando debe terminar sin errores de compilación.

### Tests automáticos

Ejecuta:

```powershell
python -m pytest
```

El número de tests puede cambiar con el proyecto.

Lo importante es que la suite actual termine sin fallos.

### Comprobación del diff de Git

En un checkout de desarrollo:

```powershell
git diff --check
```

Esto comprueba el diff actual en busca de errores de espacios en blanco.

No valida el comportamiento en tiempo de ejecución.

---

## 19. Verificación de los runtimes externos

Antes de la primera generación completa, comprueba cada runtime externo por
separado.

### Ollama

```powershell
ollama list
```

Confirma que el modelo de lenguaje configurado está disponible.

### ComfyUI

Arranca:

```powershell
cd ComfyUI
.\run_nvidia_gpu.bat
```

Confirma que el servidor local está disponible en:

```text
http://127.0.0.1:8188
```

### FFmpeg

```powershell
ffmpeg -version
ffprobe -version
```

### Whisper

```powershell
whisper --help
```

Hecho esto, vuelve a la raíz del proyecto antes de arrancar AI Visual
Composer.

---

## 20. Primera ejecución real

Que las dependencias se importen sin error no demuestra por sí solo que la
instalación esté completa.

Tras la instalación, haz una ejecución real controlada con AI Visual
Composer.

Esa ejecución debe confirmar las partes del sistema que necesite la ruta
elegida.

Según el flujo, puede incluir:

```text
Ollama
   ↓
Procesado del guion
   ↓
VoiceBuilder con Piper ONNX
   ↓
Whisper / tiempos de subtítulos
   ↓
Storyboard
   ↓
ComfyUI
   ↓
Flux
   ↓
Wan I2V
   ↓
FFmpeg
   ↓
Resultado final
```

No todos los modos de ejecución usan todas las etapas.

Si una etapa externa real no se ha ejecutado todavía, no la consideres
comprobada solo porque las comprobaciones estáticas o los tests automáticos
pasen.

---

## 21. Arranque normal

Una vez completadas la instalación y la comprobación inicial, el uso diario
no repite este procedimiento: el orden de arranque y los comandos están en
[START.md](START.md).

---

## 22. Lista de comprobación de la instalación

Antes de considerar lista la instalación local:

```text
[ ] Entorno de Python compatible disponible
[ ] Entorno virtual creado
[ ] requirements.txt instalado
[ ] FFmpeg disponible
[ ] FFprobe disponible
[ ] Ollama instalado
[ ] Modelo de Ollama configurado disponible
[ ] ComfyUI instalado en local
[ ] Requisitos de Flux disponibles en ComfyUI
[ ] Requisitos de Wan I2V disponibles en ComfyUI
[ ] Workflows de ComfyUI necesarios compatibles
[ ] Recursos de voz de Piper provistos en models/audio/piper/
[ ] Modelo de NudeNet provisto en models/visual_safety/
[ ] Whisper disponible
[ ] Assets propios en su sitio, si los usas (música, overlays; ver assets/README.md)
[ ] Configuración del proyecto revisada
[ ] La compilación de Python pasa
[ ] Los tests automáticos pasan
[ ] Los runtimes externos arrancan correctamente
[ ] Ejecución real controlada completada
```

---

## Instalación completa

Una vez instalado y comprobado el entorno, usa [START.md](START.md) para el
uso normal.

Mantén fuera del repositorio público los runtimes externos, los modelos
descargados, el resultado generado, los secretos, las rutas personales y el
estado privado de desarrollo.

---

Copyright © 2026 Juan Bautista Galisteo Marqués.

AI Visual Composer es obra de Juan Bautista Galisteo Marqués, que lo creó y
lo mantiene.
