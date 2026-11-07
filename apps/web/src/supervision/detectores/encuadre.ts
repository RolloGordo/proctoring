/**
 * Encuadre de la cámara con MediaPipe Pose Landmarker lite (Jesús Limay).
 *
 * - Antes del examen, `medirEncuadre` alimenta la comprobación de la sala de
 *   espera, que no deja entrar hasta que se vean hombros y brazos.
 * - Durante el examen, `DetectorEncuadre` emite `framing_lost` si el
 *   estudiante vuelve a apuntar la cámara solo a su cara.
 *
 * Autónomo: el modelo (5,8 MB, Apache-2.0) se sirve desde
 * `/mediapipe/pose_landmarker_lite.task`, igual que los demás. No llama a
 * ningún servicio externo, no guarda imágenes y no identifica a nadie.
 */
import type { PoseLandmarker } from '@mediapipe/tasks-vision'
import type { Detector, Observacion, Veredicto } from '../tipos'
import {
  evaluarEncuadre,
  nivelDe,
  type NivelEncuadre,
  type ResultadoEncuadre
} from './encuadre-core'

export interface AjustesEncuadre {
  /** Qué tiene que verse. Por defecto `elbows`. */
  framing_required?: NivelEncuadre
  /** Cuánto tiene que durar el mal encuadre para registrarse. */
  framing_min_duration_ms?: number
}

const MODELO = '/mediapipe/pose_landmarker_lite.task'
/**
 * La pose cambia despacio: mirarla dos veces por segundo basta y deja la CPU
 * para la cara y los objetos, que corren cada 125 y 250 ms.
 */
const INTERVALO_INFERENCIA_MS = 500

let instancia: PoseLandmarker | undefined
let preparando: Promise<void> | undefined

/** Carga el modelo una vez y lo comparten la sala de espera y el examen. */
export async function motorPose(): Promise<void> {
  if (instancia) return
  if (preparando) return preparando
  preparando = (async () => {
    const { FilesetResolver, PoseLandmarker } = await import('@mediapipe/tasks-vision')
    const wasm = await FilesetResolver.forVisionTasks('/mediapipe/wasm')
    instancia = await PoseLandmarker.createFromOptions(wasm, {
      baseOptions: { modelAssetPath: MODELO },
      runningMode: 'VIDEO',
      numPoses: 1
    })
  })()
  try {
    await preparando
  } finally {
    preparando = undefined
  }
}

function inferir(video: HTMLVideoElement, nivel: NivelEncuadre): ResultadoEncuadre | null {
  if (!instancia || video.readyState < 2 || !video.videoWidth) return null
  // performance.now() es monótono: MediaPipe lo exige en modo VIDEO, también
  // cuando la sala de espera y el examen usan la misma instancia.
  const resultado = instancia.detectForVideo(video, performance.now())
  return evaluarEncuadre(resultado.landmarks, nivel)
}

/** Una medición suelta, para la comprobación de la sala de espera. */
export async function medirEncuadre(
  video: HTMLVideoElement,
  nivel: NivelEncuadre = 'elbows'
): Promise<ResultadoEncuadre | null> {
  await motorPose()
  return inferir(video, nivel)
}

export class DetectorEncuadre implements Detector {
  readonly nombre = 'encuadre'
  readonly evento = 'framing_lost' as const
  readonly minimoMs: number
  readonly nivel: NivelEncuadre
  private ultimaInferencia = -Infinity
  private ultimo: Veredicto = {
    activa: false,
    metadata: { source: 'mediapipe-pose', available: false }
  }

  constructor(ajustes: AjustesEncuadre = {}) {
    this.nivel = nivelDe(ajustes.framing_required)
    // 5 s: tomar agua o estirarse no es mal encuadre; volver a apuntar la
    // cámara a la cara para el resto del examen, sí.
    this.minimoMs = ajustes.framing_min_duration_ms ?? 5000
  }

  async preparar(): Promise<void> {
    await motorPose()
  }

  diagnostico(): string {
    return `pose ${MODELO} cargado=${instancia !== undefined}`
  }

  observar({ video, ahoraMs }: Observacion): Veredicto {
    if (!video) return { activa: false, metadata: { source: 'mediapipe-pose', available: false } }
    if (ahoraMs - this.ultimaInferencia < INTERVALO_INFERENCIA_MS) return this.ultimo
    this.ultimaInferencia = ahoraMs
    const r = inferir(video, this.nivel)
    this.ultimo = r
      ? {
          // `no_person` ya lo cubre `face_absent`: no se cuenta dos veces.
          activa: !r.ok && r.motivo !== 'no_person',
          metadata: {
            source: 'mediapipe-pose',
            reason: r.motivo,
            framing_required: this.nivel,
            ...r.medidas,
            min_duration_ms: this.minimoMs
          }
        }
      : { activa: false, metadata: { source: 'mediapipe-pose', available: false } }
    return this.ultimo
  }

  detener(): void {
    // La instancia se mantiene caliente para el siguiente examen, como objetos.ts.
  }
}
