/** Detectores de SPEC-007. Sin grabación continua ni eventos por fotograma. */
import type { FaceLandmarker } from '@mediapipe/tasks-vision'
import type { Detector, Observacion, Veredicto } from '../tipos'
import { angulosDesdeMatriz, capacidadParaUmbralRostros, reglasVision } from './vision-core'

export interface AjustesMirada {
  yaw_degrees?: number
  yaw_baseline_deg?: number
  calibration_status?: 'calibrated' | 'default'
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

/** Modelo compartido: la biblioteca se importa solo al activar supervisión visual.
 * Si una sesión exige min_faces=3, el modelo debe ser capaz de detectar 3 caras.
 * La capacidad se puede ampliar entre sesiones sin repetir inferencia por detector.
 */
let configurando: Promise<void> | undefined
let instancia: FaceLandmarker | undefined
let capacidad = 0
let ultima: { video: HTMLVideoElement; frame: number; medicion: Medicion } | undefined

async function motor(rostrosNecesarios = 2): Promise<void> {
  const requeridos = capacidadParaUmbralRostros(rostrosNecesarios)
  if (instancia && capacidad >= requeridos) return

  // Evita iniciar varios motores o cambiar las opciones simultáneamente.
  if (configurando) {
    await configurando
    if (instancia && capacidad >= requeridos) return
    return motor(requeridos)
  }
  configurando = (async () => {
    if (instancia) {
      await instancia.setOptions({ numFaces: requeridos })
    } else {
      // Import dinámico: la página del docente no descarga MediaPipe.
      const { FaceLandmarker, FilesetResolver } = await import('@mediapipe/tasks-vision')
      const wasm = await FilesetResolver.forVisionTasks('/mediapipe/wasm')
      instancia = await FaceLandmarker.createFromOptions(wasm, {
        baseOptions: { modelAssetPath: '/mediapipe/face_landmarker.task' },
        numFaces: requeridos,
        outputFacialTransformationMatrixes: true,
        runningMode: 'VIDEO'
      })
    }
    capacidad = requeridos
    ultima = undefined
  })()
  try {
    await configurando
  } finally {
    configurando = undefined
  }
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
  private readonly yawCentro: number
  private readonly calibrationStatus: 'calibrated' | 'default'

  constructor(ajustes: AjustesMirada = {}) {
    this.minimoMs = ajustes.min_duration_ms ?? 3000
    this.yawLimite = ajustes.yaw_degrees ?? 25
    this.yawCentro = ajustes.yaw_baseline_deg ?? 0
    this.calibrationStatus = ajustes.calibration_status ?? 'default'
  }

  async preparar(): Promise<void> { await motor() }

  observar(observacion: Observacion): Veredicto {
    const m = medicionDe(observacion)
    if (!m) return { activa: false, metadata: { source: 'mediapipe', available: false } }
    return {
      activa: reglasVision(m.caras, m.yaw === null ? null : m.yaw - this.yawCentro, this.yawLimite, 2).gaze_away,
      metadata: {
        source: 'mediapipe', faces_detected: m.caras, yaw_deg: m.yaw,
        pitch_deg: m.pitch, yaw_baseline_deg: this.yawCentro, calibration_status: this.calibrationStatus, threshold_deg: this.yawLimite,
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
    this.minimoRostros = ajustes.min_faces ?? 2
  }
  async preparar(): Promise<void> { await motor(this.minimoRostros) }

  observar(observacion: Observacion): Veredicto {
    const m = medicionDe(observacion)
    if (!m) return { activa: false, metadata: { source: 'mediapipe', available: false } }
    return {
      activa: m.caras >= this.minimoRostros,
      metadata: {
        source: 'mediapipe', faces_detected: m.caras,
        min_faces: this.minimoRostros, model_num_faces: capacidad,
        min_duration_ms: this.minimoMs
      }
    }
  }
}

/** MediaPipe SOLO confirma que una fotografía de referencia tenga una cara visible.
 * Esto NO verifica identidad ni calcula embeddings; el backend de identidad
 * existente es otra pieza y requiere decisión del docente sobre la API.
 */
export async function contarRostrosEnCamara(video: HTMLVideoElement): Promise<number> {
  await motor(2)
  const result = medicionDe({ video, ahoraMs: Date.now() })
  if (!result) throw new Error('MediaPipe no pudo evaluar la imagen de la cámara.')
  return result.caras
}

/** A head-pose measurement for a consented calibration step (not identity verification). */
export async function measureHeadPose(video: HTMLVideoElement): Promise<{ faceCount: number; yaw: number | null; pitch: number | null }> {
  await motor(2)
  const result = medicionDe({ video, ahoraMs: Date.now() })
  if (!result) throw new Error('La cámara todavía no entrega una imagen válida.')
  return { faceCount: result.caras, yaw: result.yaw, pitch: result.pitch }
}
