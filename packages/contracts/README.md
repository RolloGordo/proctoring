# `packages/contracts` — Contrato compartido del evento

**Responsable:** Silva Vega, Héctor
**Backlog:** EN-003

[`event.schema.json`](event.schema.json) es la **única fuente de verdad** del evento de proctoring.
Lo consumen cuatro sitios:

| Quién | Para qué |
|---|---|
| `apps/desktop` (Rider) | construye el cuerpo del `POST /api/v1/events` |
| `apps/web/spikes/vision` (Jesús) | lo mismo, desde el navegador |
| `services/api` (Héctor) | lo valida con Pydantic y lo persiste en la tabla `events` |
| `services/ai` (Pierreluiggi) | lee el evento encolado para analizar el audio |

Si cambia este archivo, cambian **en el mismo pull request** los cuatro consumidores. El CI valida
que todos los ejemplos sigan cumpliendo el esquema.

## Forma del evento

```jsonc
{
  "session_id": "uuid",            // obligatorio
  "student_id": "uuid",            // obligatorio
  "question_id": "uuid | null",    // opcional, por defecto null
  "event_type": "focus_lost",      // obligatorio, uno del enum
  "started_at": "2026-10-03T14:21:05.120Z",  // obligatorio, ISO-8601 en UTC
  "duration_ms": 8400,             // opcional, por defecto 0, entero >= 0
  "metadata": {},                  // opcional, por defecto {}
  "evidence_path": "ruta | null"   // opcional, por defecto null
}
```

`additionalProperties: false`: una clave que no esté en la lista hace fallar la validación. Es
intencional — así un error de tipeo en el cliente se ve de inmediato en lugar de perderse.

### Dos reglas que el esquema **no** expresa

Las valida el dominio de la API y responden **400**, no 422:

1. `question_id` es **obligatorio** para `speech_detected` y `gaze_away`. Sin la pregunta en curso
   no hay con qué comparar la transcripción, que es el núcleo de la detección de IA por voz.
2. `started_at` tiene que traer zona horaria. Una marca de tiempo sin zona se rechaza.

> **422 vs 400:** 422 es "esto no cumple el contrato" (lo rechaza Pydantic antes de llegar al
> dominio). 400 es "cumple el contrato pero viola una regla de negocio".

### Un evento, no uno por frame

`duration_ms` existe porque las detecciones con duración (`focus_lost`, `gaze_away`, `face_absent`,
`screen_share`) emiten **un solo evento al cerrarse la condición**, con cuánto duró. Emitir uno por
frame multiplica los falsos positivos y revienta la meta de FPR < 20 %. Cada cliente necesita un
temporizador por condición (histéresis).

Los instantáneos (`extra_display`, `suspicious_process`, `identity_check`) van con `duration_ms: 0`.

## Ejemplos

Hay uno válido por cada `event_type` en [`examples/`](examples/). Se usan como cuerpo de referencia
en la app, en el spike de visión y en las pruebas de integración de la API.

| `event_type` | Ejemplo | Quién lo emite | `metadata` esperada |
|---|---|---|---|
| `focus_lost` | [focus_lost.json](examples/focus_lost.json) | Electron `main` | `source`, `trigger`, `returned` |
| `gaze_away` | [gaze_away.json](examples/gaze_away.json) | MediaPipe (renderer) | `yaw_deg`, `pitch_deg`, `threshold_deg`, `min_duration_ms` |
| `face_absent` | [face_absent.json](examples/face_absent.json) | MediaPipe (renderer) | `faces_detected`, `min_duration_ms` |
| `extra_person` | [extra_person.json](examples/extra_person.json) | MediaPipe (renderer) | `faces_detected` |
| `extra_display` | [extra_display.json](examples/extra_display.json) | Electron `screen` | `display_count`, `displays[]`, `detected_on` |
| `suspicious_process` | [suspicious_process.json](examples/suspicious_process.json) | Electron + `ps-list` | `process_name`, `pid`, `category` |
| `screen_share` | [screen_share.json](examples/screen_share.json) | Electron `main` | `detected_by`, `process_name` |
| `speech_detected` | [speech_detected.json](examples/speech_detected.json) | Silero VAD (renderer) | `sample_rate`, `speech_ratio` |
| `identity_check` | [identity_check.json](examples/identity_check.json) | API + InsightFace | `result`, `similarity`, `threshold`, `latency_ms` |

`metadata` es de forma libre a propósito (`additionalProperties: true`): cada detección guarda sus
umbrales y sus números, y eso es lo que después sostiene el informe de accuracy y de FPR. Pon
siempre `source` para saber qué lo generó.

## `evidence_path`, nunca el archivo

El evento lleva **la ruta**, no el contenido. El cliente sube la captura o el fragmento de audio
**directo a Storage** con una URL firmada que entrega `POST /api/v1/evidence/upload-url`, y aquí
manda solo:

```
{session_id}/{student_id}/{uuid}.{jpg|png|webp|webm|wav}
```

Buckets privados ya creados en Supabase: `evidences` (imágenes, 2 MB), `audio-segments` (audio,
5 MB), `reference-faces` (rostro de referencia, 2 MB). Ver
[`supabase/README.md`](../../supabase/README.md).

Nunca viaja video continuo. Ver
[ADR-0004](../../docs/adr/0004-deteccion-liviana-cliente-sin-video-continuo.md).

## Correspondencia con la base de datos

Las ocho claves del contrato son las ocho columnas de la tabla `events`, con los mismos nombres. El
`id` y el `created_at` los pone PostgreSQL; la respuesta del `POST` devuelve el `id` generado y la
`severity` calculada.

El enum `event_type` del esquema y el tipo `public.event_type` de PostgreSQL tienen **exactamente**
los mismos nueve valores. Si se añade uno, hay que tocar los dos sitios y crear una migración nueva.

## Validar

```bash
python packages/contracts/validate.py
```

Comprueba tres cosas: que el esquema sea un JSON Schema válido, que cada ejemplo lo cumpla, y que
no falte ningún `event_type` del enum sin su ejemplo. Lo corre el CI en el job `contracts`.

## Tipos de la base de datos

[`database.types.ts`](database.types.ts) tiene los tipos TypeScript generados desde el esquema
**real** de Supabase: las 15 tablas con sus `Row`, `Insert`, `Update`, las relaciones y los 9 enums.
Lo usan `apps/web` y `apps/desktop`:

```ts
import { createClient } from '@supabase/supabase-js';
import type { Database } from '@proctoring/contracts/database.types';

const supabase = createClient<Database>(url, publishableKey);
```

**Está generado, no se edita a mano.** Después de cada migración hay que regenerarlo:

```bash
npx supabase gen types typescript --project-id uzuysjmymvtpoxfrdxnm > packages/contracts/database.types.ts
```

Dos cosas que conviene saber al usarlo:

- `answers` cuelga de `participant_id`, no de `session_id` ni `student_id`. Para llegar a las
  respuestas de un estudiante hay que pasar por `session_participants`.
- `questions` y `question_options` **no tienen política de lectura para el estudiante**, y
  `question_options.is_correct` está en la misma tabla. El estudiante recibe las preguntas por la
  API, que las sirve con service role y quita las respuestas correctas. No intentes leerlas
  directo desde el cliente: RLS te va a devolver vacío, y es a propósito.
