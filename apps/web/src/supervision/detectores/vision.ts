/** Detectores de SPEC-007. Sin grabación continua ni eventos por fotograma. */
import type { FaceLandmarker } from '@mediapipe/tasks-vision'
import type { Detector, Observacion, Veredicto } from '../tipos'
import { ANCHO_ROSTRO, fotogramaReducido } from './fotograma'
import {
  cargarRemoto,
  remotoActivo,
  siCaeElRemoto,
  solicitarCuadro,
  ultimoRostro
} from './motorRemoto'
import {
  capacidadParaUmbralRostros,
  compactarRostro,
  medicionDesdeRostro,
  LIMITES_OJOS_POR_DEFECTO,
  reglaOjos,
  reglasVision,
  type MedicionRostro
} from './vision-core'

export interface AjustesMirada {
  yaw_degrees?: number
  /** Optional: looking up/down. Disabled unless the teacher configured it. */
  pitch_degrees?: number
  yaw_baseline_deg?: number
  calibration_status?: 'calibrated' | 'default'
  min_duration_ms?: number
  /**
   * Mirada con los ojos aunque la cabeza no se mueva (Jesús). Encendida por
   * defecto: es justo el hueco por el que se miraba el celular sin ser visto.
   * El docente la apaga con `eye_gaze: false`.
   */
  eye_gaze?: boolean
  /** Desvío de `eyeLookDown` (0 a 1) sobre la línea base que cuenta como "abajo". */
  eye_down_threshold?: number
  eye_side_threshold?: number
  /** Línea base de la calibración ("mira al centro"). */
  eye_down_baseline?: number
  eye_blink_baseline?: number
}
export interface AjustesRostro { min_duration_ms?: number }
export interface AjustesPersonaExtra {
  min_faces?: number
  min_duration_ms?: number
}

type Medicion = MedicionRostro

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
        // Los coeficientes de los ojos. El modelo ya viene en el .task.
        outputFaceBlendshapes: true,
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

/**
 * Rostros que debe poder ver el motor en segundo plano. Si el worker se cae, el
 * motor local se carga con la misma capacidad.
 */
let capacidadRemota = 0
let capacidadDeseada = 2
siCaeElRemoto(() => {
  capacidadRemota = 0
  void motor(capacidadDeseada).catch(() => {})
})

/**
 * Prepara el modelo de rostro: primero en segundo plano (`motor.worker.ts`);
 * si el worker no está disponible, en el hilo principal como antes.
 */
async function prepararRostro(rostrosNecesarios = 2): Promise<void> {
  const requeridos = capacidadParaUmbralRostros(rostrosNecesarios)
  capacidadDeseada = Math.max(capacidadDeseada, requeridos)
  if (await cargarRemoto('rostro', { numFaces: capacidadDeseada })) {
    capacidadRemota = capacidadDeseada
    return
  }
  await motor(capacidadDeseada)
}

/**
 * La medición del ciclo. `local` obliga a medir en el hilo principal: lo usan
 * la calibración y la comprobación de la foto, que necesitan la respuesta del
 * fotograma que están mirando y no la del ciclo anterior.
 */
function medicionDe({ video, ahoraMs }: Observacion, local = false): Medicion | null {
  if (!video || video.readyState < 2 || !video.videoWidth) return null
  if (!local && remotoActivo()) {
    solicitarCuadro(video, ahoraMs)
    const r = ultimoRostro(ahoraMs)
    return r ? medicionDesdeRostro(r.datos, r.ms ?? 0) : null
  }
  if (!instancia) {
    // Si el worker se cayó en pleno examen, el motor local se está cargando.
    return null
  }
  // AhoraMs es común para los tres detectores de cada ciclo, y MediaPipe
  // necesita marcas monótonas para detectForVideo.
  if (ultima?.video === video && ultima.frame === ahoraMs) return ultima.medicion
  const start = performance.now()
  // Entrada reducida (fotograma.ts): mismo resultado normalizado, menos copia.
  const resultado = instancia.detectForVideo(fotogramaReducido(video, ahoraMs, ANCHO_ROSTRO), start)
  const medicion = medicionDesdeRostro(compactarRostro(resultado), performance.now() - start)
  ultima = { video, frame: ahoraMs, medicion }
  return medicion
}

export class DetectorMirada implements Detector {
  readonly nombre = 'mirada'
  readonly evento = 'gaze_away' as const
  readonly minimoMs: number
  private readonly yawLimite: number
  private readonly pitchLimite: number | null
  private readonly yawCentro: number
  private readonly calibrationStatus: 'calibrated' | 'default'
  private readonly conOjos: boolean
  private readonly limitesOjos: {
    abajo: number
    lado: number
    baseAbajo: number
    baseParpado: number
  }

  constructor(ajustes: AjustesMirada = {}) {
    this.minimoMs = ajustes.min_duration_ms ?? 3000
    this.yawLimite = ajustes.yaw_degrees ?? 25
    this.pitchLimite = typeof ajustes.pitch_degrees === 'number' && ajustes.pitch_degrees > 0
      ? ajustes.pitch_degrees : null
    this.yawCentro = ajustes.yaw_baseline_deg ?? 0
    this.calibrationStatus = ajustes.calibration_status ?? 'default'
    this.conOjos = ajustes.eye_gaze !== false
    this.limitesOjos = {
      abajo: positivo(ajustes.eye_down_threshold) ?? LIMITES_OJOS_POR_DEFECTO.abajo,
      lado: positivo(ajustes.eye_side_threshold) ?? LIMITES_OJOS_POR_DEFECTO.lado,
      baseAbajo: finito(ajustes.eye_down_baseline) ?? 0,
      baseParpado: finito(ajustes.eye_blink_baseline) ?? 0
    }
  }

  async preparar(): Promise<void> { await prepararRostro() }

  observar(observacion: Observacion): Veredicto {
    const m = medicionDe(observacion)
    if (!m) return { activa: false, metadata: { source: 'mediapipe', available: false } }
    const yawDeviation = m.yaw === null ? null : m.yaw - this.yawCentro
    const turnedYaw = reglasVision(m.caras, yawDeviation, this.yawLimite, 2).gaze_away
    const turnedPitch = m.caras === 1 && m.pitch !== null && this.pitchLimite !== null
      && Math.abs(m.pitch) > this.pitchLimite
    // Solo con un rostro: con dos, de quién son los ojos es ambiguo.
    const ojos = this.conOjos && m.caras === 1 ? reglaOjos(m.ojos, this.limitesOjos) : null
    // El motivo queda en metadata: el docente tiene que saber si giró la cabeza
    // o si solo bajó la vista, porque se revisan distinto.
    const reason = turnedYaw ? 'head_yaw' : turnedPitch ? 'head_pitch' : ojos
    return {
      activa: turnedYaw || turnedPitch || ojos !== null,
      metadata: {
        source: 'mediapipe', reason, faces_detected: m.caras, yaw_deg: m.yaw,
        eye_gaze: this.conOjos,
        eye_down: redondear(m.ojos?.abajo), eye_side: redondear(m.ojos?.lado),
        eye_blink: redondear(m.ojos?.parpado),
        eye_down_threshold: this.limitesOjos.abajo, eye_side_threshold: this.limitesOjos.lado,
        eye_down_baseline: this.limitesOjos.baseAbajo,
        pitch_deg: m.pitch, pitch_threshold_deg: this.pitchLimite,
        inference_ms: Math.round(m.inferenceMs * 10) / 10, mouth_open_ratio: m.mouthOpenRatio,
        yaw_baseline_deg: this.yawCentro, calibration_status: this.calibrationStatus, threshold_deg: this.yawLimite,
        min_duration_ms: this.minimoMs
      }
    }
  }
}

function positivo(valor: unknown): number | undefined {
  return typeof valor === 'number' && Number.isFinite(valor) && valor > 0 ? valor : undefined
}
function finito(valor: unknown): number | undefined {
  return typeof valor === 'number' && Number.isFinite(valor) ? valor : undefined
}
function redondear(valor: number | undefined): number | null {
  return typeof valor === 'number' ? Math.round(valor * 1000) / 1000 : null
}

export class DetectorRostroAusente implements Detector {
  readonly nombre = 'rostro-ausente'
  readonly evento = 'face_absent' as const
  readonly minimoMs: number

  constructor(ajustes: AjustesRostro = {}) { this.minimoMs = ajustes.min_duration_ms ?? 5000 }
  async preparar(): Promise<void> { await prepararRostro() }

  observar(observacion: Observacion): Veredicto {
    const m = medicionDe(observacion)
    if (!m) return { activa: false, metadata: { source: 'mediapipe', available: false } }
    return {
      activa: m.caras === 0,
      metadata: { source: 'mediapipe', faces_detected: m.caras, inference_ms: Math.round(m.inferenceMs * 10) / 10, min_duration_ms: this.minimoMs }
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
  async preparar(): Promise<void> { await prepararRostro(this.minimoRostros) }

  observar(observacion: Observacion): Veredicto {
    const m = medicionDe(observacion)
    if (!m) return { activa: false, metadata: { source: 'mediapipe', available: false } }
    return {
      activa: m.caras >= this.minimoRostros,
      metadata: {
        source: 'mediapipe', faces_detected: m.caras,
        min_faces: this.minimoRostros, model_num_faces: remotoActivo() ? capacidadRemota : capacidad,
        inference_ms: Math.round(m.inferenceMs * 10) / 10,
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
  const result = medicionDe({ video, ahoraMs: Date.now() }, true)
  if (!result) throw new Error('MediaPipe no pudo evaluar la imagen de la cámara.')
  return result.caras
}

/** A head-pose measurement for a consented calibration step (not identity verification). */
export async function measureHeadPose(video: HTMLVideoElement): Promise<{
  faceCount: number
  yaw: number | null
  pitch: number | null
  eyeDown: number | null
  eyeBlink: number | null
  eyeSide: number | null
}> {
  await motor(2)
  const result = medicionDe({ video, ahoraMs: Date.now() }, true)
  if (!result) throw new Error('La cámara todavía no entrega una imagen válida.')
  return {
    faceCount: result.caras,
    yaw: result.yaw,
    pitch: result.pitch,
    eyeDown: result.ojos?.abajo ?? null,
    eyeBlink: result.ojos?.parpado ?? null,
    eyeSide: result.ojos?.lado ?? null
  }
}
