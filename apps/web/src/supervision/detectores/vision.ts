/** Detectores de SPEC-007. Sin grabación continua ni eventos por fotograma. */
import { FaceLandmarker, FilesetResolver } from '@mediapipe/tasks-vision'
import type { Detector, Observacion, Veredicto } from '../tipos'
import { angulosDesdeMatriz, reglasVision } from './vision-core'

export interface AjustesMirada {
  yaw_degrees?: number
  min_duration_ms?: number
}
export interface AjustesRostro { min_duration_ms?: number }
export interface AjustesPersonaExtra {
  min_faces?: number
  min_duration_ms?: number
}

interface Medicion {
  caras: number
  yaw: number | null
  pitch: number | null
}

/** MediaPipe se prepara una sola vez y se comparte para no triplicar la inferencia. */
let preparando: Promise<FaceLandmarker> | undefined
let instancia: FaceLandmarker | undefined
let ultima: { video: HTMLVideoElement; frame: number; medicion: Medicion } | undefined

async function motor(): Promise<void> {
  if (!preparando) {
    preparando = (async () => {
      const wasm = await FilesetResolver.forVisionTasks('/mediapipe/wasm')
      const modelo = await FaceLandmarker.createFromOptions(wasm, {
        baseOptions: { modelAssetPath: '/mediapipe/face_landmarker.task' },
        numFaces: 2,
        outputFacialTransformationMatrixes: true,
        runningMode: 'VIDEO'
      })
      instancia = modelo
      return modelo
    })().catch((error: unknown) => {
      preparando = undefined
      throw error
    })
  }
  await preparando
}

function medicionDe({ video, ahoraMs }: Observacion): Medicion | null {
  if (!video || !instancia || video.readyState < 2 || !video.videoWidth) return null
  // AhoraMs viene de Date.now() en la aplicación. Es común para los tres detectores
  // de cada ciclo, y MediaPipe necesita marcas monótonas para detectForVideo.
  if (ultima?.video === video && ultima.frame === ahoraMs) return ultima.medicion
  const resultado = instancia.detectForVideo(video, performance.now())
  const caras = resultado.faceLandmarks.length
  const angulos = caras === 1 ? angulosDesdeMatriz(resultado.facialTransformationMatrixes[0]) : null
  const medicion = { caras, yaw: angulos?.yaw ?? null, pitch: angulos?.pitch ?? null }
  ultima = { video, frame: ahoraMs, medicion }
  return medicion
}

export class DetectorMirada implements Detector {
  readonly nombre = 'mirada'
  readonly evento = 'gaze_away' as const
  readonly minimoMs: number
  private readonly yawLimite: number

  constructor(ajustes: AjustesMirada = {}) {
    this.minimoMs = ajustes.min_duration_ms ?? 3000
    this.yawLimite = ajustes.yaw_degrees ?? 25
  }

  async preparar(): Promise<void> { await motor() }

  observar(observacion: Observacion): Veredicto {
    const m = medicionDe(observacion)
    if (!m) return { activa: false, metadata: { source: 'mediapipe', available: false } }
    return {
      activa: reglasVision(m.caras, m.yaw, this.yawLimite, 2).gaze_away,
      metadata: {
        source: 'mediapipe', faces_detected: m.caras, yaw_deg: m.yaw,
        pitch_deg: m.pitch, threshold_deg: this.yawLimite,
        min_duration_ms: this.minimoMs
      }
    }
  }
}

export class DetectorRostroAusente implements Detector {
  readonly nombre = 'rostro-ausente'
  readonly evento = 'face_absent' as const
  readonly minimoMs: number

  constructor(ajustes: AjustesRostro = {}) { this.minimoMs = ajustes.min_duration_ms ?? 5000 }
  async preparar(): Promise<void> { await motor() }

  observar(observacion: Observacion): Veredicto {
    const m = medicionDe(observacion)
    if (!m) return { activa: false, metadata: { source: 'mediapipe', available: false } }
    return {
      activa: m.caras === 0,
      metadata: { source: 'mediapipe', faces_detected: m.caras, min_duration_ms: this.minimoMs }
    }
  }
}

export class DetectorPersonaExtra implements Detector {
  readonly nombre = 'persona-extra'
  readonly evento = 'extra_person' as const
  readonly minimoMs: number
  private readonly minimoRostros: number

  constructor(ajustes: AjustesPersonaExtra = {}) {
    this.minimoMs = ajustes.min_duration_ms ?? 2000
    this.minimoRostros = Math.max(2, ajustes.min_faces ?? 2)
  }
  async preparar(): Promise<void> { await motor() }

  observar(observacion: Observacion): Veredicto {
    const m = medicionDe(observacion)
    if (!m) return { activa: false, metadata: { source: 'mediapipe', available: false } }
    return {
      activa: m.caras >= this.minimoRostros,
      metadata: {
        source: 'mediapipe', faces_detected: m.caras,
        min_faces: this.minimoRostros, min_duration_ms: this.minimoMs
      }
    }
  }
}
