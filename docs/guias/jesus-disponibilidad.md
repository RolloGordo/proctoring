# Jesús — Cámara autónoma y atributo de Disponibilidad

> Responsable: Jesús Limay · Atributo de calidad: **Disponibilidad**
> («arranques en frío, recuperación, qué pasa si se cae un servicio»).

## Qué se cambió

| Archivo | Qué hace |
|---|---|
| `services/ai/vision/` | **API de imagen propia**: verificación facial con YuNet + SFace int8 de OpenCV Zoo (MIT + Apache 2.0, ~10 MB), sin servicios externos |
| `services/ai/vision/modelos/` | Los dos `.onnx` versionados + `PROCEDENCIA.json` con tamaño, `sha256`, origen y licencia |
| `services/ai/face_pipeline.py` | Elige el motor con `FACE_ENGINE`; `precalentar()`; recalcula la referencia si el embedding guardado es de otro motor |
| `services/ai/tasks.py` | `model_version` del resultado sale del motor realmente usado |
| `services/ai/worker_stub.py` | Precalienta el motor facial al arrancar y lo reporta en `/salud` (`face_model`) |
| `services/ai/Dockerfile` | Copia `vision/` (con los modelos) dentro de la imagen |
| `services/ai/tests/test_vision_opencv.py` | 16 pruebas: integridad de modelos, selección de motor, cambio de motor, precalentado |
| `apps/web/src/supervision/reconexionCamara.ts` | Reintento automático de cámara al reconectarla (`devicechange`) |
| `apps/web/src/supervision/useSupervision.ts` | Usa la reconexión automática, con tope de 10 por examen; el botón manual sigue igual |
| `apps/web/src/supervision/reconexionCamara.test.ts` | 6 pruebas de la reconexión |
| `.github/workflows/mantener-despierto.yml` | Sondea `/health` cada 10 min en horario de examen para que Render no duerma la API |
| `.gitattributes` | `*.onnx`, `*.task`, `*.tflite` como binarios |
| `.gitignore` | Excepción para versionar `services/ai/vision/modelos/*.onnx` (el repo ignora todos los `.onnx`) |

Nada cambia de comportamiento por defecto en la verificación facial: `FACE_ENGINE`
vale `insightface` si no se define. Se activa el motor nuevo cuando esté calibrado.

## Activar la API de imagen propia

1. Calibrar el umbral con pares de fotos propios (SFace mide en otra escala que
   ArcFace; OpenCV propone ~0,363 de coseno como punto de partida, no como valor
   final). `spikes/face_verify.py` ya usa `embedding_from_bytes`, así que respeta
   `FACE_ENGINE` (formato del manifiesto en `spikes/face_verify_README.md`):

   ```bash
   cd services/ai
   uv sync --extra face
   FACE_ENGINE=insightface uv run python -m spikes.face_verify pares.csv --output results/face_verify_insightface.json
   FACE_ENGINE=opencv      uv run python -m spikes.face_verify pares.csv --output results/face_verify_opencv.json
   ```

2. Actualizar `similarity_threshold` del módulo `face_verification` en
   `DEFAULT_MODULE_SETTINGS` (API) con el valor medido.
3. En el despliegue del worker, definir `FACE_ENGINE=opencv`.
4. Comprobar `GET /salud` del worker: `"face_model": {"status": "ready", "version": "opencv/..."}`.

Las referencias ya guardadas con InsightFace (512 valores) se recalculan solas desde
la foto de referencia la primera vez que se comparan con SFace (128 valores), y la
API guarda la nueva.

Cuando las métricas lo respalden, el extra `face` puede quedarse solo con
`opencv-python-headless` y `numpy` (sin `insightface` ni `build-essential`), lo que
aligera la imagen. Eso exige regenerar `uv.lock`, por eso no se hizo aquí.

## Escenarios de disponibilidad

| # | Escenario | Medida | Estado |
|---|---|---|---|
| 1 | Arranque en frío del worker | Verificación lista ≤ 60 s; 0 descargas de modelo | Hecho con `FACE_ENGINE=opencv` + precalentado |
| 2 | Arranque en frío del cliente | Detectores listos ≤ 15 s | Ya existía (`arranque.ts`) |
| 3 | Cae el worker en pleno examen | 0 exámenes interrumpidos | Ya existía (cola Redis); ahora `/salud` muestra el modelo |
| 4 | Cae la API o la red | 0 eventos perdidos en cortes ≤ 5 min | Parcial: cola en memoria (ver pendientes) |
| 5 | Se desconecta la cámara | Detección ≤ 4 s; vuelve sola al reconectar | Hecho: reconexión automática |
| 6 | Un modelo no carga | 100 % de fallos visibles | Hecho: `verificar_modelos()` con `sha256` |
| — | La API se duerme en Render | Sin arranque en frío en horario de examen | Hecho: `mantener-despierto.yml` (definir `API_HEALTH_URL`) |

## Pendiente

- **Cola del emisor en IndexedDB** (`emisor.ts`): hoy vive en memoria y se pierde si la
  ventana se recarga. Las señales llevan capturas y audio, así que hay que diseñarlo
  con cuidado (blobs, tamaño, token caducado).
- **`/health/ready` en la API** que compruebe Supabase y Redis. Es código de Héctor:
  coordinarlo con él.

## Cómo demostrar cada escenario

| Escenario | Prueba manual | Evidencia |
|---|---|---|
| 1 | Reiniciar el worker sin red de salida y pedir una verificación | Log `Motor facial listo (...) en N ms` y resultado |
| 3 | Detener el worker 3 min con un examen en curso | Examen terminado; trabajos procesados al volver |
| 4 | Modo avión 2 min en Electron | Eventos completos en la base |
| 5 | Desenchufar y volver a enchufar la webcam | Aviso ≤ 4 s y supervisión de vuelta sin pulsar nada |
| 6 | Truncar un `.onnx` y correr `pytest tests/test_vision_opencv.py` | Prueba roja con mensaje claro |
