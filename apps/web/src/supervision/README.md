# `supervision/` — detección en el cliente

Esta carpeta es el **andamiaje** de la detección que corre en el navegador del
estudiante. Está hecha para que quien escriba un detector solo tenga que resolver
su problema: ni la cámara, ni los eventos, ni los reintentos.

> **La misma web corre dentro de la app de escritorio.** Lo que se escriba aquí
> funciona igual en el navegador (para probar) y dentro del kiosco de Electron
> (durante un examen real).

## Qué hay resuelto

| Archivo | Qué hace |
|---|---|
| `camara.ts` | Abre cámara y micrófono, traduce los errores a algo accionable, captura un fotograma |
| `seguimiento.ts` | Convierte una condición de muchos fotogramas en **un solo evento** con duración |
| `emisor.ts` | Cola con reintentos hacia `POST /api/v1/events` |
| `useSupervision.ts` | Junta todo y lo enciende mientras el estudiante rinde |
| `tipos.ts` | El contrato que cumple un detector |
| `detectores/` | **Plantillas vacías**: aquí va el trabajo |

## Qué falta: rellenar `observar`

Un detector dice si la condición se cumple **en este instante**. Nada más. No
cuenta tiempo, no decide si avisar y no habla con la API.

```ts
observar({ video, ahoraMs }: Observacion): Veredicto {
  const rostros = this.landmarker.detectForVideo(video, ahoraMs)
  return {
    activa: rostros.faceLandmarks.length === 0,
    metadata: { source: 'mediapipe', faces_detected: rostros.faceLandmarks.length }
  }
}
```

### Por qué no se emite un evento por fotograma

Es la regla del contrato, y es lo que decide si se cumple la meta de **FPR < 20 %**:

> Las detecciones con duración emiten **un solo evento al cerrarse la condición**,
> con cuánto duró. Emitir uno por fotograma multiplica los falsos positivos.

De eso se encarga `SeguimientoCondicion`, que además **tolera el parpadeo**: un
fotograma suelto sin rostro no parte una ausencia de 20 segundos en quince
eventos cortos. Tiene 14 pruebas; si cambias su comportamiento, se vuelven rojas.

### Qué poner en `metadata`

Los números medidos **y los umbrales con los que se compararon**:

```json
{ "source": "mediapipe", "yaw_deg": 31.2, "threshold_deg": 25, "min_duration_ms": 3000 }
```

Es lo que después sostiene el informe de accuracy y de FPR. Un resultado sin los
parámetros con los que se obtuvo no se puede revisar ni calibrar.

### Los umbrales no se escriben fijos

Llegan de `session_modules.settings`, que viaja con la sesión. Los de hoy están en
`DEFAULT_MODULE_SETTINGS` (en la API) y son **un punto de partida razonado, no
medido**: calibrarlos con datos reales es parte del trabajo.

| Módulo | Umbral actual |
|---|---|
| `gaze` | `yaw_degrees: 25`, `min_duration_ms: 3000` |
| `extra_person` | `min_faces: 2` |
| `face_verification` | `similarity_threshold: 0.45` |
| `ai_voice` | `similarity_threshold: 0.6`, `synthetic_threshold: 0.5` |

## Enchufar un detector

```ts
const detectores = useMemo(
  () => [new DetectorMirada(modules.gaze), new DetectorRostroAusente(modules.face_absent)],
  [modules]
)
const estado = useSupervision({ sessionId, studentId, questionId, token, detectores })
```

`useSupervision` ya hace lo demás: si un modelo no carga, lo descarta y sigue con
los otros; si la cámara falla, **el examen continúa** y se avisa. Un permiso
denegado no puede dejar a nadie sin rendir.

## Los modelos se sirven desde la propia web

Los `.wasm` y los `.task` de MediaPipe van en `public/`, no en un CDN. La ventana
del examen corre en modo kiosco y no debería pedirle nada a un tercero mientras
alguien rinde. Además, la app de escritorio ata la navegación a su propio origen.

## El audio es distinto

`speech_detected` no basta con emitirlo: hay que **subir el fragmento** o el
worker no tendrá nada que transcribir.

1. `POST /api/v1/evidence/upload-url` con `kind: "audio"` → URL firmada
2. subir el fragmento **directo a Storage**
3. mandar el evento con `evidence_path`

El audio nunca pasa por la API ([ADR-0004](../../../../docs/adr/0004-deteccion-liviana-cliente-sin-video-continuo.md)).
Y solo los fragmentos **con habla**: el micrófono continuo son cientos de megas y,
sobre todo, es grabar a alguien en su casa durante hora y media.

## La regla que no se toca

`speech_detected` nace siempre con severidad **baja**. Hablar en voz alta es
legítimo: leer la pregunta para concentrarse es lo que hace mucha gente. Solo la
API puede escalarlo, y solo si se cumplen **las dos** condiciones (parecido al
enunciado **y** segunda voz sintética). No lo decidas en el cliente.

## Probar sin cámara

`seguimiento.ts` es puro: recibe `true`/`false` y una hora. Se prueba entero sin
navegador, y es donde conviene poner las pruebas de un detector nuevo que tenga
lógica temporal.

```bash
npm test --prefix apps/web
```
