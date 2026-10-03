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
│   ├── transcribir.py
│   ├── similitud.py
│   ├── pipeline_vad.py
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

### `spikes/transcribir.py`

[`faster-whisper`](https://github.com/SYSTRAN/faster-whisper), modelo `small`, idioma español.

```python
from faster_whisper import WhisperModel
model = WhisperModel("small", device="cpu", compute_type="int8")
segments, info = model.transcribe("muestra.wav", language="es", vad_filter=True)
```

Mide y reporta el tiempo: con `small` en CPU debe transcribir 10 s de audio en pocos segundos.
Si no alcanza para el presupuesto de 10 s, prueba `base` y anótalo.

### `spikes/similitud.py`

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

### `spikes/pipeline_vad.py`

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

## Reglas que no se negocian

- **Nada de modelos ni datasets en el repo** (`.gitignore` ya bloquea `models/`, `*.pt`, `*.onnx`,
  `*.wav`, `*.mp3`). Descárgalos en tiempo de ejecución a una carpeta ignorada.
- Solo herramientas **gratuitas u open source**.
- El resultado se escribe en `audio_analyses` (`event_id`, `transcript`, `similarity`,
  `synthetic_score`) y la alerta en `alerts` (`event_id`, `severity`, `reason`).

## Criterios de aceptación

- [ ] `python spikes/transcribir.py muestra.wav` imprime la transcripción en español y el tiempo.
- [ ] `python spikes/similitud.py` imprime la similitud de al menos 6 pares y marca cuáles pasan 0.6.
- [ ] `python spikes/pipeline_vad.py` imprime los tramos de habla con tiempos de un audio de prueba.
- [ ] `python spikes/qti_import.py examen.zip` escribe un JSON con preguntas y opciones.
- [ ] Caso negativo demostrado: leer la pregunta en voz alta **sin** respuesta sintética NO alerta.
- [ ] `docker compose up` y un POST de `speech_detected` aparece en los logs del worker.

## Evidencia para la semana

Captura de la terminal con cada spike corriendo y sus números, más la tabla de umbrales probados.
Guárdala en `docs/evidencias/semana-05/pierreluiggi/`.
