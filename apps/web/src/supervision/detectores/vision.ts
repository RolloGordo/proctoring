/**
 * Detectores de visión. **Son plantillas: ninguno detecta nada todavía.**
 *
 * Esto es el sitio donde se enchufa MediaPipe (SPEC-005 y SPEC-007, Jesús). Lo
 * que ya está resuelto alrededor:
 *
 * - la cámara (`camara.ts`),
 * - agrupar fotogramas en un evento con duración (`seguimiento.ts`),
 * - mandarlo con reintentos (`emisor.ts`),
 * - los umbrales, que llegan de la configuración de la sesión.
 *
 * Lo único que falta es rellenar `observar`: mirar el fotograma y decir si la
 * condición se cumple **en este instante**. Nada de temporizadores ni de
 * contar eventos: de eso se encarga el seguimiento.
 *
 * ## Cómo enchufar un modelo
 *
 * ```ts
 * import { FaceLandmarker, FilesetResolver } from '@mediapipe/tasks-vision'
 *
 * async preparar() {
 *   const wasm = await FilesetResolver.forVisionTasks('/mediapipe/wasm')
 *   this.landmarker = await FaceLandmarker.createFromOptions(wasm, {
 *     baseOptions: { modelAssetPath: '/mediapipe/face_landmarker.task' },
 *     numFaces: 2,
 *     outputFacialTransformationMatrixes: true,
 *     runningMode: 'VIDEO'
 *   })
 * }
 * ```
 *
 * Los `.wasm` y el modelo van **servidos por la propia web**, no desde un CDN:
 * la ventana del examen corre en modo kiosco y no debería pedirle nada a un
 * tercero mientras alguien rinde.
 *
 * ## Qué guardar en `metadata`
 *
 * Los números medidos **y** los umbrales con los que se compararon. Es lo que
 * después sostiene el informe de accuracy y de FPR; sin ellos, un resultado no
 * se puede revisar ni calibrar.
 */

import type { Detector, Observacion, Veredicto } from '../tipos'

/** Umbrales que vienen de `session_modules.settings`. */
export interface AjustesMirada {
  /** Grados de giro de cabeza a partir de los cuales se considera fuera. */
  yaw_degrees?: number
  min_duration_ms?: number
}

export interface AjustesRostro {
  min_duration_ms?: number
}

export interface AjustesPersonaExtra {
  /** A partir de cuántos rostros se considera que hay alguien más. */
  min_faces?: number
}

/**
 * Mirada fuera de la pantalla (`gaze_away`).
 *
 * **El más difícil de los tres y el que más falsos positivos puede dar:** mirar
 * al teclado o pensar mirando al techo no es copiar. Conviene medirlo con
 * grabaciones reales antes de confiar en el umbral.
 */
export class DetectorMirada implements Detector {
  readonly nombre = 'mirada'
  readonly evento = 'gaze_away' as const
  readonly minimoMs: number
  private readonly yawLimite: number

  constructor(ajustes: AjustesMirada = {}) {
    this.minimoMs = ajustes.min_duration_ms ?? 3000
    this.yawLimite = ajustes.yaw_degrees ?? 25
  }

  async preparar(): Promise<void> {
    // TODO(SPEC-007, Jesús): cargar FaceLandmarker de MediaPipe.
  }

  observar(_observacion: Observacion): Veredicto {
    // TODO(SPEC-007, Jesús): sacar yaw y pitch de la matriz de transformación
    //   facial, o de la posición del iris. Devolver:
    //
    //   return {
    //     activa: Math.abs(yaw) > this.yawLimite,
    //     metadata: { source: 'mediapipe', yaw_deg: yaw, pitch_deg: pitch,
    //                 threshold_deg: this.yawLimite, min_duration_ms: this.minimoMs }
    //   }
    return { activa: false, metadata: { threshold_deg: this.yawLimite } }
  }
}

/** Rostro ausente (`face_absent`): no se detecta a nadie delante de la cámara. */
export class DetectorRostroAusente implements Detector {
  readonly nombre = 'rostro-ausente'
  readonly evento = 'face_absent' as const
  readonly minimoMs: number

  constructor(ajustes: AjustesRostro = {}) {
    this.minimoMs = ajustes.min_duration_ms ?? 5000
  }

  observar(_observacion: Observacion): Veredicto {
    // TODO(SPEC-007, Jesús): activa cuando el detector devuelve 0 rostros.
    //   metadata: { source: 'mediapipe', faces_detected: 0, min_duration_ms }
    return { activa: false }
  }
}

/**
 * Otra persona en cámara (`extra_person`).
 *
 * Instantáneo en el contrato, pero aquí también lleva un mínimo: alguien que
 * cruza por detrás un segundo no es una segunda persona rindiendo el examen.
 */
export class DetectorPersonaExtra implements Detector {
  readonly nombre = 'persona-extra'
  readonly evento = 'extra_person' as const
  readonly minimoMs = 2000
  private readonly minimoRostros: number

  constructor(ajustes: AjustesPersonaExtra = {}) {
    this.minimoRostros = ajustes.min_faces ?? 2
  }

  observar(_observacion: Observacion): Veredicto {
    // TODO(SPEC-007, Jesús): activa cuando el nº de rostros >= this.minimoRostros.
    //   metadata: { source: 'mediapipe', faces_detected: n }
    return { activa: false, metadata: { min_faces: this.minimoRostros } }
  }
}
