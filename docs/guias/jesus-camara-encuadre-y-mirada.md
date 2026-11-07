# Jesús — Cámara: mirada con los ojos y encuadre de hombros y brazos

> Responsable: Jesús Limay. Complementa `jesus-disponibilidad.md`.

## El problema (probado a mano)

1. **Ojos sin mover la cabeza.** La mirada se calculaba solo con el giro de la
   cabeza (yaw/pitch de la matriz facial). Con la cabeza quieta se podía bajar la
   vista a un celular, y más aún con lentes, sin que se detectara nada.
2. **Cámara apuntando solo a la cara.** Si la cámara enfoca solo el rostro, un
   celular sostenido más abajo nunca entra en la imagen. El detector de objetos
   solo lo veía si se lo mostraba a la cámara.

## La solución: 100 % local, gratuita, sin servicios externos

| Pieza | Modelo | Peso extra | Licencia |
|---|---|---|---|
| Mirada con los ojos | `face_blendshapes.tflite`, que **ya viene dentro** de `face_landmarker.task` | **0 MB** | Apache-2.0 |
| Encuadre de hombros y brazos | MediaPipe Pose Landmarker **lite** (`pose_landmarker_lite.task`) | 5,8 MB | Apache-2.0 |

Todo corre en el navegador o en Electron con el mismo `@mediapipe/tasks-vision` que
ya usa el proyecto. Los modelos se sirven desde `public/mediapipe/`: no hay llamadas
a terceros, no hay costo por uso y no se envía ninguna imagen.

`pose_landmarker_lite.task` es el *float16* oficial de Google. Su sha256
(`59929e1d…0d574a`) queda fijado en `scripts/prepare-mediapipe.mjs`, y el build
falla si el archivo falta o no coincide.

## 1. Mirada con los ojos

Archivos: `detectores/vision-core.ts` (reglas puras), `detectores/vision.ts`,
`calibration.ts`, `pages/RendirExamen.tsx`.

- Se activa `outputFaceBlendshapes` en el mismo Face Landmarker. Se usan
  `eyeLookDown*`, `eyeLookIn*`, `eyeLookOut*` y `eyeBlink*`.
- `gaze_away` se dispara también si los ojos bajan (`eyes_down`) o se van a un lado
  (`eyes_side`), aunque el yaw esté en cero. `metadata.reason` dice cuál fue la
  causa: `head_yaw`, `head_pitch`, `eyes_down` o `eyes_side`.
- **Con lentes:** al mirar algo en las piernas, el párpado tapa el iris y
  `eyeLookDown` sube menos. Por eso también cuenta un párpado caído (`eyeBlink` ≥ 0,35
  sobre la línea base) junto con la mitad del umbral de `eyeLookDown`. Un parpadeo
  real dura menos de medio segundo y lo descarta el mínimo de 3 s del módulo.
- **Calibración:** los pasos "esquinas inferiores" miden cuánto baja la vista ese
  estudiante para leer el borde de *su* pantalla. El umbral queda 0,15 por encima,
  con un mínimo de 0,45 y un tope de 0,7. Las calibraciones guardadas antes de este
  cambio siguen cargando.
- Ajustes del módulo `gaze` (opcionales): `eye_gaze: false` apaga la regla;
  `eye_down_threshold` y `eye_side_threshold` (por defecto 0,45 y 0,55).

## 2. Encuadre de hombros y brazos

Archivos: `detectores/encuadre-core.ts` (reglas puras), `detectores/encuadre.ts`,
`components/ComprobacionEncuadre.tsx`, `supervision/encuadreSala.ts`,
`pages/SalaDeEspera.tsx`.

- **Antes del examen (bloquea):** en la sala de espera, el botón "Entrar al examen"
  no aparece hasta que la cámara muestre hombros y codos durante 2 s seguidos. El
  estudiante ve qué corregir, por ejemplo: *"Solo se ve tu cara. Aleja la cámara o
  inclina la pantalla hacia atrás hasta que se vean tus hombros."*
- **Durante el examen:** `DetectorEncuadre` mide dos veces por segundo. Si el mal
  encuadre dura más de 5 s, avisa al estudiante y registra **`framing_lost`** con
  el motivo y lo que se veía. Así, saltarse la sala no sirve de nada.
- Si el modelo no carga, **no bloquea**: se avisa y se puede entrar. Es el mismo
  criterio del proyecto: un modelo que falla no puede dejar a nadie sin rendir.
- Se enciende con los módulos `gaze` u `objects`. El nivel se configura con
  `framing_required` en cualquiera de los dos: `shoulders`, `elbows` (por defecto),
  `hands` u `off`.

### Evento nuevo `framing_lost`

Se agregó siguiendo exactamente el precedente de `prohibited_object`:

| Capa | Archivo |
|---|---|
| Base de datos | `supabase/migrations/20261107090000_framing_lost_event.sql` |
| API, dominio | `event.py`, `exam_session.py` (va con `gaze` u `objects`), `severity.py` (LOW; MEDIUM si dura ≥ 30 s), `alert.py` |
| Contratos | `event.schema.json`, `database.types.ts`, `examples/framing_lost.json` |
| Web | `lib/api.ts`, `lib/formato.ts`, `supervision/avisos.ts` |
| Escritorio | `renderer.ts`, `preload/types.d.ts` |

**Al integrar hay que aplicar la migración** (`supabase db push` o el flujo habitual);
sin ella, la base rechaza el evento.

## Verificado

- Web: `tsc -b`, eslint, 277 pruebas de vitest y `npm run build`.
- API: ruff, mypy y 1005 pruebas. Contratos: 12 ejemplos válidos.
- Escritorio: typecheck, lint y 59 pruebas.
- **Con los modelos reales en Chromium**, sobre una foto de dominio público
  (`astronaut` de scikit-image, NASA):

  | Encuadre | Resultado |
  |---|---|
  | Foto completa | `ok`: 2 hombros, 2 codos, 2 muñecas |
  | Recortada a la cara | `no_shoulders` |
  | Recortada hasta los hombros | `no_elbows` |

  Mirando a la cámara, `eyeLookDown` ≈ 0,14: no se marca. La pose tarda unos 50 ms
  por medición en CPU.

## Lo que falta medir

Los umbrales de los ojos (0,45 y 0,55) son un punto de partida razonable, **no un
valor medido**. No había fotos ni video de alguien mirando hacia abajo para
validarlos. Antes de la entrega hay que grabar con el equipo:

- 10 personas, con y sin lentes, mirando el celular en las piernas;
- 10 personas leyendo la parte baja de la pantalla.

Con eso se calculan accuracy y FPR (la meta SMART es FPR < 20 % por módulo) y se
ajustan los umbrales.
