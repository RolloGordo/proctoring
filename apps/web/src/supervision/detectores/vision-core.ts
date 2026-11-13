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

// ---------------------------------------------------------------------------
// Mirada con los ojos (Jesús Limay).
//
// El giro de la cabeza no basta: con la cabeza quieta se puede bajar la vista
// a un celular en las piernas y el yaw/pitch no cambia. Face Landmarker trae
// un tercer modelo, `face_blendshapes.tflite`, que ya viaja DENTRO de
// `face_landmarker.task`: activarlo no descarga ni pesa nada más. De sus 52
// coeficientes (0 a 1) se usan los de los ojos.
// ---------------------------------------------------------------------------

export interface CategoriaBlendshape {
  categoryName: string
  score: number
}

/** Cuánto se desvían los ojos, de 0 (centro) a 1 (al tope). */
export interface Ojos {
  /** Promedio de `eyeLookDownLeft` y `eyeLookDownRight`. */
  abajo: number
  /** El mayor de mirar a un lado (ambos ojos hacia el mismo lado). */
  lado: number
  /** Promedio de `eyeBlinkLeft` y `eyeBlinkRight`: párpado caído. */
  parpado: number
}

export function ojosDesdeBlendshapes(categorias: CategoriaBlendshape[] | undefined): Ojos | null {
  if (!categorias?.length) return null
  const v = new Map(categorias.map((c) => [c.categoryName, c.score]))
  const par = (a: string, b: string): number | null => {
    const x = v.get(a)
    const y = v.get(b)
    return typeof x === 'number' && typeof y === 'number' ? (x + y) / 2 : null
  }
  const abajo = par('eyeLookDownLeft', 'eyeLookDownRight')
  // Mirar a la izquierda de la imagen: un ojo mira "afuera" y el otro "adentro".
  const ladoA = par('eyeLookOutLeft', 'eyeLookInRight')
  const ladoB = par('eyeLookInLeft', 'eyeLookOutRight')
  const parpado = par('eyeBlinkLeft', 'eyeBlinkRight')
  if (abajo === null || ladoA === null || ladoB === null || parpado === null) return null
  return { abajo, lado: Math.max(ladoA, ladoB), parpado }
}

export interface LimitesOjos {
  /** Cuánto más abajo que en el centro calibrado cuenta como "mirando abajo". */
  abajo: number
  lado: number
  /** Línea base de la calibración ("mira al centro"). Sin calibrar, 0. */
  baseAbajo?: number
  baseParpado?: number
}

export const LIMITES_OJOS_POR_DEFECTO = { abajo: 0.45, lado: 0.55 } as const

export type MotivoOjos = 'eyes_down' | 'eyes_side' | null

/**
 * Si los ojos miran fuera de la pantalla aunque la cabeza no se mueva.
 *
 * Dos formas de "mirar abajo":
 * 1. El iris baja: `eyeLookDown` sube sobre la línea base.
 * 2. El párpado cae sobre el iris (típico al mirar algo en las piernas, y peor
 *    con lentes): el iris casi no se ve y `eyeLookDown` sube menos, pero
 *    `eyeBlink` sube mucho. Se acepta con un `eyeLookDown` menor.
 *
 * Un parpadeo real también sube `eyeBlink`, pero dura menos de medio segundo:
 * lo descarta el mínimo de duración del módulo (3 s por defecto).
 */
export function reglaOjos(ojos: Ojos | null, limites: LimitesOjos): MotivoOjos {
  if (!ojos) return null
  const abajo = ojos.abajo - (limites.baseAbajo ?? 0)
  const parpado = ojos.parpado - (limites.baseParpado ?? 0)
  if (abajo >= limites.abajo) return 'eyes_down'
  if (parpado >= 0.35 && abajo >= limites.abajo * 0.5) return 'eyes_down'
  if (ojos.lado >= limites.lado) return 'eyes_side'
  return null
}

// ---------------------------------------------------------------------------
// Medición del rostro a partir del resultado compacto (Jesús Limay).
//
// La misma función sirve para el motor en el hilo principal y para el motor en
// segundo plano (`motor.worker.ts`): las reglas no pueden dar otro resultado
// según dónde corrió el modelo.
// ---------------------------------------------------------------------------

export interface PuntoNormalizado {
  x: number
  y: number
}

export interface RostroCompactoCore {
  caras: number
  matriz: ArrayLike<number> | null
  boca: {
    arriba?: PuntoNormalizado
    abajo?: PuntoNormalizado
    izquierda?: PuntoNormalizado
    derecha?: PuntoNormalizado
  } | null
  blendshapes: CategoriaBlendshape[] | null
}

export interface MedicionRostro {
  caras: number
  yaw: number | null
  pitch: number | null
  inferenceMs: number
  mouthOpenRatio: number | null
  ojos: Ojos | null
}

/** Lo que devuelve FaceLandmarker, reducido a lo que usan las reglas. */
export function compactarRostro(resultado: {
  faceLandmarks: PuntoNormalizado[][]
  facialTransformationMatrixes?: Array<{ data: ArrayLike<number> }>
  faceBlendshapes?: Array<{ categories: CategoriaBlendshape[] }>
}): RostroCompactoCore {
  const caras = resultado.faceLandmarks.length
  const puntos = caras === 1 ? resultado.faceLandmarks[0] : undefined
  return {
    caras,
    matriz: caras === 1 ? (resultado.facialTransformationMatrixes?.[0]?.data ?? null) : null,
    boca: puntos
      ? { arriba: puntos[13], abajo: puntos[14], izquierda: puntos[61], derecha: puntos[291] }
      : null,
    blendshapes: caras === 1 ? (resultado.faceBlendshapes?.[0]?.categories ?? null) : null
  }
}

export function medicionDesdeRostro(r: RostroCompactoCore, inferenceMs: number): MedicionRostro {
  const angulos =
    r.caras === 1 && r.matriz
      ? angulosDesdeMatriz({ data: Array.from(r.matriz) } as MatrizFacial)
      : null
  // La apertura de boca es solo una señal observable: no prueba que hable.
  const { arriba, abajo, izquierda, derecha } = r.boca ?? {}
  const ancho =
    izquierda && derecha ? Math.hypot(izquierda.x - derecha.x, izquierda.y - derecha.y) : 0
  const mouthOpenRatio =
    ancho > 0 && arriba && abajo ? Math.hypot(arriba.x - abajo.x, arriba.y - abajo.y) / ancho : null
  return {
    caras: r.caras,
    yaw: angulos?.yaw ?? null,
    pitch: angulos?.pitch ?? null,
    inferenceMs,
    mouthOpenRatio,
    ojos: r.caras === 1 ? ojosDesdeBlendshapes(r.blendshapes ?? undefined) : null
  }
}
