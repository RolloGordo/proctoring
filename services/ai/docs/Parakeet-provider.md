# Proveedor Parakeet sherpa-onnx

**Estado:** implementado en Etapa 3.1 y medido en Etapa 3.2.
**Decisión relacionada:** [`DECISION-asr.md`](../../../docs/evidencias/DECISION-asr.md).
No cambia contratos de API, aplicaciones, migraciones ni defaults globales.

## 1. Contrato exacto del proveedor

El contrato existente del worker está expresado por `audio_runtime.measure_audio(path: Path, question: str | None) -> dict[str, Any]`, llamado desde `tasks.analyze_audio`. El worker recibe un trabajo por `GET /api/v1/internal/audio-jobs/{event_id}`, descarga el audio a un temporal, mide ASR/similitud/voz sintética y publica un resultado con `POST /api/v1/internal/audio-jobs/{event_id}/result`.

Cada proveedor de ASR debe cumplir:

- Construcción explícita que valida la configuración y carga el modelo local si aplica.
- Propiedad `version: str` estable y trazable.
- Método `transcribe(audio: Path, reference: str | None = None) -> dict[str, Any]`.
- Resultado con, al menos, `transcript: str`, `audio_seconds`, `inference_seconds` y `segments: list[dict]`; con `reference`, agregar las métricas WER usadas por `spikes.metrics.word_errors`.
- Sin decisiones de alertas, escrituras de DB, llamadas a API ni captura silenciosa de fallos de infraestructura.

`measure_audio` es el orquestador actual: decodifica el audio, selecciona ASR, evalúa calidad, posiblemente ejecuta fallback, calcula similitud con la pregunta localmente, calcula la puntuación TTS y devuelve `transcript`, `similarity`, `synthetic_voice_score` y `model_versions`. La API continúa siendo responsable de crear una alerta de consulta a IA solo cuando se cumplen simultáneamente similitud con la pregunta y voz sintética. El evento `speech_detected` se conserva por sí solo.

El formato sugerido para trazabilidad es:

```text
parakeet-tdt-0.6b-v3-fp32;sherpa-onnx=2.0.1;revision=5fcc0122fe87e8365e339e467af90c67b746218f
faster-whisper-small-cpu-int8;fallback_from=<versión Parakeet>;reason=<motivo>
```

El string de versión describe qué motor produjo el texto final; agregar estado de calidad no debe borrar la cadena de fallback.

## 2. Variables y validación

Configuración propuesta:

| Variable | Recomendación | Validación |
|---|---|---|
| `ASR_PROVIDER` | Permitir `parakeet`; default global continúa `deepgram` | Rechazar valores desconocidos al iniciar |
| `ASR_FALLBACK_PROVIDER` | Para el VPS recomendado: `faster-whisper`; default global continúa `none` | Añadir el valor al enum, validar que el extra local existe |
| `ASR_LOCAL_MODEL` | `small` cuando el fallback sea faster-whisper | Usar la validación existente tiny/base/small |
| `PARAKEET_MODEL_DIR` | Obligatoria al seleccionar Parakeet; ruta montada desde `/models` | Directorio presente y archivos requeridos por precisión presentes |
| `PARAKEET_PRECISION` | `fp32` por default del proveedor; acepta `fp32` o `int8` | Elegir nombres de archivos según precisión; verificar SHA-256 contra el manifiesto fijado |
| `PARAKEET_NUM_THREADS` | `4` para el VPS de seis vCPU | Entero positivo; reservar CPU para worker, similitud y sistema |

Revisiones P02 fijadas en [`validation-model-assets.json`](../results/validation-model-assets.json): FP32 `5fcc0122fe87e8365e339e467af90c67b746218f`; INT8 `ed5d745623472f97cfc2e6c2916ee248798fc5a8`. FP32 requiere `encoder.onnx`, `encoder.weights`, `decoder.onnx`, `joiner.onnx` y `tokens.txt`; INT8 requiere `encoder.int8.onnx`, `decoder.int8.onnx`, `joiner.int8.onnx` y `tokens.txt`.

Errores visibles y no ambiguos:

- Variable ausente/inválida, precisión desconocida, threads ≤ 0, ruta vacía/inexistente, SHA que no coincide, dependencia `sherpa-onnx` ausente o archivos incompletos: error de configuración con nombre de variable/archivo, sin texto de transcripción y sin cambiar automáticamente de motor.
- Una vez validado el contrato y los pesos, una falla del runtime ONNX al crear la sesión o durante inferencia: log seguro con motor, clase de error y sample/job ID no sensible; usar fallback local si está configurado y registrar el motivo en `model_versions`.
- Si el fallback local no está configurado o falla, propagar el fallo para que el trabajo pueda fallar/reintentarse según política RQ. No falsificar una transcripción vacía exitosa.

## 3. Puerta de calidad sin Deepgram

Usar la duración real del audio, calculada al decodificar, para palabras por segundo. No inferir duración de la última marca temporal. `stream.result` de sherpa expone texto, tokens, timestamps, duraciones y `ys_log_probs`; el adaptador debe normalizar estos datos en `segments` y guardar el promedio de log-probabilidades como señal de confianza, si se confirma su semántica con la versión fijada.

Señales candidatas de la puerta:

1. Texto vacío.
2. Menos de `ASR_MIN_WORDS_PER_SECOND` en texto no vacío (punto de partida congelado actual: 0,50 palabras/s).
3. Heurística de idioma basada en marcadores; el set y regla deben quedar versionados. La P02 mostró que esta señal no detectó cinco transcripciones malas.
4. Media/estadístico robusto de `ys_log_probs`, timestamps con huecos anómalos y proporción de tokens de control/no palabra; solo después de confirmar qué entrega sherpa-onnx 2.0.1.

Los valores calibrados están en `results/quality-gate-parakeet.json`, se obtuvieron con una sola voz P01 y no son garantía para otras voces. No se calibrará ni escogerá un umbral con P02. La hipótesis de mejora para P03 es que una señal de confianza del decodificador capture errores de contenido con WPS normal y que la heurística de idioma se sustituya o complemente con evidencia más robusta. Para la validación P03 se deben fijar los umbrales antes de revelar WER y medir recall, falsos disparos e intervalos Wilson; conservar este conjunto P02 como prueba, sin retuning.

Cuando falle la calidad y Deepgram esté desactivado, conservar el texto de Parakeet y devolver estado **`low_confidence` / “transcripción de baja confianza”** con lista de motivos. No disparar otro motor por el mero resultado de la puerta. La cascada local a faster-whisper se reserva para fallo técnico de Parakeet. La similitud de una transcripción de baja confianza puede calcularse para que el docente tenga contexto, pero no debe producir por sí sola la alerta de consulta a IA; la API conserva su regla de dos señales.

### Contrato API propuesto (no implementar en esta etapa)

Hoy `AudioMeasurementRequest` permite `transcript`, `similarity`, `synthetic_voice_score`, `processing_ms` y `model_versions`; rechaza campos extra. La respuesta y persistencia de `audio_analyses` tampoco expresan directamente confianza de transcripción. Para que la UI no confunda baja confianza con ausencia de habla o un resultado negativo, propongo:

- Añadir `transcription_status: "ok" | "low_confidence" | "unavailable"` y `quality_reasons: string[]` al contrato de resultado interno y a la respuesta de análisis.
- Persistir ambos campos con una migración futura; reflejarlos en el modelo de dominio/repositorio y los tipos de `packages/contracts`.
- Mostrar en la UI “transcripción de baja confianza” junto al texto y motivo. Mantener `similarity=null` cuando no haya pregunta/modelo o no se pueda medir; nunca traducir esa ausencia a similitud cero.
- Mantener inalterado el criterio de alerta IA: similitud suficiente **y** voz sintética suficiente. El estado `low_confidence` no elimina el evento hablado ni crea una alerta de fraude.

## 4. Fork, precarga y memoria

RQ `Worker` ejecuta trabajos mediante `fork()` en Linux; `SimpleWorker` ejecuta en el mismo proceso. `worker_stub.precargar_modelos()` ya trata faster-whisper de forma distinta en esos dos modos porque CTranslate2 crea threads C++ que no deben heredarse usando una instancia del padre tras fork. No hay medición de seguridad de fork para sherpa-onnx/ONNX Runtime en este repositorio.

Diseño conservador: no construir `OfflineRecognizer` en el padre antes de `fork()`. En `Worker` normal, construirlo después del fork en el proceso del trabajo y no reutilizar estado nativo heredado. En `SimpleWorker`, se puede precargar una vez, pero debe probarse con medición y estrés antes de recomendarlo. Si el costo por trabajo es inaceptable, la alternativa operativa a validar es `WORKER_USE_SIMPLE_WORKER=true` con un proceso serial; no asumir seguridad del fork a partir de que una prueba pequeña pase.

La matriz actual reportó pico cgroup FP32 de 3.171,4 MB bajo configuración medida con similitud y OOM bajo 2 GiB. Falta medir la mezcla exacta de FP32 + `SIMILARITY_BACKEND=torch`, número de procesos RQ, carga fría/caliente y presión total de 12 GB. El preflight debe sumar límite cgroup observado, porcentaje de reserva del 85 % y número de procesos. Con `ASR_ENFORCE_MEMORY_BUDGET=false`, emitir aviso; con `true`, abortar si el perfil configurado excede la reserva acordada. El límite y el conteo soportado no se fijan hasta la Fase 3.2.

## 5. Riesgos, licencia y decisiones abiertas

- La P02 midió mejor WER FP32, pero una voz nueva no prueba generalización; P01 no tiene artefacto verificable y solo hay dos voces objetivo.
- FP32 usa `encoder.weights` de 2.435.420.160 bytes en el artefacto P02 y tiene pico cgroup medido de 3.171,4 MB en una combinación anterior. El VPS de 12 GB parece el perfil adecuado, pero falta prueba simultánea con la configuración de similitud y workers real.
- TDT FP32 ocupa más tiempo de arranque/carga; P02 registró 8,633 s de carga en laptop. No extrapolar ese tiempo al VPS.
- El uso de ONNX Runtime después de `fork()` no se ha medido. Hasta medirlo, no compartir un recognizer creado antes del fork.
- INT8 queda seleccionable únicamente para experimentación: P02 arrojó 58,44 % WER general, 8 salidas vacías y 2 salidas con heurística de idioma extranjero; no es el recomendado.
- El model card oficial indica CC-BY-4.0, atribuye los pesos a NVIDIA y la exportación al proyecto sherpa-onnx. Conservar sus atribuciones y avisos de licencia en README/NOTICE al implementar. Véase [model card FP32](https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3).
- No hay ahora paquete/licencia/contrato de configuración implementado para el proveedor. `ASR_PROVIDERS`, fallback, memoria, `/health`, preloads, `model_versions`, dependencias e instalación quedan para 3.1, tras aprobación.

## Estado de etapa 3.1

El adaptador está registrado en `ASR_PROVIDERS`. FP32 es la precisión predeterminada del proveedor; INT8 genera advertencia con resultados P02. `scripts/download_parakeet.py` descarga revisiones fijas y valida cada SHA-256. Configuración y artefactos se validan antes de aceptar trabajos. La cascada Parakeet → faster-whisper small se permite solo para errores de inicialización/inferencia; la puerta solo registra `low_confidence` en log y `model_versions` y no conmuta proveedor. Los umbrales existentes se validaron con salidas INT8, no FP32.

El worker no necesita `DEEPGRAM_API_KEY` en el perfil local. `/health` incluye precisión, ruta, revisión, estado de carga, estrategia y presupuesto de memoria; no publica secretos.

### Medición de precarga y fork

Se hicieron cinco pruebas por modo con sherpa-onnx 2.0.1, revisión FP32 `5fcc0122fe87e8365e339e467af90c67b746218f`, 4 hilos y audio P02_A1_base de 16 kHz mono. El reconocedor heredado tuvo 5/5 ejecuciones y tiempos de decode [2,20191; 2,16229; 2,18297; 2,17302; 2,19002] s. Construirlo en el hijo dio 5/5, inicialización [3,04770; 2,32132; 2,23754; 2,30659; 2,39978] s y decode [0,77902; 0,75362; 0,73419; 0,80092; 0,73166] s. Python emitió advertencia de posible deadlock al hacer fork desde un proceso multihilo. Cinco éxitos no prueban seguridad: RQ `Worker` carga en el hijo tras fork y `SimpleWorker` precarga en su proceso serial. Datos: `results/parakeet-fork-safety.json`.

## Etapa 3.2: resultados medidos

Las corridas usaron Docker cgroups en el host disponible, que reporta 12.309.565.440 bytes de RAM física y 8 CPU visibles; las cuotas Docker se fijaron por contenedor. Por tanto, estos resultados reproducen cuotas, pero no equivalen a una VPS remota independiente.

### Memoria y latencia de pipeline

Parakeet FP32 más similitud ONNX int8 consumió un pico cgroup de **2.699.165.696 bytes** (15 s) y **2.812.870.656 bytes** (30 s). RSS máximo del proceso: **3.002.306.560** y **3.165.171.712 bytes**, respectivamente. Para obtener esas duraciones, el audio P02_A1_base se decodificó y repitió/recortó a 15/30 s; no son archivos grabados con esa duración. JSON: `results/phase3.2-memory-15s.json`, `results/phase3.2-memory-30s.json`.

La latencia integra copia local como descarga simulada, `measure_audio` (ASR + similitud) y serialización JSON como POST simulado. Se midió un primer trabajo frío y **20 calientes** por cuota; el detalle p50/p90, muestras y RSS está en `results/phase3.2-latency-cpu1.json`, `results/phase3.2-latency-cpu2.json` y `results/phase3.2-latency-cpu3.json`. Las latencias frías para CPU 1/2/3 fueron 20,28 / 17,97 / 12,86 s; calientes p50/p90 fueron 9,30/11,43 s, 5,06/6,34 s y 2,05/2,64 s. RSS HWM de CPU 1/2/3: 3.066.0 / 3.065.2 / 3.064.3 MB; pico cgroup 3.784.302.592 / 3.665.223.680 / 3.931.389.952 bytes. POST y descarga no atraviesan red: esos pasos solo simulan serialización y copia de archivo.

La imagen `proctoring-ai-worker:vps` mide **3.012.124.371 bytes**. No incluye pesos; se montan desde `/models`.

### Worker, fork y recuperación

Se usaron 50 trabajos RQ consecutivos por modo, cuota de seis CPU / 12 GiB. `Worker` con fork completó 50/50 en 219,86 s (13,64 trabajos/minuto), primer trabajo 8,07 s y siguientes p50/p90 3,96/4,17 s; RSS HWM del proceso hijo 2.846.552.064 bytes y pico cgroup 4.698.435.584 bytes. `SimpleWorker` sin fork completó 50/50 en 73,22 s (40,97 trabajos/minuto), primer trabajo 0,93 s y siguientes p50/p90 1,32/1,68 s; RSS HWM del proceso 2.990.006.272 bytes y pico cgroup 3.124.047.872 bytes. Es una comparación operacional de una corrida. Datos: `results/phase3.2-worker-modes.json`, `results/phase3.2-worker-mode-a.json`, `results/phase3.2-worker-mode-b.json`.

El timeout de RQ falló el trabajo y el worker continuó con el siguiente. Al terminarse el proceso B con `os._exit`, la política Docker reinició el contenedor, pero el trabajo quedó en estado `started` y no se recuperó automáticamente. El modo A detectó el workhorse terminado y preservó el trabajo como reintento programado; el worker está invocado con `with_scheduler=False`, por lo que no se observó reejecución automática del retry. **Recomendación: modo A (`WORKER_USE_SIMPLE_WORKER=false`) por aislamiento y preservación del estado del trabajo ante caída fatal.** Configurar y verificar el scheduler/requeue antes de prometer recuperación automática. Si se elige B, un fallo grave reinicia todo el proceso y puede dejar el trabajo en `started`; la política `restart` por sí sola no lo recupera.

La composición de RQ con 1/2/3 procesos, jobs/minuto y límite de RAM 75 % está en `results/phase3.2-worker-capacity.json`. En A, 1 proceso completó 50 trabajos a 13,64 trabajos/min y pico cgroup 4,70 GB; 2 procesos completaron 30 a 14,59/min con pico agregado simultáneo 5,51 GB; 3 procesos completaron 30 a 6,89/min con pico agregado 7,65 GB. Los tres caben bajo el 75 % de la memoria física medida (9,23 GB), pero 2 procesos obtuvieron la mayor tasa observada. El modo B de un proceso está en `results/phase3.2-worker-mode-b.json`. El fallback local cargó faster-whisper small junto a Parakeet en el mismo proceso; el pico combinado fue 3.936.030.720 bytes cgroup y RSS HWM 3.427.516.416 bytes (`results/phase3.2-failure-probes.json`). Una prueba RQ mixta con 3 procesos, fallback forzado y dos trabajos normales finalizó 3/3; su máximo agregado simultáneo fue 6,94 GB (`results/phase3.2-capacity-rq-3-fallback.json`).

### Evaluación integrada y pruebas de fallos

Se repitieron 28 filas del artefacto previo: **20 audios propios P01 y 8 MediaSpeech**, además de los 30 audios de P02. Se ejecutó `audio_runtime.measure_audio` con Parakeet FP32 y similitud ONNX int8; no se cambiaron umbrales. Resultado actual: P01 propio 92/520 errores, micro-WER 17,69 % vs 90/520 (17,31 %) guardado, diferencia +0,38 pp; P02 168/770 (21,82 %) vs 171/770 (22,21 %), diferencia −0,39 pp. P01 histórico no tenía hash/revisión verificable; esto es una repetición con los pesos fijados ahora, no valida que el artefacto antiguo fuera idéntico. JSON completo por muestra (sin audio ni texto de transcripción): `results/phase3.2-integrated-evaluation.json`; delta resumido: `results/phase3.2-evaluation-differences.json`.

La prueba Compose local usa Redis, API y almacenamiento simulados; 1, 30 y 200 trabajos terminaron, y el POST simulado 503 produjo un retry y resultado final. `/health` respondió con el modelo cargado y sin `DEEPGRAM_API_KEY`; solo health del worker quedó publicado en `127.0.0.1`, mientras Redis y mocks no tenían puertos publicados. Evidencia: `results/phase3.2-compose-e2e.json`. No valida una API remota real.

Las pruebas separadas verifican carpeta ausente, carpeta equivocada, hash alterado, salida vacía y error de ejecución con cascada local. Las cifras y el máximo de memoria con ambos modelos cargados están en `results/phase3.2-failure-probes.json`. Ninguna prueba modifica la puerta ni sus umbrales.

### Perfil de despliegue provisional

Usar Parakeet FP32, faster-whisper small como fallback de error técnico, similitud ONNX int8, RQ Worker con fork y `PARAKEET_NUM_THREADS=4`. En la medición de concurrencia, dos procesos produjeron el mayor throughput (14,59 trabajos/min); tres degradaron a 6,89/min. El Compose de VPS actual publica un puerto de health por servicio, así que hasta separar los puertos por réplica la configuración operativa recomendada para ese archivo es **un proceso** (13,64 trabajos/min medidos), sin escalado `--scale` que choque en 8080. Mantener Deepgram sin clave. Defaults globales: Deepgram / ningún fallback / similitud PyTorch.
