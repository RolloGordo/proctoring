/** TA-073: per-student, per-session browser calibration. Never stores images or embeddings. */
export interface CalibrationSample {
  faceCount: number
  yaw: number | null
  pitch: number | null
  /** `eyeLookDown` (0 a 1). Opcional: una calibración vieja no lo trae. */
  eyeDown?: number | null
  eyeBlink?: number | null
  /** Mirada lateral con los ojos (0 a 1). Opcional, como `eyeDown`. */
  eyeSide?: number | null
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
  /** Mirada lateral con los ojos que cuenta como fuera de pantalla. */
  eyeSideThreshold?: number
}

/** Nunca por debajo del valor por defecto: calibrar no puede volver más estricta la regla. */
export const EYE_DOWN_DEFAULT = 0.45
/** Tope: más arriba, mirar a las piernas dejaría de contar. */
export const EYE_DOWN_MAX = 0.7
/** Margen sobre lo que el estudiante baja la vista para leer el borde inferior. */
const EYE_DOWN_MARGIN = 0.15
/**
 * Lo más que puede bajar la vista alguien que mira la esquina inferior de SU
 * pantalla. Más abajo ya está mirando fuera (la mesa, las piernas): ese paso se
 * rechaza, porque aceptarlo subiría el umbral y apagaría la regla de los ojos.
 * Igual a tope menos margen: un paso aceptado nunca deja el umbral sobre el tope.
 */
export const EYE_DOWN_PLAUSIBLE = EYE_DOWN_MAX - EYE_DOWN_MARGIN
/** Mirada lateral: mismo criterio que hacia abajo, con las esquinas izquierda y derecha. */
export const EYE_SIDE_DEFAULT = 0.55
export const EYE_SIDE_MAX = 0.8
const EYE_SIDE_MARGIN = 0.15

/** Fotogramas que se toman por paso, y cuántos tienen que salir bien. */
export const MUESTRAS_POR_PASO = 6
export const MUESTRAS_VALIDAS_MINIMAS = 4

/**
 * Un paso de la calibración a partir de varios fotogramas seguidos (Jesús).
 *
 * Antes cada paso tomaba UN fotograma: si el estudiante parpadeaba justo en
 * ese instante, `eyeBlink` y `eyeLookDown` quedaban falseados para todo el
 * examen. La mediana de seis fotogramas ignora un parpadeo o un fotograma
 * malo. Devuelve `null` si menos de cuatro vieron exactamente un rostro.
 */
export function combinarMuestras(muestras: CalibrationSample[]): CalibrationSample | null {
  const validas = muestras.filter((m) => m.faceCount === 1 && isNum(m.yaw))
  if (validas.length < MUESTRAS_VALIDAS_MINIMAS) return null
  const campo = (f: (m: CalibrationSample) => number | null | undefined) =>
    mediana(validas.map(f).filter(isNum))
  return {
    faceCount: 1,
    yaw: campo((m) => m.yaw),
    pitch: campo((m) => m.pitch),
    eyeDown: campo((m) => m.eyeDown),
    eyeBlink: campo((m) => m.eyeBlink),
    eyeSide: campo((m) => m.eyeSide)
  }
}

function mediana(valores: number[]): number | null {
  if (!valores.length) return null
  const o = [...valores].sort((a, b) => a - b)
  const m = Math.floor(o.length / 2)
  return o.length % 2 ? o[m] : (o[m - 1] + o[m]) / 2
}

/**
 * Comprueba que un paso tenga sentido antes de aceptarlo. Devuelve el mensaje
 * para el estudiante, o `null` si está bien. El paso 0 (centro) siempre vale.
 */
export function validarPaso(
  paso: number,
  muestra: CalibrationSample,
  centro?: CalibrationSample
): string | null {
  if (paso === 0 || !centro) return null
  if (
    isNum(muestra.eyeDown) &&
    isNum(centro.eyeDown) &&
    muestra.eyeDown - centro.eyeDown > EYE_DOWN_PLAUSIBLE
  ) {
    return 'Parece que miraste por debajo de la pantalla. Mira la esquina de la pantalla e inténtalo otra vez.'
  }
  return null
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
  const lados = samples.map((s) => s.eyeSide)
  return {
    baselineEyeDown: base,
    baselineEyeBlink: parpados[0],
    eyeDownThreshold: Math.min(
      EYE_DOWN_MAX,
      Math.max(EYE_DOWN_DEFAULT, abajoEnPantalla + EYE_DOWN_MARGIN)
    ),
    // Las cuatro esquinas son lo más a un lado que mira sin salir de la pantalla.
    ...(lados.every(isNum) && {
      eyeSideThreshold: Math.min(
        EYE_SIDE_MAX,
        Math.max(EYE_SIDE_DEFAULT, Math.max(...lados.slice(1)) + EYE_SIDE_MARGIN)
      )
    })
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
