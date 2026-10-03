# `services/ai` — Servicio de IA de audio (FastAPI + workers RQ)

**Responsable:** Zevallos Bocanegra, Pierreluiggi
**Backlog:** EN-007 / TA-00x (detección de asistente de IA por voz, importación QTI)

Esta carpeta está preparada pero **sin implementar**: es tuya. Lee [`CLAUDE.md`](../../CLAUDE.md)
§1 y §3 antes de empezar.

## Objetivo

Este es el **diferencial del proyecto**. Hay que detectar que el estudiante le está preguntando a
un asistente de IA por voz. La regla es estricta y tiene dos condiciones que deben cumplirse
**las dos**:

1. Lo que el estudiante dice en voz alta **se parece al enunciado de la pregunta en curso**
   (similitud semántica por encima del umbral).
2. Se detecta una **segunda voz sintética** respondiendo.

Si solo se cumple la primera, **no hay alerta**: leer en voz alta para concentrarse es legítimo y
contarlo como trampa es un falso positivo. La meta del módulo es FPR < 20 %.

Presupuesto de latencia: la alerta de IA por voz debe llegar al docente en **menos de 10 s** desde
que termina el fragmento de audio.

## Flujo

```
App del estudiante (Silero VAD en el renderer)
   detecta habla -> sube el fragmento a Storage con URL firmada
   -> POST /api/v1/events  { event_type: "speech_detected", question_id, evidence_path }
                                    |
                     API principal encola en Redis (cola "audio")
                                    v
              worker de este servicio: transcribe -> compara -> clasifica voz
                                    v
            escribe en audio_analyses y, si procede, en alerts
```

La API ya encola: el caso de uso `RegisterEvent` llama a `JobQueue.enqueue_audio_analysis(event_id)`
cuando el evento es `speech_detected`. Hay un `worker_stub.py` que prueba ese camino de punta a
punta; reemplázalo por el worker real.

## Estructura esperada (misma hexagonal que la API)

```
services/ai/
├── spikes/                      # EMPIEZA AQUI: scripts suetos, sin arquitectura
│   ├── transcribe.py
│   ├── similarity.py
│   ├── vad_pipeline.py
│   └── qti_import.py
├── src/proctoring_ai/
│   ├── domain/                  # reglas puras: umbrales, decisión de alerta
│   ├── application/{ports,use_cases}/
│   ├── adapters/{inbound/http,outbound}/
│   ├── config.py
│   └── main.py
├── worker_stub.py               # ya existe, es el esqueleto del worker
├── pyproject.toml
└── Dockerfile
```

## Spikes (esto es lo que el docente pidió como "tangible")

El profesor fue claro en la reunión del 03/10: no quiere solo investigación, quiere un script que
corra y demuestre el resultado. Cada spike es un archivo que se ejecuta solo y escribe su salida.

### `spikes/transcribe.py`

[`faster-whisper`](https://github.com/SYSTRAN/faster-whisper), modelo `small`, idioma español.

```python
from faster_whisper import WhisperModel
model = WhisperModel("small", device="cpu", compute_type="int8")
segments, info = model.transcribe("muestra.wav", language="es", vad_filter=True)
```

Mide y reporta el tiempo: con `small` en CPU debe transcribir 10 s de audio en pocos segundos.
Si no alcanza para el presupuesto de 10 s, prueba `base` y anótalo.

### `spikes/similarity.py`

[`sentence-transformers`](https://www.sbert.net/) con `paraphrase-multilingual-MiniLM-L12-v2`.

```python
from sentence_transformers import SentenceTransformer, util
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
emb = model.encode([enunciado, transcripcion])
score = util.cos_sim(emb[0], emb[1]).item()   # alerta si > 0.6
```

Prueba el umbral **0.6** con casos a favor y en contra: la pregunta leída literal, la pregunta
parafraseada, y conversación no relacionada. Escribe los números que obtengas; el umbral final sale
de esos datos, no de la intuición.

### `spikes/vad_pipeline.py`

[Silero VAD](https://github.com/snakers4/silero-vad) en continuo, con marcas de tiempo de inicio y
fin de cada tramo de habla. Esto es lo que corre en el cliente, así que mide el consumo de CPU: no
puede competir con MediaPipe por el procesador del estudiante.

### `spikes/qti_import.py`

QTI 2.1 (`.zip` con `imsmanifest.xml`) → JSON con la forma de las tablas `questions` y
`question_options` de [`CLAUDE.md`](../../CLAUDE.md) §7. Solo importación: **no** nos integramos con
Blackboard ni Canvas por LTI.

### Clasificador de voz sintética

Lo más difícil del módulo. Explora, en este orden:

1. Separación de locutores / diarización ligera: si en el mismo fragmento hay **dos** locutores,
   ya es una señal fuerte.
2. Un clasificador de antispoofing de audio preentrenado (busca modelos de deepfake de voz en
   Hugging Face con licencia permisiva).
3. Si nada funciona a tiempo, deja el `synthetic_score` en el evento y haz que la decisión final
   dependa solo de la similitud + presencia de segundo locutor, y **documenta esa limitación**.

## Qué se versiona y qué no

Los modelos y el audio **no entran al repositorio**: pesan y el `.gitignore` los bloquea. Pero el
**manifiesto, la procedencia y los resultados sí**, porque son texto de unos pocos kilobytes y son
lo único que permite que otra persona compruebe tus números:

```gitignore
# en services/ai/.gitignore
models/
datasets/**
!datasets/**/
!datasets/**/manifest.csv
!datasets/**/provenance.json
results/*
!results/*.json
```

El `.gitignore` de la raíz ya deja pasar `manifest.csv` y `provenance.json`. Si añades uno propio en
`services/ai/`, no vuelvas a excluirlos: un spike cuyos resultados no están en el repo es, para
quien lo revisa, un spike que no ocurrió.

## Reglas que no se negocian

- **Nada de modelos ni datasets en el repo** (`.gitignore` ya bloquea `models/`, `*.pt`, `*.onnx`,
  `*.wav`, `*.mp3`). Descárgalos en tiempo de ejecución a una carpeta ignorada.
- Solo herramientas **gratuitas u open source**.
- El resultado se escribe en `audio_analyses` (`event_id`, `transcript`, `similarity`,
  `synthetic_score`) y la alerta en `alerts` (`event_id`, `severity`, `reason`).

## Criterios de aceptación

- [ ] `python spikes/transcribe.py muestra.wav` imprime la transcripción en español y el tiempo.
- [ ] `python spikes/similarity.py` imprime la similitud de al menos 6 pares y marca cuáles pasan 0.6.
- [ ] `python spikes/vad_pipeline.py` imprime los tramos de habla con tiempos de un audio de prueba.
- [ ] `python spikes/qti_import.py examen.zip` escribe un JSON con preguntas y opciones.
- [ ] Caso negativo demostrado: leer la pregunta en voz alta **sin** respuesta sintética NO alerta.
- [ ] `docker compose up` y un POST de `speech_detected` aparece en los logs del worker.

## Evidencia para la semana

Captura de la terminal con cada spike corriendo y sus números, más la tabla de umbrales probados.
Guárdala en `docs/evidencias/semana-05/pierreluiggi/`.

---

## Lo que ya está hecho (Héctor)

Dos archivos de andamiaje para que no empieces desde cero:

| Archivo | Qué es |
|---|---|
| `worker_stub.py` | worker de RQ que escucha las colas `high` y `audio`. Funciona. |
| `tasks.py` | la función `analyze_audio(event_id)` que el worker ejecuta. **Es un esqueleto**: registra el id y no analiza nada. |

El flujo de punta a punta **ya funciona**:

```bash
docker compose up --build
```

```bash
curl -X POST http://localhost:8000/api/v1/events -H "Content-Type: application/json" --data-binary @packages/contracts/examples/speech_detected.json
```

```bash
docker compose logs ai-worker
```

Verás el `event_id` que devolvió la API aparecer en los logs del worker. Lo único que falta es que
`analyze_audio` haga el trabajo de verdad.

### Dos cosas que no debes cambiar

- **Por la cola solo viaja el `event_id`.** El audio se lee desde Storage con el `evidence_path` del
  evento. Meter el audio en Redis llenaría la memoria del plan gratuito en una sola sesión de examen.
- **Las colas son `high` y `audio`.** `high` es para la verificación facial, que tiene a un
  estudiante esperando en pantalla (P90 < 500 ms); `audio` es la tuya. Si metes el análisis de audio
  en `high`, bloqueas la sala de espera.

La API encola por **nombre** (`tasks.analyze_audio`), no importando la función, para no tener que
instalar tus modelos en su imagen. Si mueves la función, avísame: la constante está en
`services/api/src/proctoring_api/adapters/outbound/redis_queue/job_queue.py`.
