/** TA-073: per-student, per-session browser calibration. Never stores images or embeddings. */
export interface CalibrationSample { faceCount: number; yaw: number | null; pitch: number | null }
export interface GazeCalibration {
  version: 1
  calibratedAt: string
  baselineYawDeg: number
  thresholdDeg: number
  samples: number[]
  source: 'mediapipe'
}
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
  return { version: 1, calibratedAt: new Date().toISOString(), baselineYawDeg: center, thresholdDeg: threshold,
    samples: samples.map(s => s.yaw as number), source: 'mediapipe' }
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
