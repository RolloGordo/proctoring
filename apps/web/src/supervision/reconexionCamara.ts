/**
 * Reintento automático de la cámara (Jesús Limay — atributo de Disponibilidad).
 *
 * Cuando la cámara se desconecta, el estudiante tenía que reconectarla **y**
 * pulsar «Reintentar cámara». Con esto basta con reconectarla: el navegador
 * avisa con `devicechange` y, si vuelve a haber una cámara, la supervisión se
 * reinicia sola. El botón sigue ahí por si el navegador no avisa (algunos
 * controladores no lo hacen).
 *
 * Es una táctica de *recuperación*: reduce el tiempo sin supervisión visual
 * sin depender de que alguien lea un aviso durante el examen.
 */

/** Lo mínimo de `navigator.mediaDevices` que hace falta. Así se prueba sin navegador. */
export interface DispositivosMedia {
  addEventListener(tipo: 'devicechange', escucha: () => void): void
  removeEventListener(tipo: 'devicechange', escucha: () => void): void
  enumerateDevices(): Promise<Array<{ kind: string }>>
}

export interface OpcionesReconexion {
  /**
   * Cuánto se espera tras el último `devicechange` antes de reintentar.
   * Al enchufar una webcam USB llegan varios avisos seguidos; reabrirla en el
   * primero suele fallar porque el sistema aún no terminó de registrarla.
   */
  esperaMs?: number
  /** Tope de reintentos automáticos por desconexión: un cable flojo no debe hacer un bucle. */
  maximo?: number
}

export const ESPERA_RECONEXION_MS = 1_500
export const MAXIMO_REINTENTOS_AUTOMATICOS = 3

/**
 * Escucha la reconexión y llama `alReconectar` cuando vuelve a haber cámara.
 * Devuelve la función que deja de escuchar. Nunca lanza.
 */
export function escucharReconexionCamara(
  dispositivos: DispositivosMedia | undefined,
  alReconectar: () => void,
  {
    esperaMs = ESPERA_RECONEXION_MS,
    maximo = MAXIMO_REINTENTOS_AUTOMATICOS
  }: OpcionesReconexion = {}
): () => void {
  if (!dispositivos) return () => {}
  let reloj: ReturnType<typeof setTimeout> | undefined
  let intentos = 0
  let activo = true

  const comprobar = async () => {
    try {
      const lista = await dispositivos.enumerateDevices()
      if (!activo || intentos >= maximo) return
      if (lista.some((d) => d.kind === 'videoinput')) {
        intentos += 1
        alReconectar()
      }
    } catch {
      // Sin permiso para enumerar no hay nada que hacer: queda el botón.
    }
  }

  const alCambiar = () => {
    clearTimeout(reloj)
    reloj = setTimeout(() => void comprobar(), esperaMs)
  }

  try {
    dispositivos.addEventListener('devicechange', alCambiar)
  } catch {
    return () => {}
  }
  return () => {
    activo = false
    clearTimeout(reloj)
    try {
      dispositivos.removeEventListener('devicechange', alCambiar)
    } catch {
      // Ya no importa.
    }
  }
}
