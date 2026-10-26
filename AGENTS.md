# AGENTS.md — Reglas comunes para agentes de IA

Válido para cualquier agente (Claude Code, Codex, Antigravity u otros). Aquí solo hay
reglas permanentes y comunes. El estado de trabajo no va aquí: ver §7.

**Idioma:** todos los agentes responden siempre en español (chat, informes, bitácoras
y resúmenes).

Cada agente tiene además sus reglas propias, que no repiten lo común:

- Si eres Claude, tus reglas propias están en `AGENT_AI/CLAUDE/AGENT.md`.
- Si eres Codex, lee `AGENT_AI/CODEX/AGENT.md` al empezar.
- Si eres Antigravity, lee `AGENT_AI/ANTIGRAVITY/AGENT.md` al empezar. Antigravity es
  **solo auditor en modo lectura**: no modifica, crea ni borra archivos fuera de
  `AGENT_AI/ANTIGRAVITY/REPORTS/` y no hace ninguna operación de Git que cambie algo.
  Sus reglas prevalecen sobre cualquier autorización de este archivo.

## 1. Protección del producto

Sin autorización expresa en la tarea, no modifiques código, arquitectura,
comportamiento en ejecución, configuración, perfiles, tests, workflows ni prompts,
y no hagas commit, push, pull, merge, reset ni tags.

Si una tarea autoriza cambios, mantenlos mínimos y dentro de lo pedido, y lista
cada archivo modificado.

## 2. Arquitectura guiada por datos (no negociable)

- El código implementa capacidades genéricas; la configuración declara entidades,
  familias, perfiles, variantes y valores.
- La estructura es el contexto:
  `config/profiles/<componente>/<formato>/[<familia>/]<perfil>.json`.
  Se descubre dinámicamente donde la arquitectura lo permite; Python no registra
  de antemano nombres de familias o perfiles futuros.
- Los IDs técnicos (`profile_id` y equivalentes) son identidad opaca: no se analizan
  (prefijos, sufijos, `split`, regex) para deducir comportamiento ni se construyen
  concatenando nombres.
- `display_name` y las etiquetas de terminal o menú son solo presentación; nunca
  deciden identidad, enrutado, resolución, carga ni comportamiento.
- Un perfil o familia nuevo que use capacidades existentes no requiere tocar Python.
- Una capacidad nueva se implementa de forma genérica y configurable,
  nunca como `if perfil == X`.
- Flujo correcto: estructura/configuración → descubrimiento → identidad técnica →
  validación → capacidades → ejecución.
- Componentes fijos: GUION, IMAGEN, VIDEO, STUDIO.
- `OperationalProfileKey(component, format, profile_id)` y
  `SubtitleProfileKey(component, format, family, profile_id)` son dominios
  separados; no se fusionan.
- Fixtures de test con nombres técnicos (`test_family`, `dummy_profile`), nunca
  nombres que parezcan de producto.
- El acoplamiento nominal heredado se mantiene solo donde esté documentado como
  compatibilidad; no se copia ni se extiende.
- Al tocar identidad, descubrimiento, selectores, cargadores, registros, enrutado
  o integración en ejecución, comprueba que se cumple esta sección y avisa de
  cualquier incumplimiento que encuentres.

## 3. Validación proporcional

- Cambio acotado: tests focales del ámbito + `compileall` del ámbito +
  `git diff --check` (+ validar JSON si se tocó JSON).
- Suite global (`python -m pytest tests -q`) solo al cerrar una fase, ante impacto
  transversal demostrado o si el propietario la pide; una sola vez, con la salida y
  el código de salida capturados en esa misma ejecución.
- No repetir suites por salida truncada, para obtener otro formato o para recuperar
  el código de salida.

## 4. Documentación de cierre

- **Bitácora** (`AGENT_AI/<AGENTE>/BITACORA.md`): entrada de ≤ 15 líneas solo si la
  tarea produjo cambios, hallazgos o decisiones. Solo se añade al final; nunca se
  borra ni se reescribe.
- **Estado** (`AGENT_AI/ESTADO.md`): se actualiza al cerrar cada tarea con cambios
  (rama, línea activa, último resultado, decisiones pendientes, siguiente paso).
- **Puente** (`AGENT_AI/<AGENTE>/PUENTE.md`): solo cuando el propietario lo pida o
  al cerrar un lote. Se regenera desde cero.
- **Informes**: un resultado largo va a `AGENT_AI/<AGENTE>/REPORTS/` o al documento
  vivo de su línea en `AGENT_AI/TRABAJO/`; las demás piezas lo enlazan, no lo copian.
- Las preguntas triviales no requieren cierre.
- Si el prompt del propietario indica otra cosa, prevalece el propietario.

## 5. Privacidad

`AGENT_AI/` es privado y está fuera de Git. No se publica ni se incluye en releases.
Si detectas un archivo de `AGENT_AI/` versionado, avísalo sin alterar Git.

## 6. Estructura de `AGENT_AI/`

```text
AGENT_AI/
  ESTADO.md            estado común y siguiente paso
  TRABAJO/             documentos vivos de cada línea de trabajo (comunes)
  <AGENTE>/            CLAUDE, CODEX…: misma estructura en todos
    AGENT.md           reglas propias del agente
    BITACORA.md        historia del agente
    PUENTE.md          resultado para el propietario u otro asistente
    REPORTS/           informes del agente
  ANTIGRAVITY/         auditor de reserva, solo lectura
    AGENT.md           sus reglas
    REPORTS/           sus informes (sin bitácora ni puente)
```

## 7. Dónde está el estado

- Estado actual y siguiente paso: `AGENT_AI/ESTADO.md` (léelo al empezar).
- Líneas de trabajo: `AGENT_AI/TRABAJO/<linea>.md`.
- Historia: `AGENT_AI/<AGENTE>/BITACORA.md` (buscar, no leer entera).
- Cómo redactar prompts: `PROMPTS.md`.

## 8. Comportamientos intencionados (no cambiar sin preguntar)

Parecen mejorables, pero son así a propósito. No se cambian ni se proponen como
mejora sin preguntar antes al propietario.

- **Ollama y WAN no tienen tiempo límite (timeout).** Con límites como 180 s se
  cortaban generaciones válidas y daba fallos. No añadas timeouts a esas llamadas.
- **STUDIO, SRT + VIDEO usa siempre el SRT tal cual (ORIGINAL, sin Whisper).** Si
  SOLO VIDEO transcribe mal una palabra, el propietario corrige el SRT y usa
  SRT + VIDEO. No es una opción que haya que ofrecer ni "mejorar" (decisión P1 de
  `AGENT_AI/TRABAJO/LIMPIEZA.md` §3.1).
