# `services/ai` — Servicio de IA de audio (FastAPI + workers RQ)

**Responsable:** Zevallos Bocanegra, Pierreluiggi
**Backlog:** SP-007 / TA-008 / TA-009 (previos); TA-012 y TA-013 (worker y similitud).

**Actualización local 09/10/2026:** hay evaluadores P1/P2, worker P3, integración
de audio web P4 y parser QTI P5. No se han completado las evaluaciones de datasets
ni la aceptación con infraestructura real. Los apartados de planificación que
siguen proceden del andamiaje inicial; consultar primero estas guías vigentes:

- [P1: similitud](docs/P1-similitud.md).
- [P2: voz sintética](docs/P2-voz-sintetica.md).
- [P3: worker](docs/P3-worker-audio.md).
- [P4: VAD web](docs/P4-vad-web.md).
- [P5: QTI y manifiestos](docs/P5-qti-actualizacion.md).

El Dockerfile heredado sigue siendo provisional y **no instala ni copia todo lo
necesario para este worker**. La ejecución comprobada es local con uv. La imagen
y composición Docker deben integrarse con Héctor; no se declaran verificadas.
Lee [`CLAUDE.md`](../../CLAUDE.md) §1 y §3 antes de integrar.

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
score = util.cos_sim(emb[0], emb[1]).item()  # alerta si > 0.6
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

## Probar el spike de transcripción (ya funciona)

Tras un `git pull`, **primero recupera los audios**: el repositorio guarda el manifiesto, las
referencias y los hashes, pero no el audio (pesa y está en `.gitignore`).

```bash
cd services/ai && uv run python -m spikes.download_sample --restore
```

```bash
uv run python -m spikes.demo --offline
```

`--restore` descarga las ocho muestras registradas y **verifica su SHA-256** contra el manifiesto;
si encuentra un audio local modificado, se detiene y lo conserva. `--offline` evita descargar el
modelo, así que la primera vez quítalo o usa `--model base`, que es más ligero.

Si lo ejecutas sin recuperar los audios, verás `Audio inexistente o fuera de la carpeta del
manifiesto`. No es un error del código: es el manifiesto haciendo su trabajo.

Detalle completo en [`docs/SP-007-guide.md`](docs/SP-007-guide.md). Los resultados medidos y lo que
significan para el presupuesto de 10 s están en
[`docs/development-report.md`](docs/development-report.md).

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

---

## Configuración del motor ASR, puerta de calidad y cascada (Etapa 2A)

El módulo de audio (`audio_runtime.py`) soporta dos motores de transcripción y una cascada opcional controlada íntegramente por variables de entorno:

| Variable | Por defecto | Valores permitidos / Descripción |
|---|---|---|
| `ASR_PROVIDER` | `faster-whisper` | `faster-whisper` \| `deepgram`. Motor de transcripción primario (leído en cada llamada). |
| `ASR_LOCAL_MODEL` | `small` | `tiny` \| `base` \| `small`. Tamaño del modelo CTranslate2 (`int8`, CPU). |
| `ASR_FALLBACK_PROVIDER` | `none` | `none` \| `deepgram`. Con `none` (por defecto), el procesamiento es **100 % local** sin requerir credenciales externas. Con `deepgram`, pasa a Deepgram Nova-3 solo si Whisper falla o no supera la puerta de calidad. |
| `ASR_FALLBACK_ON_EMPTY` | `true` | `true` \| `false`. Si `true`, una salida vacía de Whisper dispara el respaldo (cuando está activo). |
| `ASR_LOCAL_VAD_FILTER` | `true` | `true` \| `false`. Activa el filtro Silero VAD integrado en `faster-whisper`. |
| `ASR_LOCAL_VAD_THRESHOLD` | `0.3` | Flotante en `(0, 1)`. Umbral de probabilidad de voz del VAD local. |
| `ASR_MIN_WORDS_PER_SECOND` | `0.50` | Palabras por segundo mínimas aceptables en transcripciones no vacías. |
| `ASR_MAX_NO_SPEECH_PROB` | `0.60` | `no_speech_prob` máxima permitida en cualquier segmento de Whisper. |
| `ASR_MIN_AVG_LOGPROB` | `-0.60` | `avg_logprob` mínima permitida en cualquier segmento de Whisper. |
| `ASR_MAX_COMPRESSION_RATIO` | `1.85` | `compression_ratio` máxima permitida por segmento (atrapa bucles repetitivos). |
| `ASR_HALLUCINATION_PHRASES` | *(lista por defecto)* | Frases típicas de alucinación separadas por coma (`suscríbete`, `más información en www`, `amara.org`, `gracias por ver`, etc.). |
| `ASR_LATENCY_BUDGET_SECONDS` | `10.0` | Presupuesto total de latencia para calcular el timeout restante del respaldo: `min(4.5, 10.0 - t_gastado - 1.5)`. Si no queda presupuesto (`<= 0`), se omite Deepgram y el evento se reporta sin análisis (`transcript=""`, `similarity=None`). |
| `ASR_FALLBACK_MAX_TIMEOUT_SECONDS` | `4.5` | Timeout máximo por solicitud a Deepgram cuando actúa como respaldo. |
| `ASR_POST_ASR_RESERVE_SECONDS` | `1.5` | Margen reservado tras el ASR para `SimilarityModel` y publicación del resultado. |
| `SIMILARITY_BACKEND` | `torch` | `torch` \| `onnx-int8` \| `onnx-fp32`. Backend para `paraphrase-multilingual-MiniLM-L12-v2` (`SimilarityModel` con PyTorch o `OnnxSimilarityModel` con `onnxruntime` + `tokenizers`). |
| `SIMILARITY_ONNX_VOCAB` | `es_en` | `es_en` \| `full`. Modo de vocabulario para `OnnxSimilarityModel` (`es_en` recorta a 90 525 tokens ES/EN manteniendo paridad 1,000000 y bajando el pico de RAM a ~221 MiB). |
| `ASR_ENFORCE_MEMORY_BUDGET` | `false` | `false` \| `true`. Con `false` (por defecto), un límite de memoria de contenedor (`memory.max`) inferior al mínimo requerido por `(SIMILARITY_BACKEND, ASR_PROVIDER)` solo emite un aviso (`logger.warning` y `/health`). Con `true`, aborta el arranque con código de salida `1`. |

### Trazabilidad en `model_versions["asr"]` y `model_versions["sim"]`

- Motor local aceptado: `faster-whisper-small-cpu-int8`.
- Respaldo ejecutado en Deepgram: `deepgram-nova-3-es;fallback_from=faster-whisper-small-cpu-int8;reason=<motivo>`.
- Respaldo omitido por presupuesto agotado: `faster-whisper-small-cpu-int8;fallback_skipped=budget_exhausted;reason=<motivo>`.
- Puerta de calidad activada con `ASR_FALLBACK_PROVIDER=none`: `faster-whisper-small-cpu-int8;quality_gate=<motivo>;fallback=none`.
- Similitud: `multilingual-MiniLM-L12-v2@<SIM_REVISION>` (con `torch`) o `multilingual-MiniLM-L12-v2@<SIM_REVISION>;backend=onnx-int8` / `onnx-fp32`.

### Nota de privacidad y limitaciones conocidas

- **Privacidad**: Con `ASR_PROVIDER=faster-whisper` y `ASR_FALLBACK_PROVIDER=none`, ningún fragmento de audio sale del servidor. Con `ASR_FALLBACK_PROVIDER=deepgram` (o `ASR_PROVIDER=deepgram`), los fragmentos de audio que requieran respaldo (o todos en modo `deepgram`) son procesados por la API externa de Deepgram Nova-3. **El enunciado de la pregunta del examen nunca se envía a Deepgram**; la comparación semántica (`SimilarityModel` / `OnnxSimilarityModel`) se ejecuta siempre en local.
- **Calibración en muestra**: Los umbrales de la puerta de calidad se calibraron sobre **28 audios en muestra** (8 de MediaSpeech y 20 grabaciones de una sola voz `P01` en 5 condiciones), sin validación independiente (véase `results/quality-gate-calibration.json`).
- **Limitación conocida (susurro / voz muy baja)**: Las grabaciones en susurro (`voz baja`) presentan un WER de `100 %` en `faster-whisper small` y de `79,81 %` en Deepgram Nova-3 (`results/asr-comparison.json`). El susurro extremo no es transcribible de manera fiable por ninguno de los dos motores.
- **Requisitos de memoria y CPU (Etapa 0 y 2B, `results/stage0-docker-limits.json` y `results/onnx-minilm-experiment.json`)**:
  - Con `SIMILARITY_BACKEND=torch`: `faster-whisper small` alcanza un pico de `1.698,42 MiB` de RSS en Docker (mínimo requerido `1.800 MiB`), y Deepgram alcanza `1.124,38 MiB` (mínimo requerido `1.280 MiB`), por lo que requieren al menos **2 GB de RAM**.
  - Con `SIMILARITY_BACKEND=onnx-int8` (`SIMILARITY_ONNX_VOCAB=es_en`): Deepgram baja a `~225 MiB` de RSS (cabe en **512 MB**), `faster-whisper tiny` a `~435 MiB` (cabe en **512 MB**), `base` a `~545 MiB` (cabe en **1 GB**) y `small` a `~980 MiB` (cabe en **2 GB**).
  - Al arrancar, `worker_stub.py` lee `/sys/fs/cgroup/memory.max` y compara contra el mínimo según `(SIMILARITY_BACKEND, ASR_PROVIDER)`: por defecto emite un aviso en logs y en `/health`, y solo aborta el arranque si `ASR_ENFORCE_MEMORY_BUDGET=true`.



## Parakeet ASR (experimental integration)

Install `uv sync --extra asr-parakeet`; add `--extra asr-local` to enable the local
faster-whisper small runtime fallback. Download pinned model files with
`uv run --extra asr-parakeet python scripts/download_parakeet.py --precision fp32 --output /models/parakeet-fp32`.
Set `ASR_PROVIDER=parakeet`, `PARAKEET_MODEL_DIR=/models/parakeet-fp32`,
`PARAKEET_PRECISION=fp32`, and optionally `PARAKEET_NUM_THREADS=4`. FP32 is the
primary precision. INT8 is experimental and emits a warning. Its P02 measurement
was 58.44% WER with 8/30 empty outputs and 2/30 foreign-language heuristic matches.
The quality-gate thresholds were calibrated on Parakeet INT8 outputs (P01), not
FP32; the gate records low confidence in logs and `model_versions` and never routes
to another provider.

Parakeet configuration, missing files, checksum mismatch, and unavailable extras
fail without fallback. Only runtime initialization/inference failures can cascade
locally to faster-whisper small when explicitly configured. RQ's fork worker loads
Parakeet lazily in its child; measured fork trials are recorded in
`results/parakeet-fork-safety.json`. SimpleWorker may load in its own process.
The memory check warns below its budget and becomes fatal only with
`ASR_ENFORCE_MEMORY_BUDGET=true`; the FP32 ONNX similarity combination uses a
conservative bound pending a direct measurement.
