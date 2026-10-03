# `apps/web/spikes/vision` — Spike de visión por computadora

**Responsable:** Limay Capristan, Jesús
**Backlog:** EN-008 / TA-00x (mirada, rostro ausente, persona adicional)

Esta carpeta está preparada pero **sin implementar**: es tuya.

## Objetivo

Demostrar, con código que corre en el navegador, las tres detecciones de visión. Todo esto va en
el **cliente** (es detección liviana) usando MediaPipe sobre el `<video>` de la cámara. **No se
envía video continuo**: solo el evento y, como mucho, una captura del `canvas` en el momento.

| Detección | Regla | `event_type` |
|---|---|---|
| Rostro ausente | sin rostro durante más de **5 s** | `face_absent` |
| Persona adicional | más de un rostro en cuadro | `extra_person` |
| Mirada fuera de pantalla | cabeza girada más de **25°** durante más de **3 s** | `gaze_away` |

El presupuesto es: alerta al docente en **menos de 5 s**. Y la meta de calidad es accuracy ≥ 80 %
con FPR < 20 %, así que los umbrales de arriba son un punto de partida que **tienes que validar
con datos**, no un dogma.

## Montaje

```bash
cd apps/web/spikes/vision
npm create vite@latest . -- --template vanilla-ts
npm install @mediapipe/tasks-vision
npm run dev
```

## Face Landmarker de MediaPipe

```ts
import { FaceLandmarker, FilesetResolver } from '@mediapipe/tasks-vision';

const vision = await FilesetResolver.forVisionTasks(
  'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision/wasm'
);
const landmarker = await FaceLandmarker.createFromOptions(vision, {
  baseOptions: {
    modelAssetPath:
      'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
    delegate: 'GPU',
  },
  runningMode: 'VIDEO',
  numFaces: 2,                        // necesario para detectar persona adicional
  outputFacialTransformationMatrixes: true,  // necesario para el angulo de la cabeza
});
```

En cada frame: `landmarker.detectForVideo(video, performance.now())`.

- `result.faceLandmarks.length` → 0 = rostro ausente, 2 o más = persona adicional.
- `result.facialTransformationMatrixes[0]` → de esa matriz 4x4 sacas yaw y pitch
  (rotación en Y y en X). El yaw es el que te dice si miró a un costado.

## Lo importante: histéresis

La detección frame a frame **parpadea**. Un `face_absent` por cada frame sin rostro genera cientos
de eventos falsos y te revienta el FPR. Implementa un temporizador por condición:

```
condicion verdadera de forma continua >= umbral de tiempo  ->  emite UN evento con duration_ms
condicion vuelve a falsa                                   ->  cierra y reinicia el temporizador
```

Es el mismo patrón que Rider necesita para `focus_lost`. Pónganse de acuerdo y compartan la
utilidad si pueden.

## Captura de evidencia

Al emitir un evento, dibuja el frame en un `canvas` y saca `canvas.toBlob(..., 'image/jpeg', 0.7)`.
En el spike basta con descargarla localmente. En la app real la captura se sube **directo a
Storage** con una URL firmada que da la API, y en el evento solo va el `evidence_path`.

## Envío del evento

Contrato en [`packages/contracts`](../../../../packages/contracts/), con un ejemplo por tipo en
`examples/`.

```
POST http://localhost:8000/api/v1/events
```

Ojo: `gaze_away` **exige** `question_id` (lo valida el dominio de la API y devuelve 400 si falta).

## Criterios de aceptación

- [ ] `npm run dev` abre la cámara y dibuja los landmarks en vivo.
- [ ] Taparse la cámara 6 s genera **un** `face_absent` con `duration_ms` ≈ 6000.
- [ ] Que entre una segunda persona genera `extra_person`.
- [ ] Girar la cabeza unos 30° durante 4 s genera **un** `gaze_away`; un giro rápido de 1 s **no**.
- [ ] Se guarda una captura JPEG por evento.
- [ ] Tabla con los umbrales probados y cuántos falsos positivos dio cada uno (esto es lo que
      demuestra la meta de FPR < 20 %).

## Evidencia para la semana

Video de la cámara con los landmarks y los eventos apareciendo en consola, más la tabla de
umbrales. Guárdalo en `docs/evidencias/semana-05/jesus/`.
