/**
 * Cuándo se da por caída la conexión durante un examen (reconexión, Rider).
 *
 * Dar por caída la conexión **bloquea el examen** de un estudiante y le deja
 * una marca al docente, así que un solo sondeo lento no puede bastar: con la
 * API cargada una respuesta tarda más de un segundo sin que nadie haya perdido
 * la red, y todos los que rinden verían la pantalla en blanco a la vez.
 *
 * - Sin red según el navegador (`offline`): caída inmediata. Es el caso de
 *   desenchufar el cable, y ahí no hay nada que esperar.
 * - Si lo que falla es el sondeo a la API: hacen falta `FALLOS_PARA_CAER`
 *   seguidos.
 * - Para volver basta un sondeo bueno.
 */
export const FALLOS_PARA_CAER = 2

/**
 * Cada cuánto se sondea. Espaciado mientras todo va bien: con 1.000
 * estudiantes, sondear cada 2 s serían 500 peticiones por segundo solo para
 * preguntar «¿sigues ahí?». Seguido cuando ya se cayó, para volver pronto.
 */
export const SONDEO_SANO_MS = 15_000
export const SONDEO_CAIDO_MS = 2_000
/** Lo que se espera a `/health` antes de contar el sondeo como fallido. */
export const ESPERA_SONDEO_MS = 4_000

export class EstadoConexion {
  private fallos = 0
  private caida = false

  get conectado(): boolean {
    return !this.caida
  }

  /** El navegador dice que no hay red. Devuelve si esto cambió el estado. */
  sinRed(): boolean {
    this.fallos = FALLOS_PARA_CAER
    return this.caer()
  }

  /** Resultado de un sondeo. Devuelve `'cayo'`, `'volvio'` o `null` si sigue igual. */
  sondeo(respondio: boolean): 'cayo' | 'volvio' | null {
    if (respondio) {
      this.fallos = 0
      if (!this.caida) return null
      this.caida = false
      return 'volvio'
    }
    this.fallos += 1
    return this.fallos >= FALLOS_PARA_CAER && this.caer() ? 'cayo' : null
  }

  private caer(): boolean {
    if (this.caida) return false
    this.caida = true
    return true
  }
}
