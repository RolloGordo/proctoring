/**
 * Encuadre de la cámara: reglas puras (Jesús Limay).
 *
 * El problema: con la cámara apuntando solo a la cara, un celular sostenido
 * bajo el borde de la imagen no se ve nunca, y el detector de objetos no
 * puede encontrar lo que no está en el fotograma. La regla exige que se vean
 * los hombros y los brazos: así lo que el estudiante tiene en las manos queda
 * dentro de la imagen.
 *
 * Usa los puntos del Pose Landmarker de MediaPipe (33 puntos, coordenadas de
 * 0 a 1 sobre el fotograma, con `visibility` de 0 a 1). Sin cámara, sin modelo
 * y sin navegador, para poder probarlo.
 */

/** Lo mínimo de un punto de MediaPipe. */
export interface PuntoPose {
  x: number
  y: number
  visibility?: number
}

/** Índices de MediaPipe Pose (BlazePose, 33 puntos). */
export const PUNTOS = {
  nariz: 0,
  orejaIzq: 7,
  orejaDer: 8,
  hombroIzq: 11,
  hombroDer: 12,
  codoIzq: 13,
  codoDer: 14,
  munecaIzq: 15,
  munecaDer: 16
} as const

/**
 * Qué tiene que verse, de menos a más exigente.
 * - `shoulders`: los dos hombros.
 * - `elbows`: hombros y los dos codos (por defecto: "que se vean los brazos").
 * - `hands`: hombros, codos y las dos muñecas.
 * - `off`: sin comprobación.
 */
export type NivelEncuadre = 'shoulders' | 'elbows' | 'hands' | 'off'
export const NIVEL_POR_DEFECTO: NivelEncuadre = 'elbows'

export type MotivoEncuadre =
  'ok' | 'no_person' | 'too_close' | 'no_shoulders' | 'no_elbows' | 'no_hands'

export interface ResultadoEncuadre {
  ok: boolean
  motivo: MotivoEncuadre
  /** Qué hacer, en palabras para el estudiante. */
  mensaje: string
  /** Lo medido, para `metadata` del evento. */
  medidas: {
    shoulders_visible: number
    elbows_visible: number
    wrists_visible: number
    shoulder_width: number | null
  }
}

/** Con menos confianza que esto, MediaPipe está adivinando dónde está el punto. */
export const VISIBILIDAD_MINIMA = 0.5
/**
 * Hombros que ocupan más del 80 % del ancho: la persona está tan cerca que lo
 * que tiene delante del pecho queda fuera de la imagen.
 */
export const ANCHO_HOMBROS_MAXIMO = 0.8

export const MENSAJES: Record<MotivoEncuadre, string> = {
  ok: 'Encuadre correcto: se ven tus hombros y brazos.',
  no_person: 'No se te ve en la cámara. Siéntate frente a ella.',
  too_close: 'Estás demasiado cerca de la cámara. Aléjate un poco o echa la pantalla hacia atrás.',
  no_shoulders:
    'Solo se ve tu cara. Aleja la cámara o inclina la pantalla hacia atrás hasta que se vean tus hombros.',
  no_elbows:
    'Deben verse tus brazos. Baja un poco la cámara o aléjala hasta que se vean tus codos.',
  no_hands: 'Deben verse tus manos. Aleja la cámara o pon las manos sobre la mesa, a la vista.'
}

/** Un punto cuenta si MediaPipe confía en él y cae dentro del fotograma. */
export function visible(p: PuntoPose | undefined): boolean {
  if (!p || !Number.isFinite(p.x) || !Number.isFinite(p.y)) return false
  if ((p.visibility ?? 0) < VISIBILIDAD_MINIMA) return false
  // Un punto en el borde inferior suele estar "estirado" fuera de la imagen.
  return p.x >= 0 && p.x <= 1 && p.y >= 0 && p.y <= 0.98
}

function cuantos(puntos: PuntoPose[], indices: number[]): number {
  return indices.filter((i) => visible(puntos[i])).length
}

export function evaluarEncuadre(
  poses: PuntoPose[][] | undefined,
  nivel: NivelEncuadre = NIVEL_POR_DEFECTO
): ResultadoEncuadre {
  const sinMedidas = {
    shoulders_visible: 0,
    elbows_visible: 0,
    wrists_visible: 0,
    shoulder_width: null
  }
  if (nivel === 'off') return { ok: true, motivo: 'ok', mensaje: MENSAJES.ok, medidas: sinMedidas }
  const p = poses?.[0]
  if (!p?.length) return resultado('no_person', sinMedidas)

  const hombros = cuantos(p, [PUNTOS.hombroIzq, PUNTOS.hombroDer])
  const codos = cuantos(p, [PUNTOS.codoIzq, PUNTOS.codoDer])
  const munecas = cuantos(p, [PUNTOS.munecaIzq, PUNTOS.munecaDer])
  const hi = p[PUNTOS.hombroIzq]
  const hd = p[PUNTOS.hombroDer]
  const ancho = hombros === 2 && hi && hd ? Math.abs(hi.x - hd.x) : null
  const medidas = {
    shoulders_visible: hombros,
    elbows_visible: codos,
    wrists_visible: munecas,
    shoulder_width: ancho === null ? null : Math.round(ancho * 1000) / 1000
  }

  // Ni hombros ni cara: no hay nadie, o está fuera de cuadro.
  const cara = cuantos(p, [PUNTOS.nariz, PUNTOS.orejaIzq, PUNTOS.orejaDer]) > 0
  if (hombros === 0 && !cara) return resultado('no_person', medidas)
  if (ancho !== null && ancho > ANCHO_HOMBROS_MAXIMO) return resultado('too_close', medidas)
  if (hombros < 2) return resultado('no_shoulders', medidas)
  if (nivel === 'shoulders') return resultado('ok', medidas)
  if (codos < 2) return resultado('no_elbows', medidas)
  if (nivel === 'elbows') return resultado('ok', medidas)
  if (munecas < 2) return resultado('no_hands', medidas)
  return resultado('ok', medidas)
}

function resultado(
  motivo: MotivoEncuadre,
  medidas: ResultadoEncuadre['medidas']
): ResultadoEncuadre {
  return { ok: motivo === 'ok', motivo, mensaje: MENSAJES[motivo], medidas }
}

export function nivelDe(valor: unknown): NivelEncuadre {
  return valor === 'shoulders' || valor === 'elbows' || valor === 'hands' || valor === 'off'
    ? valor
    : NIVEL_POR_DEFECTO
}

/**
 * Cuánto tiene que sostenerse un buen encuadre antes de dar paso. Sin esto,
 * un solo fotograma bueno al echarse hacia atrás un instante bastaría.
 */
export const ESTABLE_MS = 2000

/** Cuenta cuánto lleva seguido el encuadre bien. Puro: la hora viene de fuera. */
export class EstabilidadEncuadre {
  private desde: number | null = null
  constructor(private readonly necesarioMs = ESTABLE_MS) {}

  /** Devuelve si ya lleva `necesarioMs` seguidos bien. */
  registrar(ok: boolean, ahoraMs: number): boolean {
    if (!ok) {
      this.desde = null
      return false
    }
    this.desde ??= ahoraMs
    return ahoraMs - this.desde >= this.necesarioMs
  }

  /** De 0 a 1, para la barra de progreso. */
  progreso(ahoraMs: number): number {
    return this.desde === null ? 0 : Math.min(1, (ahoraMs - this.desde) / this.necesarioMs)
  }
}
