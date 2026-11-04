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

`project_tree.txt` representa la estructura arquitectónica prevista del proyecto en el momento de su ejecución.

## Funcionamiento

La utilidad recorre el proyecto de forma recursiva utilizando exclusivamente la librería estándar de Python.

Reglas principales:

- Ordena alfabéticamente.
- Muestra siempre primero las carpetas.
- Muestra después los archivos.
- Usa formato de árbol UTF-8.
- Detecta automáticamente la raíz desde el directorio actual de ejecución.
- Es compatible con Windows.
- No usa dependencias externas.
- No llama a comandos del sistema.
- Escribe `project_tree.txt` en UTF-8.

Carpetas colapsadas:

- `.venv`.
- `cache`.
- `data`.
- `models`.
- `node_modules`.
- `temp`.
- `venv`.
- `assets/music`.
- `assets/videos`.
- carpetas que contienen únicamente recursos multimedia o binarios conocidos.

Carpetas omitidas completamente:

- `.agents`.
- `.git`.
- `.mypy_cache`.
- `.pytest_cache`.
- `AGENT_AI`.
- `CODEX`.
- `ComfyUI`.
- `input`.
- `logs`.
- `output`.
- cualquier carpeta `backup_*`.
- `__pycache__` y cualquier carpeta cuyo nombre contenga `pycache`.

Carpetas de assets no expandidas:

- `assets/music`.
- `assets/videos`.
- cualquier contenido descendiente de ellas queda fuera del árbol porque no aporta valor arquitectónico.

Carpetas de recursos binarios:

- Si una carpeta contiene únicamente archivos multimedia o recursos binarios conocidos, se muestra solo la carpeta y no se expande.
- Esto evita documentar inventarios extensos de audio, imagen, vídeo o fuentes.

## Cuando ejecutarlo

Ejecutar `python tools/generate_project_tree.py`:

- antes de crear un Punto Oficial de Restauración;
- cuando cambie la arquitectura;
- cuando se añadan módulos importantes;
- cuando se reorganice el proyecto;
- antes de checkpoints donde sea necesario congelar una fotografía estructural del repositorio.
