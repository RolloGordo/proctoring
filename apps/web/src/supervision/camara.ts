/**
 * Cámara y micrófono del estudiante.
 *
 * Reglas del proyecto que esto respeta:
 *
 * - **No se graba ni se envía vídeo continuo.** El `MediaStream` se queda en el
 *   navegador; de él solo salen eventos y, cuando corresponde, capturas sueltas.
 * - Se pide **después** del consentimiento. Esta clase no pide permiso por su
 *   cuenta: la llama la pantalla del examen, que es donde el estudiante ya
 *   aceptó.
 */

export interface OpcionesCamara {
  /** Si hace falta el micrófono (detección de habla). */
  audio?: boolean
  /** Resolución pedida. Pequeña a propósito: los modelos no necesitan más y
   *  una cámara a 1080p calienta el equipo durante una hora de examen. */
  ancho?: number
  alto?: number
}

export type MotivoFallo = 'denegado' | 'sin-camara' | 'en-uso' | 'desconocido'

export class CamaraNoDisponibleError extends Error {
  constructor(
    readonly motivo: MotivoFallo,
    mensaje: string
  ) {
    super(mensaje)
    this.name = 'CamaraNoDisponibleError'
  }
}

/** Traduce el error del navegador a algo que el estudiante pueda accionar. */
function traducir(error: unknown): CamaraNoDisponibleError {
  const nombre = error instanceof DOMException ? error.name : ''
  switch (nombre) {
    case 'NotAllowedError':
    case 'SecurityError':
      return new CamaraNoDisponibleError(
        'denegado',
        'No diste permiso para usar la cámara. Búscalo en la barra de direcciones y vuelve a intentarlo.'
      )
    case 'NotFoundError':
    case 'OverconstrainedError':
      return new CamaraNoDisponibleError('sin-camara', 'No se encontró una cámara conectada.')
    case 'NotReadableError':
      return new CamaraNoDisponibleError(
        'en-uso',
        'Otra aplicación está usando la cámara. Ciérrala y vuelve a intentarlo.'
      )
    default:
      return new CamaraNoDisponibleError('desconocido', 'No se pudo abrir la cámara.')
  }
}

/**
 * Abre la cámara y entrega un `<video>` listo para que los detectores lo miren.
 *
 * Devuelve el elemento y una función para apagarlo. **Hay que llamarla siempre**
 * al terminar: si no, la luz de la cámara se queda encendida.
 */
export async function abrirCamara({
  audio = false,
  ancho = 640,
  alto = 480
}: OpcionesCamara = {}): Promise<{ video: HTMLVideoElement; cerrar: () => void }> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new CamaraNoDisponibleError(
      'desconocido',
      'Este navegador no permite usar la cámara. Usa la aplicación de escritorio.'
    )
  }

  let stream: MediaStream
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: ancho }, height: { ideal: alto }, facingMode: 'user' },
      audio
    })
  } catch (error) {
    throw traducir(error)
  }

  const video = document.createElement('video')
  video.srcObject = stream
  video.muted = true
  video.playsInline = true
  await video.play()

  return {
    video,
    cerrar: () => {
      for (const pista of stream.getTracks()) pista.stop()
      video.srcObject = null
    }
  }
}

/**
 * Captura el fotograma actual como JPEG.
 *
 * **Solo se llama cuando ya hay un evento que justifica la captura**, nunca de
 * forma periódica: es la diferencia entre guardar evidencia y grabar a alguien.
 */
export async function capturarFotograma(
  video: HTMLVideoElement,
  calidad = 0.8
): Promise<Blob | null> {
  const lienzo = document.createElement('canvas')
  lienzo.width = video.videoWidth
  lienzo.height = video.videoHeight
  const contexto = lienzo.getContext('2d')
  if (!contexto) return null
  contexto.drawImage(video, 0, 0, lienzo.width, lienzo.height)
  return new Promise((resolver) => lienzo.toBlob(resolver, 'image/jpeg', calidad))
}
