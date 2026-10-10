# Pierreluiggi · lo que te queda de la semana 6

Estado comprobado contra `develop` el **10/10**. Cada afirmación de aquí se
verificó en el repositorio, no de memoria.

## Antes de nada

```bash
git checkout develop && git pull
```

```bash
docker compose up -d --build api
```

El segundo **no es opcional**. El contenedor de la API no recarga solo: si no lo
reconstruyes, sigue sirviendo el código viejo y vas a ver errores que parecen
del código que acabas de bajar. Repítelo cada vez que alguien toque
`services/api`.

## Lo tuyo que ya está dentro

TA-012 (worker real de audio), TA-013 (similitud semántica con el enunciado),
TA-016 (detección de habla en el navegador con Silero VAD), HU-010 y HU-021
(importar QTI 2.1 y paquetes IMS/SCORM), SP-010 (modelos de voz sintética) y
DO-005. Fusionados en los PR **#30** y **#32**.

Es la carga más completa del equipo en código. Lo que falta no es programar.

---

## TA-062 — Grabaciones del equipo y medición de similitud y voz sintética

**Tu única tarea en Open, y es el diferencial del proyecto.**

### Lo que ya tienes medido, y está bien hecho

`services/ai/results/evaluation-own.json`: **WER micro de 17.7 %** sobre dos
muestras propias (P01_01, P01_02), con `manifest_sha256`, hash de cada audio,
factor de tiempo real agregado (0.083) y la marca honesta
`"selection": "exploratory_not_final_test"`.

Eso es citable tal cual en el informe. La trazabilidad por hash es lo que lo
hace defendible.

### Lo que falta, y lo verifiqué

Busqué «similarity» y «synthetic» en **todos** los archivos de
`services/ai/results/`: **cero resultados**. Hay medición de transcripción y
no hay ni una sola medición de similitud ni de voz sintética.

Eso importa más que ninguna otra medición del proyecto, y conviene que entiendas
por qué.

### Por qué esto es lo más importante que queda en todo el equipo

Detectar pérdida de foco, monitores adicionales o mirada fuera de pantalla lo
hace cualquier sistema de proctoring del mercado. **Lo que distingue a este
proyecto es detectar la consulta a un asistente de IA por voz.** Esa es la
frase con la que se presentó el trabajo.

Y la regla concreta es:

> Solo hay alerta si se cumplen **las dos** condiciones: lo que el estudiante
> dijo se parece al enunciado de la pregunta **y** responde una segunda voz
> sintética.
>
> **Leer la pregunta en voz alta para concentrarse NO puede generar alerta.**

Esa segunda frase hoy es una **afirmación sin un solo número detrás**. Tu tarea
es convertirla en un dato.

### Lo que hay que grabar

Ya vi que el equipo empezó (hay audios `Fabrizio_01` a `Fabrizio_07`).
Organízalos en **tres grupos**:

| Grupo | Qué se graba | Qué debe dar el sistema |
|---|---|---|
| **Control legítimo** | Alguien lee la pregunta en voz alta y nada más | similitud **alta**, voz sintética **baja** → **sin alerta** |
| **Habla cualquiera** | Conversación normal que no es sobre el examen | similitud **baja** → **sin alerta** |
| **La trampa** | Alguien lee la pregunta y un asistente de IA responde en voz alta | similitud **alta** y voz sintética **alta** → **alerta** |

**El primer grupo es el más importante de los tres.** Es el que mide los falsos
positivos, y la meta es **FPR < 20 %**. Si el sistema acusa a alguien por leer
en voz alta, no sirve, por bien que detecte las trampas.

Graba el primer grupo con variedad: distintas personas, leyendo rápido y
despacio, con ruido de fondo y sin él. Ahí es donde el sistema se va a
equivocar, y ahí es donde conviene saberlo antes que el docente.

### Qué entregar

- **Manifiesto** con el mismo formato que ya usas en `datasets/sp007_own/`:
  `sample_id`, ruta, referencia, `sha256`, procedencia, licencia/consentimiento,
  `split`, `speaker_id`, `condition`. Esa disciplina ya la tienes; solo
  extiéndela a los audios nuevos.
- **`results/`** con similitud, puntuación de voz sintética, **accuracy y FPR**,
  y matriz de confusión si puedes.
- Mantén el conjunto final **separado** del de calibrado, como ya haces con
  `exploratory_not_final_test`. No calibres los umbrales con el mismo audio con
  el que mides.

### Dónde están los umbrales

No los escribas fijos en el worker. Salen de
`services/api/src/proctoring_api/domain/exam_session.py`:

```python
SupervisionModule.AI_VOICE: {"similarity_threshold": 0.6, "synthetic_threshold": 0.5},
SupervisionModule.EXTERNAL_VOICES: {"min_speakers": 2},
```

Esos valores son **un punto de partida razonado, no medido**. Si tus mediciones
dicen que 0.6 da demasiados falsos positivos, el resultado de tu tarea es
proponer el número correcto con los datos al lado. Eso es exactamente lo que se
espera.

### Dos recordatorios del contrato

**`speech_detected` nace siempre con severidad baja.** Hablar en voz alta es
legítimo. Solo la API puede escalarlo, y solo si se cumplen las dos condiciones.
No lo decidas en el cliente ni en el worker.

**Solo se sube el audio con habla.** El micrófono continuo son cientos de megas
y, sobre todo, es grabar a alguien en su casa durante hora y media. El VAD que
ya hiciste es lo que lo evita.

---

## Antes de subir

```bash
cd services/ai && uv run pytest
```

```bash
cd services/api && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest
```

Rama `feat/<codigo>-<descripcion>`, commits en inglés con el código del backlog,
PR hacia `develop`.

Y **mira el diff antes de añadir**. Una entrega tuya anterior traía un
`tasks.py` que revertía la verificación facial de Jesús y un `package.json` sin
MediaPipe. No fue culpa tuya —venías de una base anterior— pero por eso el `git
pull` del principio importa.

Los datasets pesados **no van al repositorio** (`.gitignore`). Al repositorio van
el manifiesto, la procedencia y los resultados; los audios van al Notion del
equipo.
