# Jesús — visión computacional

**Tu área:** rostro, mirada, persona adicional y verificación de identidad.
**SPEC:** 005 (identidad) y 007 (visión). **Además:** mantenimiento de la base.

Lee antes [`docs/guias/README.md`](README.md): cómo trabajar, la puerta de
calidad y las tres reglas que no se rompen.

---

## Lo que ya está hecho por ti

Esto **no** lo tienes que escribir. Está en `apps/web/src/supervision/`:

| Archivo | Qué resuelve |
|---|---|
| `camara.ts` | Abrir cámara, traducir errores, capturar un fotograma |
| `seguimiento.ts` | Convertir muchos fotogramas en **un evento** con duración |
| `emisor.ts` | Mandar el evento a la API con reintentos |
| `useSupervision.ts` | Encenderlo todo mientras el estudiante rinde |
| `detectores/vision.ts` | **Tus tres detectores, vacíos, esperándote** |

En la app de escritorio ya está el permiso de cámara (`src/main/permisos.ts`), así
que `getUserMedia` funciona dentro del kiosco.

**Tu trabajo es rellenar `observar()` en tres clases.** Nada más. Un detector
mira un fotograma y dice si la condición se cumple **ahora mismo**; no cuenta
tiempo, no decide si avisar y no habla con la API.

---

## Tarea J1 — Dataset de visión (4 h)

**Rama:** `feat/SPEC-007-dataset-vision`
**Carpeta (nueva):** `apps/web/spikes/vision/datasets/` — el vídeo **no** se sube

Graba a 3 o 4 personas del equipo, **con consentimiento escrito**, cubriendo:

| Situación | Para qué detector |
|---|---|
| Mirando a la pantalla, luz buena | el caso normal (son los falsos positivos) |
| Mirando a la pantalla, luz mala / a contraluz | robustez |
| Con lentes | robustez |
| Mirando al teclado | **el falso positivo más importante**: no es trampa |
| Mirando a un lado 5–10 s | `gaze_away` verdadero |
| Saliendo de cuadro | `face_absent` |
| Una segunda persona entrando | `extra_person` |
| Alguien que cruza por detrás 1 s | **falso positivo** de `extra_person` |
| Una foto de otra persona frente a la cámara | para la verificación facial |

Por cada clip, un `.txt` con los tramos etiquetados:

```
00:00-00:12  mirando_pantalla
00:12-00:19  mirando_lado
00:19-00:31  mirando_teclado
```

Y un `manifest.csv` con `id,archivo,persona,condicion,duracion_s,sha256` más un
`provenance.json`. Copia el formato de `services/ai/datasets/sp007_own/`: ya está
resuelto y así los dos datasets se parecen.

**Terminado cuando:** el manifiesto y la procedencia están en el repositorio, los
vídeos no, y otra persona puede verificar los hashes.

---

## Tarea J2 — Spike de MediaPipe (6 h)

**Rama:** `feat/SPEC-007-spike-vision`
**Carpeta:** `apps/web/spikes/vision/`

Una página suelta que abre la cámara y dibuja lo que detecta. **Todavía no toca
la aplicación**: es para ver si funciona y medir.

Candidato a evaluar: `@mediapipe/tasks-vision` con `FaceLandmarker`. Da los
puntos de la cara, el número de rostros y la matriz de transformación de la
cabeza, que es de donde sale el yaw.

```ts
const wasm = await FilesetResolver.forVisionTasks('/mediapipe/wasm')
const landmarker = await FaceLandmarker.createFromOptions(wasm, {
  baseOptions: { modelAssetPath: '/mediapipe/face_landmarker.task' },
  numFaces: 2,                                 // hace falta para extra_person
  outputFacialTransformationMatrixes: true,    // de aquí sale el yaw
  runningMode: 'VIDEO'
})
const resultado = landmarker.detectForVideo(video, performance.now())
```

> Los `.wasm` y el `.task` van en `apps/web/public/mediapipe/` (carpeta nueva), **no en un CDN**:
> la ventana del examen corre en kiosco y tiene la navegación atada a su propio
> origen. Si los pides a un CDN, no cargarán.

Lo que tienes que sacar de cada fotograma:

| Dato | De dónde | Para |
|---|---|---|
| nº de rostros | `resultado.faceLandmarks.length` | `face_absent` (0), `extra_person` (≥2) |
| yaw y pitch | `facialTransformationMatrixes[0]` | `gaze_away` |

**Y un script de evaluación** que corra sobre J1 y escriba
`apps/web/spikes/vision/results/evaluation.json` con **accuracy y FPR por
detector**. Mira `services/ai/spikes/evaluate.py` como referencia del formato.

**Terminado cuando:** hay un número de accuracy y de FPR para `gaze_away`,
`face_absent` y `extra_person`, medidos sobre tus clips, guardados en
`results/`, y el README del spike dice cómo reproducirlo.

> **Lo más difícil va a ser la mirada.** Mirar al teclado para escribir, o al
> techo para pensar, no es copiar. Si el FPR te sale alto, prueba a subir el
> `min_duration_ms` antes que el ángulo: la mayoría de las miradas legítimas son
> cortas.

---

## Tarea J3 — Enchufar los detectores (4 h)

**Rama:** `feat/SPEC-007-detectores-vision`
**Archivo:** `apps/web/src/supervision/detectores/vision.ts`

Ahora sí, mover lo que funciona al detector real. Tres clases ya escritas, cada
una con un `TODO` donde va tu código:

```ts
export class DetectorMirada implements Detector {
  private landmarker?: FaceLandmarker

  async preparar(): Promise<void> {
    const wasm = await FilesetResolver.forVisionTasks('/mediapipe/wasm')
    this.landmarker = await FaceLandmarker.createFromOptions(wasm, { /* ... */ })
  }

  observar({ video, ahoraMs }: Observacion): Veredicto {
    if (!this.landmarker || !video) return { activa: false }
    const r = this.landmarker.detectForVideo(video, ahoraMs)
    const yaw = yawDesdeMatriz(r.facialTransformationMatrixes[0])
    return {
      activa: Math.abs(yaw) > this.yawLimite,
      metadata: {
        source: 'mediapipe',
        yaw_deg: yaw,
        threshold_deg: this.yawLimite,
        min_duration_ms: this.minimoMs
      }
    }
  }
}
```

Tres cosas que no se negocian:

1. **`observar` devuelve si la condición se cumple ahora.** No cuentes segundos:
   de eso se encarga `SeguimientoCondicion`, que ya tolera el parpadeo y tiene 14
   pruebas.
2. **Los umbrales vienen del constructor**, que los recibe de la sesión. No los
   escribas fijos: el docente elige el nivel de supervisión y cada examen puede
   tener los suyos.
3. **En `metadata` van los números medidos *y* los umbrales usados.** Es lo que
   sostiene el informe de accuracy. Pon siempre `source`.

**Terminado cuando:** `npm test --prefix apps/web` pasa, y rindiendo un examen de
prueba aparecen eventos `gaze_away` / `face_absent` / `extra_person` en la
pantalla del docente.

---

## Tarea J4 — Verificación de identidad (8 h)

**Rama:** `feat/SPEC-005-verificacion-facial`
**Archivo:** `services/ai/tasks.py`, función `verify_face`

La API ya tiene todo el camino montado. El flujo es:

1. El estudiante registra su cara una vez → `POST /api/v1/me/reference-face`
2. Al entrar al examen manda una captura → `POST /api/v1/exam/{id}/identity/check`
3. La API encola `tasks.verify_face` → **aquí entras tú**
4. Pides el trabajo: `GET /internal/face-jobs/{participant_id}?capture_path=...`
   → te da las dos rutas, el bucket de cada una, el umbral y el embedding de
   referencia si ya se calculó
5. Comparas y devuelves la similitud a
   `POST /internal/sessions/{id}/students/{id}/identity-result`

**Tú solo mides.** El umbral lo aplica la API, con el de la sesión. Si no detectas
una cara, o detectas varias, manda `inconclusive: true`: **no es lo mismo que "no
coincide"**, y el docente lo distingue al revisar.

Antes de integrarlo, un spike offline en `services/ai/spikes/face_verify.py` (nuevo) con:

- pares **reales** (la misma persona en dos momentos) e **impostores** (personas
  distintas), de tu dataset J1,
- la curva **FAR/FRR** y el umbral que recomiendas (hoy está en 0.45),
- la **latencia P90 en CPU**, que tiene que ser **< 500 ms**: hay alguien
  esperando en pantalla.

Candidato a evaluar: InsightFace / ArcFace. **Pruébalo antes de comprometerte**:
si no cabe en el presupuesto de latencia en CPU, busca uno más pequeño. La meta
manda sobre el modelo.

**Terminado cuando:** hay una tabla de FAR/FRR, un umbral recomendado con su
justificación, la latencia P90 medida, y un estudiante de prueba pasa de
`pending` a `verified` solo.

---

## Tarea J5 — Auditoría de RLS (4 h)

**Rama:** `fix/SPEC-006-auditoria-rls`
**Carpeta:** `supabase/migrations/`

La API usa la *service role key* y **omite RLS** ([ADR-0010](../adr/0010-autenticacion-en-la-api-no-en-rls.md)),
así que RLS protege el caso en que alguien vaya **directo a Supabase** con la
clave pública desde el navegador.

Escribe un script que, con la clave **publicable** (no la de servicio) y el token
de un estudiante, intente leer lo que no debería:

| Intento | Debe |
|---|---|
| Leer `events` de otro estudiante | devolver 0 filas |
| Leer `answers` de otro | 0 filas |
| Leer `questions` con `is_correct` | 0 filas o sin esa columna |
| Leer `decisions` | 0 filas |
| Escribir en `events` a nombre de otro | fallar |

Cualquier hallazgo se corrige con una **migración nueva** en
`supabase/migrations/`, con nombre `<fecha>_<qué_arregla>.sql`. **Nunca edites
nada en el panel de Supabase**: lo que no está en una migración no existe para el
resto del equipo.

---

## Orden recomendado

```
J1 (dataset) ──► J2 (spike + medir) ──► J3 (enchufar)
                                   └──► J4 (identidad)
J5 cuando quieras: no depende de nada
```

J1 y J2 se pueden empezar **hoy**, en el navegador, sin esperar a nadie.
