# Pierreluiggi — IA de audio

**Tu área:** detección de habla, transcripción, similitud con el enunciado, voz
sintética e importación QTI.
**SPEC:** 007 (transcripción, ya medida), 008 (IA por voz), 003 (QTI).

Lee antes [`docs/guias/README.md`](README.md).

---

## Lo que ya tienes hecho

| Qué | Dónde | Resultado |
|---|---|---|
| Transcripción en español | `services/ai/spikes/transcribe.py` | WER 16,0 % (`small`, MediaSpeech) y 7,6 % (audios propios) |
| Cálculo de WER | `services/ai/spikes/metrics.py` | conserva tildes y ñ |
| Evaluación con hashes | `services/ai/spikes/evaluate.py` | manifiestos y procedencia versionados |

**Tu diferencial es lo que falta**: comparar lo que se dice con el enunciado y
detectar una segunda voz sintética.

---

## Lo que ya está hecho por ti

`services/ai/tasks.py` tiene el esqueleto con los `TODO` en su sitio, y la API ya
expone el contrato. **No tienes que tocar la base de datos ni crear alertas.**

El reparto es:

| Quién | Qué hace |
|---|---|
| tu worker | **mide**: transcribe, calcula similitud, puntúa la voz |
| la API | **decide**: aplica los umbrales de la sesión y crea la alerta |

La regla que define el proyecto ya está escrita y probada en la API:

> Se alerta **solo** si lo dicho se parece al enunciado **y** hay una segunda voz
> sintética.

Leer la pregunta en voz alta puntúa altísimo en la primera condición y **no debe
alertar nunca**. Hay una prueba que lo fija. No intentes decidirlo en el worker.

---

## Tarea P1 — Similitud con el enunciado (4 h)

**Rama:** `feat/SPEC-008-similitud`
**Archivo nuevo:** `services/ai/spikes/similarity.py`

Un spike que reciba dos textos y devuelva una similitud entre 0 y 1.

Candidato a evaluar: `sentence-transformers` con un modelo multilingüe
(`paraphrase-multilingual-MiniLM-L12-v2` es pequeño y suele bastar). **Mídelo
antes de comprometerte**: si no cabe en el presupuesto de tiempo, hay más chicos.

El dataset importa más que el modelo. Necesitas **≥ 60 pares** etiquetados en tres
grupos:

| Grupo | Ejemplo | Debe |
|---|---|---|
| **Lee la pregunta en voz alta** | "¿Qué garantiza Row Level Security?" | puntuar **alto** y aun así **no** alertar (falta la voz sintética) |
| **Le dicta la pregunta a un asistente** | "Oye, dime qué garantiza Row Level Security en PostgreSQL" | puntuar alto |
| **Habla de otra cosa** | "ya casi termino", "qué calor hace" | puntuar bajo |

Entrega: **curva ROC**, el umbral que recomiendas (hoy está en 0,6) y el **FPR a
ese umbral**, en `services/ai/results/similarity.json`.

> El primer grupo es el que importa. Si tu umbral no separa "leer la pregunta" de
> "dictársela a una IA", la similitud sola no sirve — y por eso hacen falta las
> dos condiciones.

---

## Tarea P2 — Detector de voz sintética (6 h)

**Rama:** `feat/SPEC-008-voz-sintetica`
**Archivo nuevo:** `services/ai/spikes/synthetic_voice.py`

Lo más difícil y lo más propio del proyecto.

**El dataset:**

- **Voz real**: Common Voice en español, más grabaciones del equipo.
- **Voz sintética**: generada con **al menos 3 motores distintos** (Piper, XTTS,
  edge-tts son candidatos). Usa dos para ajustar y **guarda el tercero sin
  tocar**: evaluar con un motor que no viste es lo único que dice si generaliza.

**El escenario realista:** la voz de la IA sale por los **parlantes** del equipo y
el micrófono la capta **mezclada con la del estudiante**, con el eco de la
habitación. Graba así, no solo audios limpios. Un detector entrenado con audio
limpio de TTS funcionará perfecto en tu máquina y fallará en un examen.

**Candidatos a evaluar:** embeddings de wav2vec2/XLS-R más una regresión
logística (sencillo, rápido), o un modelo ya entrenado tipo AASIST sin
reentrenar, para comparar.

Entrega en `services/ai/results/synthetic_voice.json`: **EER, accuracy y FPR**,
**más el resultado con el motor TTS no visto**, que es el número que vale.

---

## Tarea P3 — El worker real (8 h)

**Rama:** `feat/SPEC-008-worker-audio`
**Archivo:** `services/ai/tasks.py`, función `analyze_audio`

Ya tiene la estructura. Rellena los cuatro `TODO`:

```python
job = _get(f"/api/v1/internal/audio-jobs/{event_id}")
# job["audio_path"], job["audio_bucket"]   -> descargar de Supabase Storage
# job["question_statement"]                -> con esto comparas
# job["similarity_threshold"]              -> para registrarlo, no para decidir
```

y al final devuelves lo medido:

```python
return _post(f"/api/v1/internal/audio-jobs/{event_id}/result", {
    "transcript": transcript,
    "similarity": similarity,
    "synthetic_voice_score": score,
    "processing_ms": int((time.monotonic() - comenzado) * 1000),
    "model_versions": {"asr": "faster-whisper-small", "sim": "...", "tts_det": "..."},
})
```

La respuesta trae `alerted`: lo que **la API** decidió.

Dos cosas:

- Si `question_statement` es `None` (la pregunta ya no existe), no hay con qué
  comparar: deja `similarity` en `None`. La API no alertará, que es lo correcto.
- **El presupuesto es 10 s de punta a punta.** Con `small`, un fragmento de 10 s
  cuesta ~2,3 s, así que te quedan ~7,7 s. Mide `processing_ms` completo, no por
  partes: ese es el número que dice si la meta se cumple.

Para probar sin montar nada:

```bash
docker compose up -d api redis
```

```bash
cd services/ai && INTERNAL_API_TOKEN=<el del .env> PROCTORING_API_URL=http://localhost:8000 uv run python -c "import tasks; print(tasks.analyze_audio('<event_id>'))"
```

**Terminado cuando:** con un evento real de habla, el análisis queda en
`audio_analyses` y, con las dos condiciones, aparece una alerta en la pantalla
del docente. Y hay una prueba de que leer en voz alta **no** alerta.

---

## Tarea P4 — Detección de habla en el navegador (6 h)

**Rama:** `feat/SPEC-008-vad`
**Archivo:** `apps/web/src/supervision/detectores/voz.ts`

Es el único detector que **no basta con emitir**: hay que subir el fragmento o el
worker no tendrá nada que transcribir.

1. Silero VAD con `onnxruntime-web` dice cuándo hay voz → `activa: true`
2. Un `MediaRecorder` sobre la pista de audio graba **solo esos tramos**
3. Al cerrarse la condición:
   - `POST /api/v1/evidence/upload-url` con `kind: "audio"` y `extension: "webm"`
   - subir el fragmento **directo a Storage** con la URL firmada
   - mandar el evento con `evidence_path` = la ruta devuelta

El audio **nunca pasa por la API** ([ADR-0004](../adr/0004-deteccion-liviana-cliente-sin-video-continuo.md)).
Y solo los tramos **con habla**: grabar el micrófono entero son cientos de megas
y, sobre todo, es grabar a alguien en su casa durante hora y media.

Lee `apps/web/src/supervision/README.md`: la cámara, la histéresis y el envío ya
están resueltos.

---

## Tarea P5 — Importación QTI (6 h)

**Rama:** `feat/SPEC-003-importar-qti`
**Archivo nuevo:** `services/ai/spikes/qti_import.py` (función pura, con fixtures)

**Esta no depende de nadie y se puede hacer hoy.** El profesor la pidió
explícitamente, y es determinista: no hay modelos ni incertidumbre.

Una función que reciba el XML de un QTI 2.1 (o el `imsmanifest.xml` de un paquete
SCORM que lo contenga) y devuelva una lista de preguntas con esta forma:

```python
{
  "question_type": "multiple_choice",   # o true_false, numeric, fill_blank, essay
  "statement": "¿Qué garantiza Row Level Security?",
  "points": "2",
  "options": [{"option_text": "Filtra filas", "is_correct": True}, ...],
  "correct_numeric_answer": None,
  "correct_text_answer": None,
}
```

Es exactamente lo que acepta `POST /api/v1/sessions/{id}/questions` hoy, y lo que
aceptará el banco de preguntas. Héctor lo expone como endpoint; tú entregas la
función y sus pruebas.

Qué cubrir:

| Tipo QTI | Nuestro tipo |
|---|---|
| `choiceInteraction` con `maxChoices=1` | `multiple_choice` |
| `choiceInteraction` de 2 opciones V/F | `true_false` |
| `textEntryInteraction` | `fill_blank` |
| numérico con tolerancia | `numeric` |
| `extendedTextInteraction` | `essay` |

Guarda 3 o 4 archivos QTI de ejemplo en `services/ai/tests/fixtures/qti/` (son
texto, sí van al repositorio) y una prueba por tipo. **Un QTI con algo que no
entiendes no debe reventar**: salta esa pregunta y deja constancia, para que
importar 40 preguntas no falle por una.

---

## Orden recomendado

```
P5 (QTI)        ──► no depende de nada, se puede hacer hoy
P1 (similitud)  ──┐
P2 (sintética)  ──┴──► P3 (worker real)
P4 (VAD)        ──► necesita que P3 exista para probarse entero
```
