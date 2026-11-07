/** TA-073: per-student, per-session browser calibration. Never stores images or embeddings. */
export interface CalibrationSample {
  faceCount: number
  yaw: number | null
  pitch: number | null
  /** `eyeLookDown` (0 a 1). Opcional: una calibración vieja no lo trae. */
  eyeDown?: number | null
  eyeBlink?: number | null
}
export interface GazeCalibration {
  version: 1
  calibratedAt: string
  baselineYawDeg: number
  thresholdDeg: number
  samples: number[]
  source: 'mediapipe'
  /**
   * Mirada con los ojos (Jesús). Opcionales para que una calibración guardada
   * antes de este cambio siga cargando: sin ellos se usan los valores por defecto.
   */
  baselineEyeDown?: number
  baselineEyeBlink?: number
  /** Desvío de `eyeLookDown` sobre la línea base que cuenta como mirar abajo. */
  eyeDownThreshold?: number
}

/** Nunca por debajo del valor por defecto: calibrar no puede volver más estricta la regla. */
export const EYE_DOWN_DEFAULT = 0.45
/** Tope: más arriba, mirar a las piernas dejaría de contar. */
export const EYE_DOWN_MAX = 0.7
/** Margen sobre lo que el estudiante baja la vista para leer el borde inferior. */
const EYE_DOWN_MARGIN = 0.15
export const CALIBRATION_STEPS = [
  'Mira al centro de la pantalla',
  'Mira a la esquina superior izquierda',
  'Mira a la esquina superior derecha',
  'Mira a la esquina inferior izquierda',
  'Mira a la esquina inferior derecha'
] as const

/** An exploratory personal threshold, not an accuracy-certified threshold. */
export function estimateCalibration(samples: CalibrationSample[], defaultDeg = 25): GazeCalibration {
  if (samples.length !== CALIBRATION_STEPS.length || samples.some(s => s.faceCount !== 1 || s.yaw === null || !Number.isFinite(s.yaw))) {
    throw new Error('Necesitas cinco mediciones válidas con un único rostro.')
  }
  const center = samples[0].yaw as number
  const deviations = samples.slice(1).map(s => Math.abs((s.yaw as number) - center))
  const max = Math.max(...deviations)
  // Preserve the instructor's session threshold as a floor: never weaken it silently.
  const threshold = Math.min(45, Math.max(defaultDeg, max * 0.6))
  const result: GazeCalibration = { version: 1, calibratedAt: new Date().toISOString(), baselineYawDeg: center, thresholdDeg: threshold,
    samples: samples.map(s => s.yaw as number), source: 'mediapipe' }
  return { ...result, ...calibrarOjos(samples) }
}

/**
 * Los pasos 4 y 5 piden mirar las esquinas inferiores: es lo más abajo que el
 * estudiante mira SIN salir de la pantalla. El umbral queda por encima de eso,
 * para no marcar a quien lee la última línea de la pregunta.
 */
function calibrarOjos(samples: CalibrationSample[]): Partial<GazeCalibration> {
  const ojos = samples.map(s => s.eyeDown)
  const parpados = samples.map(s => s.eyeBlink)
  if (!ojos.every(isNum) || !parpados.every(isNum)) return {}
  const base = ojos[0]
  const abajoEnPantalla = Math.max(ojos[3], ojos[4]) - base
  return {
    baselineEyeDown: base,
    baselineEyeBlink: parpados[0],
    eyeDownThreshold: Math.min(EYE_DOWN_MAX, Math.max(EYE_DOWN_DEFAULT, abajoEnPantalla + EYE_DOWN_MARGIN))
  }
}

function isNum(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function key(sessionId: string, studentId: string): string {
  return `proctoring:gaze-calibration:v1:${sessionId}:${studentId}`
}

export function saveCalibration(sessionId: string, studentId: string, value: GazeCalibration): void {
  sessionStorage.setItem(key(sessionId, studentId), JSON.stringify(value))
}

export function loadCalibration(sessionId: string, studentId: string): GazeCalibration | null {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(key(sessionId, studentId)) ?? 'null')
    if (!value || typeof value !== 'object') return null
    const data = value as Partial<GazeCalibration>
    if (data.version !== 1 || data.source !== 'mediapipe' ||
        !Number.isFinite(data.baselineYawDeg) || !Number.isFinite(data.thresholdDeg) ||
        !Array.isArray(data.samples) || data.samples.length !== 5) return null
    if (Date.now() - Date.parse(data.calibratedAt ?? '') > 24 * 60 * 60 * 1000) return null
    return data as GazeCalibration
  } catch { return null }
}
