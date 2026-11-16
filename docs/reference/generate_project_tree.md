# Generate Project Tree

## Objetivo

`generate_project_tree.py` genera una fotografía documental de la arquitectura del proyecto AI Visual Composer.

Su salida no pretende ser un inventario completo de recursos, modelos, cachés, memoria privada o artefactos locales. El objetivo es producir un árbol limpio, estable y legible para documentación, auditorías y Puntos Oficiales de Restauración.

## Ubicación

El archivo está en la carpeta `tools/`:

```text
tools/generate_project_tree.py
```

Debe ejecutarse también desde la raíz del proyecto.

## Ejecución

```bash
python tools/generate_project_tree.py
```

## Resultado

La utilidad genera el archivo:

```text
project_tree.txt
```

en la raíz del proyecto.

`project_tree.txt` representa la estructura versionada del proyecto en el momento de su ejecución. El propio archivo está fuera de Git.

## Funcionamiento

La utilidad parte de la lista de archivos que versiona Git (`git ls-files`), de modo que el árbol contiene exactamente lo que hay en el repositorio y nada de lo ignorado o local (`validation/`, `.claude/`, `.env`, `models/`, `project_tree.txt`, etc.). Sobre esa lista construye el árbol en memoria y aplica las reglas de presentación.

Reglas principales:

- Ordena alfabéticamente, sin distinguir mayúsculas.
- Muestra siempre primero las carpetas y después los archivos.
- Usa formato de árbol UTF-8.
- Toma como raíz el directorio actual de ejecución, que debe ser la raíz del repositorio.
- Es compatible con Windows.
- Solo usa la librería estándar de Python y necesita `git` en el PATH.
- Si Git no está disponible, o la carpeta no es un repositorio, termina con un mensaje de error en español y no escribe nada.
- Escribe `project_tree.txt` en UTF-8.

Al terminar imprime: carpetas recorridas, carpetas excluidas, archivos documentados y archivos versionados no listados (los de carpetas colapsadas u omitidas). Documentados + no listados = número de líneas de `git ls-files`.

Carpetas colapsadas (se muestra la carpeta, no su contenido):

- `.venv`, `cache`, `data`, `models`, `node_modules`, `temp`, `venv`.
- `assets/music` y `assets/videos`.
- cualquier carpeta `backup_*`.
- carpetas que contienen únicamente recursos multimedia o binarios conocidos (audio, imagen, vídeo, fuentes), para no documentar inventarios extensos.

Carpetas omitidas completamente:

- `.agents`, `.git`, `.mypy_cache`, `.pytest_cache`, `AGENT_AI`, `CODEX`, `ComfyUI`, `input`, `logs`, `output`.
- cualquier carpeta `backup_*`.
- `__pycache__` y cualquier carpeta cuyo nombre contenga `pycache`.

## Cuando ejecutarlo

Ejecutar `python tools/generate_project_tree.py`:

- antes de crear un Punto Oficial de Restauración;
- cuando cambie la arquitectura;
- cuando se añadan módulos importantes;
- cuando se reorganice el proyecto;
- antes de checkpoints donde sea necesario congelar una fotografía estructural del repositorio.
