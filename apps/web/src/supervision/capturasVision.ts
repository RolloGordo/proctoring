/** TA-018: una fotografía por episodio sostenido, nunca por fotograma.
 *
 * La captura se solicita mientras la condición sigue activa y ya superó su
 * duración mínima. Se conserva la promesa (no un vídeo) hasta cerrar el evento.
 */
import type { Veredicto } from './tipos'

export class CapturasPorCondicion {
  private inicio: number | null = null
  private ultimaActiva: number | null = null
  private fotografia?: Promise<Blob | null>
  private avisada = false

  constructor(
    private readonly minimoMs: number,
    private readonly toleranciaMs = 400
  ) {}

  /** Devuelve true una sola vez cuando el episodio supera el mínimo. */
  actualizar(
    veredicto: Veredicto,
    ahoraMs: number,
    fotografiar: () => Promise<Blob | null>
  ): boolean {
    if (veredicto.activa) {
      this.inicio ??= ahoraMs
      this.ultimaActiva = ahoraMs
      if (!this.avisada && ahoraMs - this.inicio >= this.minimoMs) {
        this.avisada = true
        // No bloquea el bucle de MediaPipe con una subida de red.
        this.fotografia = Promise.resolve().then(fotografiar).catch(() => null)
        return true
      }
    } else if (
      this.ultimaActiva !== null &&
      ahoraMs - this.ultimaActiva >= this.toleranciaMs
    ) {
      // El episodio terminó: el emisor consume su imagen antes de reiniciar.
      // El borrado real se realiza por `consumir()`.
    }
    return false
  }

  consumir(): Promise<Blob | null> | undefined {
    const foto = this.fotografia
    this.reiniciar()
    return foto
  }

  reiniciar(): void {
    this.inicio = null
    this.ultimaActiva = null
    this.avisada = false
    this.fotografia = undefined
  }
}
