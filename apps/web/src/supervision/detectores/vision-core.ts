/** Geometría y reglas puras, compartidas por el spike y los detectores reales. */
export interface MatrizFacial { data: number[] | Float32Array }
export interface AngulosCabeza { yaw: number; pitch: number }

/**
 * MediaPipe devuelve una matriz 4x4 en orden de filas. La orientación del eje
 * Y se recupera con atan2(R02,R22); X con atan2(-R12, sqrt(R10²+R11²)).
 * Estos ángulos son aproximaciones del giro de la cabeza, no de los ojos.
 */
export function angulosDesdeMatriz(matriz: MatrizFacial | undefined): AngulosCabeza | null {
  const m = matriz?.data
  if (!m || m.length !== 16 || !Array.from(m).every(Number.isFinite)) return null
  const yaw = (Math.atan2(m[2], m[10]) * 180) / Math.PI
  const pitch = (Math.atan2(-m[6], Math.hypot(m[4], m[5])) * 180) / Math.PI
  return Number.isFinite(yaw) && Number.isFinite(pitch) ? { yaw, pitch } : null
}

export function reglasVision(caras: number, yaw: number | null, limiteYaw: number, minimoCaras: number) {
  return {
    gaze_away: caras === 1 && yaw !== null && Math.abs(yaw) > limiteYaw,
    face_absent: caras === 0,
    extra_person: caras >= minimoCaras
  }
}

/** El máximo es un límite operativo explícito, no un detector silencioso incapaz.
 * Configuraciones mayores necesitan una decisión de rendimiento del equipo.
 */
export const MAX_ROSTROS_MODELO = 10
export function capacidadParaUmbralRostros(minFaces: number): number {
  if (!Number.isInteger(minFaces) || minFaces < 2 || minFaces > MAX_ROSTROS_MODELO) {
    throw new RangeError(`min_faces debe estar entre 2 y ${MAX_ROSTROS_MODELO} (recibido: ${minFaces})`)
  }
  return minFaces
}
