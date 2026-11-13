# Decisión ASR — Fase 2

**Fecha:** 13 de noviembre de 2026
**Rama:** `feat/audio-faster-whisper-principal`
**Estado:** avanzar al diseño 3.0 del adaptador Parakeet TDT 0.6B v3 FP32. La implementación no se inicia hasta aprobar ese diseño.

> Historial: esta línea conserva el estado al aprobar Fase 2. El cierre de Etapas 3.1 y 3.2 está documentado al final de este memo.

## Regla aplicada

La regla de decisión congelada dispone continuar si la estimación puntual de H1 en P02 reduce el WER adverso en al menos 10 puntos porcentuales y su dirección coincide con P01. La reducción medida en P02 es **27,49 pp**, con bootstrap por audio estratificado por hablante e IC95 **[−43,22; −13,85] pp** para el delta FP32−faster-whisper. Es mayor que 10 pp y la dirección coincide con la comparación histórica P01 indicada para esta decisión. **La regla se cumple: se continúa con el adaptador FP32.**

La reducción P02 (**27,49 pp**) es menor que la reducción P01 calculada con los resultados guardados (**54,49 pp**: WER adverso 79,49 % a 25,00 %). La comparación con P01 es histórica, no una reproducción verificada: los resultados P01 no guardaron la revisión ni hashes de Parakeet. Solo hay **dos voces objetivo** (P01 y P02), así que esto no demuestra generalización a nuevas voces.

## Artefactos Parakeet usados en P02 y cierre de H4

Se bajaron y verificaron estos artefactos oficiales de sherpa-onnx. La revisión y hashes están registrados también en [`validation-model-assets.json`](../../services/ai/results/validation-model-assets.json); la corrida y sus transcripciones están en [`validation-evaluation.json`](../../services/ai/results/validation-evaluation.json).

| Variante | Repositorio | Revisión Hugging Face | Runtime |
|---|---|---|---|
| FP32 | `csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3` | `5fcc0122fe87e8365e339e467af90c67b746218f` | sherpa-onnx 2.0.1 |
| INT8 | `csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` | `ed5d745623472f97cfc2e6c2916ee248798fc5a8` | sherpa-onnx 2.0.1 |

SHA-256 de los archivos consumidos:

| FP32 | SHA-256 |
|---|---|
| `encoder.onnx` | `36b758364dfddce472b9a9f75bf6049bbd35c886d7927e3eda80d4ceb3348512` |
| `encoder.weights` | `3af3f51af5f2d01dbbf5af47d42c7962a2c205f11004254bb4f2b979862f39a8` |
| `decoder.onnx` | `caed31af1bb08edcc09a01a1c3cbb4d4eb5bfdb9c4e5f307012f84bbf5dbfdbc` |
| `joiner.onnx` | `0f294e5ba9021a3d80e492de94abe4c116f0afce78452c7debb5dd07690d0340` |
| `tokens.txt` | `d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d` |

| INT8 | SHA-256 |
|---|---|
| `encoder.int8.onnx` | `1afbe69c1ffdabee94755f42e4daf1d93549131a3da11356bda84fcef0f2c479` |
| `decoder.int8.onnx` | `0222a86147299d4dee90edf95b6d13827edb42ad8b7c9cf0b2582f030937c0b5` |
| `joiner.int8.onnx` | `cbd02f3696e9944970111fb439d9c3fd365a80374565f13f2b9c7007d253fc98` |
| `tokens.txt` | `d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d` |

**H4 queda no verificada entre voces.** Busqué los pesos y metadatos P01 en `services/ai`, resultados, historial Git y directorios locales de modelos. P01 no conserva revisión, hashes ni los archivos que permitirían calcularlos; no se puede demostrar que usara estas mismas revisiones. Por eso no volví a ejecutar P01 con un artefacto distinto como si reprodujera el anterior. El orden previo coincide, pero la identidad de modelo no está comprobada. La marca anterior “no concluyente” se precisa aquí como **“comparación entre voces no verificada”**.

## Perfil recomendado: VPS de 12 GB y 6 vCPU

Configuración de despliegue recomendada una vez implementado y validado el adaptador:

```dotenv
ASR_PROVIDER=parakeet
ASR_FALLBACK_PROVIDER=faster-whisper
ASR_LOCAL_MODEL=small
PARAKEET_PRECISION=fp32
PARAKEET_MODEL_DIR=/models/parakeet_tdt_0.6b_v3_fp32
PARAKEET_NUM_THREADS=4
SIMILARITY_BACKEND=torch
```

No configurar `DEEPGRAM_API_KEY`: Deepgram queda desactivado en este perfil. Su proveedor y código actuales se conservan para quien lo seleccione explícitamente. Estos valores son una **configuración recomendada por entorno**, no cambios a los defaults del repositorio: `ASR_PROVIDER=deepgram`, `ASR_FALLBACK_PROVIDER=none` y `SIMILARITY_BACKEND=torch` siguen como defaults.

Parakeet FP32 es el principal por calidad observada. faster-whisper small INT8 es el respaldo local cuando falle la ejecución de Parakeet. No se recomienda Parakeet INT8: en P02 produjo WER adverso alto, salidas vacías y salidas marcadas como idioma extranjero.

La matriz Docker anterior midió un pico de **3.171,4 MB de cgroup** para Parakeet FP32 con similitud bajo límite de 4 GiB; con límites de 512 MiB, 1 GiB y 2 GiB terminó por OOM. Esa medición no incluyó la composición final de 12 GB, varios procesos RQ ni carga completa del servidor. Arrancar con un proceso de inferencia por vez y 4 hilos ASR es una propuesta conservadora, no una capacidad de producción medida. Se deben medir memoria combinada (Parakeet + similitud PyTorch), carga en frío, latencia y concurrencia en el VPS antes de afirmar capacidad o SLO.

## Alcance y límites de la decisión

La decisión habilita únicamente el trabajo de diseño de Etapa 3.0. No autoriza todavía integración ni cambio de defaults. H3 se refutó en P02: la puerta INT8 mantuvo 0/13 falsos disparos observados, pero detectó 12/17 transcripciones malas (70,59 % de recall; Wilson 95 % [46,87 %; 86,72 %]). No se ajustan umbrales con P02. La hipótesis para evaluar con P03 es añadir una señal de confianza del decodificador Parakeet basada en los log-probabilidades de tokens (`ys_log_probs`), además de validar una detección de idioma más fiable; cualquier umbral debe fijarse con datos independientes antes de evaluar P03.

Los modelos sherpa publicados requieren audio mono a 16 kHz, y el model card declara licencia CC-BY-4.0; el despliegue debe conservar atribución de NVIDIA por los pesos y sherpa-onnx por la exportación. La documentación oficial describe los paquetes FP32 e INT8 y sus archivos separados ([model card FP32](https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3), [model card INT8](https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8)).

## H3: origen, positivos omitidos y señal

Los **17 casos malos y 13 buenos** son las 30 transcripciones P02 de **Parakeet INT8**, el motor al que se aplicó la puerta calibrada en `quality-gate-parakeet.json`. “Mala” significa, tal como se fijó antes de P02, **WER > 0,40 o similitud exacta de referencia < 0,60**. La puerta solo dispara con texto vacío, texto no vacío a menos de 0,50 palabras/s o al menos dos marcadores ingleses. Los cinco casos siguientes tenían texto, superaron 0,50 palabras/s y no alcanzaron dos marcadores; por eso ninguna regla disparó.

`avg_logprob` no se guardó en el resultado inicial de P02 y sherpa no entrega el mismo campo segmentado de faster-whisper. Para responder con una señal comparable dentro del decodificador de sherpa, repetí solo estas cinco inferencias con los artefactos INT8 P02 fijados arriba y calculé **media de `stream.result.ys_log_probs`**. Es un proxy propio del decodificador, no es Whisper `avg_logprob`, no se usó por la puerta y no se eligió umbral con estos datos. No sustituye el `avg_logprob` original: esa columna queda como **N/D**.

| Audio | Condición | WER | Similitud referencia | `avg_logprob` original | Media sherpa `ys_log_probs` | Palabras/s | Por qué pasó |
|---|---|---:|---:|---:|---:|---:|---|
| `P02_A4_lejos` | lejos | 0,5263 | 0,5755 | N/D | −0,506201 | 0,967 | No vacío; WPS ≥0,50; idioma no disparado |
| `P02_A4_voz_baja` | voz baja | 0,7368 | 0,2846 | N/D | −0,340079 | No vacío; WPS ≥0,50; idioma no disparado |
| `P02_B1_lejos` | lejos | 1,0000 | 0,2427 | N/D | −0,639804 | No vacío; WPS ≥0,50; idioma no disparado |
| `P02_B2_bajaylejos` | baja y lejos | 1,0000 | 0,0359 | N/D | −0,402592 | No vacío; WPS 0,5135 ≥0,50; idioma no disparado |
| `P02_B2_lejos` | lejos | 0,5185 | 0,6813 | N/D | −0,219825 | No vacío; WPS ≥0,50; similitud de referencia no forma parte de la puerta runtime |

La puerta empleada en producción no puede calcular WER o similitud exacta de referencia porque no recibe una transcripción de referencia. Esos campos solo definen la etiqueta de evaluación. La investigación para P03 debe validar, sin tocar los umbrales con P02, si un estadístico de `ys_log_probs` combinado con mejor detección de idioma mejora recall sin disparar falsos positivos. El conjunto de P03 debe separar calibración y prueba antes de fijar el umbral.

## Sin Deepgram: comportamiento propuesto

- **Fallo de ejecución de Parakeet:** si `ASR_FALLBACK_PROVIDER=faster-whisper`, ejecutar faster-whisper small local y registrar ambos modelos y motivo en `model_versions`. La falla debe quedar en log estructurado; nunca ocultarla. Si faster-whisper también falla, propagar error para política de reintentos del trabajo.
- **Error de configuración:** variable inválida, dependencia ausente, directorio vacío/inexistente, artefacto incompleto o checksum incorrecto debe fallar en el preflight/inicio con error claro. No cambiar silenciosamente a faster-whisper, porque eso ocultaría un despliegue roto.
- **Puerta de baja confianza:** si Parakeet produce texto pero no supera la puerta y Deepgram está desactivado, devolver ese texto como `low_confidence` (“transcripción de baja confianza”), con motivos; no activar el respaldo local por una mera señal de calidad. La cascada a faster-whisper queda reservada para falla técnica de Parakeet. No declarar una baja confianza como similitud 0 ni crear por ello una alerta de IA.

La API hoy acepta y persiste texto, similitud, puntuación de voz sintética, duración de proceso y `model_versions`; no tiene campo tipado de confianza de transcripción. En una etapa futura propongo añadir `transcription_status` (`ok`, `low_confidence`, `unavailable`) y `quality_reasons` al resultado interno, persistirlos en `audio_analyses` y devolverlos a la UI. Esto requiere actualizar los esquemas Pydantic con `extra="forbid"`, dominio/repositorios, tipos compartidos, migración de DB y vista del docente. En esta Fase 2/3.0 no se modifica ninguno de esos contratos ni `services/api`.

## Etapa 3.1 autorizada

La implementación mantiene los defaults globales y habilita Parakeet FP32 como proveedor seleccionable. La puerta de calidad registra baja confianza sin ejecutar otro motor; su calibración corresponde a salidas de Parakeet INT8 y no se considera validada para FP32. La cascada local a faster-whisper small ocurre solo ante errores de ejecución de Parakeet. La selección de proveedor local no exige `DEEPGRAM_API_KEY`.

Se revisó la precarga con cinco pruebas por modo usando sherpa-onnx 2.0.1 y FP32 revisión `5fcc0122fe87e8365e339e467af90c67b746218f`. El recognizer heredado logró 5/5, pero Python notificó posible deadlock por fork multihilo. Por precaución, RQ carga Parakeet en el hijo tras fork; `SimpleWorker` puede precargar en su proceso serial. Los tiempos y condiciones están en `services/ai/results/parakeet-fork-safety.json`.

## Cierre de Etapa 3.2

**Implementación y mediciones:** rama `feat/asr-parakeet-provider`; sin push. Defaults globales comprobados sin cambios: `ASR_PROVIDER=deepgram`, `ASR_FALLBACK_PROVIDER=none`, `SIMILARITY_BACKEND=torch`. No se cambiaron contratos API ni migraciones.

### Memoria, imagen y latencia

Con Docker cgroups en el host disponible (12.309.565.440 bytes RAM, 8 CPU visibles), el pico cgroup combinado FP32 + ONNX int8 fue 2.699.165.696 bytes con audio de 15 s y 2.812.870.656 bytes con audio de 30 s. Se construyeron al repetir y recortar P02_A1_base; no son dos grabaciones nativas. El tamaño de imagen sin pesos fue 3.012.124.371 bytes. JSON: `services/ai/results/phase3.2-memory-15s.json`, `phase3.2-memory-30s.json` y el tamaño de imagen en `phase3.2-image.json`.

Pipeline frío/caliente usa descarga por copia local, ejecución real de ASR/similitud y POST solo serializado localmente. A CPU 1: frío 20,28 s; 20 calientes p50 9,30 s, p90 11,43 s. Los tres límites CPU 1/2/3 y los RSS/picos están en `services/ai/results/phase3.2-latency-cpu{1,2,3}.json`. No son latencias de red a API/Storage reales.

### Elección del modo RQ

En una corrida de 50 trabajos con A (RQ Worker/fork): 192,74 s, 15,56 trabajos/min, un trabajo observado 3,529 s incluyendo la carga Parakeet del hijo y pico cgroup 3.839.369.216 bytes. B (SimpleWorker sin fork): 59,89 s, 50,09 trabajos/min, modelo cargado una vez y pico 4.528.955.392 bytes. B fue más rápido, pero el lote tuvo cola previa y no es A/B controlado. Timeout: ambos modos fallan el trabajo con timeout y aceptan el siguiente. Caída fatal: B reinició el contenedor pero dejó el trabajo `started`; A registró el trabajo interrumpido como retry programado. Como `worker.work(with_scheduler=False)` no ejecuta esos retries automáticamente, A también requiere habilitar/probar el scheduler o requeue operativo antes de declarar recuperación automática. Recomiendo A por aislamiento y preservación del trabajo; la limitación de reintento programado debe resolverse antes de producción. Datos: `services/ai/results/phase3.2-worker-modes.json`.

El pico observado en E2E compose con B fue 4.528.955.392 bytes; las pruebas de fallback que cargan simultáneamente ambos modelos deben tomarse de `services/ai/results/phase3.2-failure-probes.json`. La capacidad final para 1/2/3 procesos en el límite de RAM 75 % se encuentra en `services/ai/results/phase3.2-worker-capacity.json`.

### Repetición de P01/P02 y límites

Se repitieron 20 audios propios P01 y los 30 P02 con el proveedor integrado. P01 dio 92/520 ediciones (17,69 %) vs 90/520 (17,31 %) guardadas, +0,38 pp. P02 dio 168/770 (21,82 %) vs 171/770 (22,21 %), −0,39 pp. No se reajustó ningún umbral. Las 28 filas del otro artefacto incluyen además ocho audios de MediaSpeech; no se atribuyen a P01. P01 continúa como comparación de artefacto **no verificada** porque el resultado antiguo no registró revisión/hash. Datos: `services/ai/results/phase3.2-integrated-evaluation.json` y `phase3.2-evaluation-differences.json`.

E2E local con Docker Compose completó lotes de 1, 30 y 200; un 503 simulado generó retry y luego resultado. `/health` estaba limitado a loopback y Redis/API/storage mocks carecían de puertos publicados. Worker local arrancó sin `DEEPGRAM_API_KEY`. JSON: `services/ai/results/phase3.2-compose-e2e.json`.

Configuración de despliegue recomendada para el Compose actual: `ASR_PROVIDER=parakeet`, `ASR_FALLBACK_PROVIDER=faster-whisper`, `ASR_LOCAL_MODEL=small`, `PARAKEET_PRECISION=fp32`, `PARAKEET_NUM_THREADS=4`, `SIMILARITY_BACKEND=onnx-int8`, `WORKER_USE_SIMPLE_WORKER=false`, un proceso y directorio `/models/parakeet-fp32`. En la capacidad RQ, 1/2/3 procesos produjeron 13,64 / 14,59 / 6,89 trabajos/min; picos simultáneos agregados 4,70 / 5,51 / 7,65 GB. Los tres estuvieron por debajo del 75 % de RAM física medida (9,23 GB), pero el Compose actual publica un único puerto de health 8080, por eso recomiendo una réplica hasta adaptar ese mapeo. Deepgram queda desactivado sin clave en este perfil; el código permanece disponible. JSON: `services/ai/results/phase3.2-worker-capacity.json`.

La comparación de modo RQ medido indica que SimpleWorker fue más rápido en sus 50 trabajos (41,0/min frente a 13,64/min de RQ Worker/fork), pero una caída fatal del proceso dejó un trabajo `started`, sin recuperación automática pese al restart. RQ Worker/fork conserva el trabajo interrumpido como scheduled retry; la configuración actual desactiva scheduler (`with_scheduler=False`), así que tampoco se comprobó la reejecución automática. Elijo RQ Worker por aislamiento, pero habilitar y verificar recuperación de retry es una decisión operativa pendiente. Los tiempos por trabajo, RSS y timeout/restart constan en `phase3.2-worker-mode-a.json`, `phase3.2-worker-mode-b.json` y `phase3.2-timeout-restart.json`.
