/**
 * Fotograma reducido y turnos de inferencia (Jesús Limay — rendimiento de cámara).
 *
 * La cámara se abre a 960x540 porque el docente necesita reconocer al
 * estudiante en la vista en vivo. Los modelos no necesitan tanto: cada uno
 * reduce la imagen por dentro a su propia entrada (rostro 192/256 px, pose
 * 256 px, objetos 320 px). Pasarles el fotograma entero solo obliga a MediaPipe
 * a copiar y convertir 518.400 píxeles en el hilo principal, en cada inferencia.
 *
 * Aquí se dibuja el fotograma **una vez por ciclo** en un lienzo más pequeño y
 * se reutiliza. Como todos los detectores trabajan con coordenadas
 * normalizadas (0 a 1), reducir la imagen no cambia sus reglas.
 *
 * Además, los dos modelos más caros (objetos y pose) se turnan: nunca corren
 * en el mismo ciclo. Antes coincidían cada 500 ms y ese ciclo congelaba la
 * pantalla del examen.
 */

/** Lo que acepta `detectForVideo` de MediaPipe. */
export type Fuente = HTMLVideoElement | HTMLCanvasElement

/**
 * Anchos de entrada por modelo. El rostro va más grande que los demás: de él
 * salen los ojos (blendshapes), que necesitan detalle alrededor de los párpados.
 */
export const ANCHO_ROSTRO = 640
export const ANCHO_POSE = 480
export const ANCHO_OBJETOS = 480

interface Lienzo {
  lienzo: HTMLCanvasElement
  contexto: CanvasRenderingContext2D
  ultimoMs: number
}

const lienzos = new WeakMap<HTMLVideoElement, Map<number, Lienzo>>()

/**
 * El fotograma de `video` reducido a `anchoMax` de ancho, dibujado una sola vez
 * por `ahoraMs` (el reloj común del ciclo). Si la cámara ya es más pequeña, o
 * no hay lienzo disponible, devuelve el propio vídeo: nunca impide observar.
 */
export function fotogramaReducido(
  video: HTMLVideoElement,
  ahoraMs: number,
  anchoMax: number
): Fuente {
  const ancho = video.videoWidth
  const alto = video.videoHeight
  if (!ancho || !alto || ancho <= anchoMax || typeof document === 'undefined') return video
  let porAncho = lienzos.get(video)
  if (!porAncho) {
    porAncho = new Map()
    lienzos.set(video, porAncho)
  }
  let entrada = porAncho.get(anchoMax)
  if (!entrada) {
    const lienzo = document.createElement('canvas')
    const contexto = lienzo.getContext('2d', { alpha: false })
    if (!contexto) return video
    entrada = { lienzo, contexto, ultimoMs: Number.NaN }
    porAncho.set(anchoMax, entrada)
  }
  const altoReducido = Math.round((anchoMax * alto) / ancho)
  if (entrada.lienzo.width !== anchoMax || entrada.lienzo.height !== altoReducido) {
    entrada.lienzo.width = anchoMax
    entrada.lienzo.height = altoReducido
    entrada.ultimoMs = Number.NaN
  }
  if (entrada.ultimoMs !== ahoraMs) {
    entrada.contexto.drawImage(video, 0, 0, anchoMax, altoReducido)
    entrada.ultimoMs = ahoraMs
  }
  return entrada.lienzo
}

// ---------------------------------------------------------------------------
// Turnos: un solo modelo pesado por ciclo.
// ---------------------------------------------------------------------------

let cicloOcupado: number | undefined

/**
 * Pide el turno pesado del ciclo `ahoraMs`. Devuelve `false` si otro modelo
 * pesado ya lo tomó: entonces se espera al ciclo siguiente (125 ms después),
 * que para objetos (cada 250 ms) y pose (cada 500 ms) no cambia nada que se
 * pueda medir, porque sus reglas exigen 0,5 s y 5 s de duración mínima.
 */
export function tomarTurnoPesado(ahoraMs: number): boolean {
  if (cicloOcupado === ahoraMs) return false
  cicloOcupado = ahoraMs
  return true
}

/** Solo para pruebas. */
export function reiniciarTurnos(): void {
  cicloOcupado = undefined
}
