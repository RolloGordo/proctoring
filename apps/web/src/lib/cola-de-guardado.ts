import type { NewAnswer } from './api'

/**
 * La cola que guarda las respuestas del estudiante mientras rinde.
 *
 * Vive fuera de React a propósito. Es el camino por el que se pierden o no se
 * pierden las respuestas de alguien en un examen, y dentro de un componente no
 * se podía probar sin montar una pantalla: por eso un fallo aquí llegó a
 * producción y se vio por primera vez en un examen real.
 *
 * Qué hace:
 *
 * - **Agrupa.** Escribir un desarrollo largo dispararía una petición por cada
 *   campo que pierde el foco. Con un lote cada medio segundo, la última
 *   respuesta siempre es la que queda.
 * - **No se pisa a sí misma.** Si hay un envío en vuelo, quien llegue después
 *   lo espera en vez de darlo por inexistente.
 * - **No pierde nada al fallar.** Un lote que no llega vuelve a la cola, salvo
 *   que entre tanto se haya escrito algo más reciente para esa pregunta.
 */
export class ColaDeGuardado {
  private pendientes = new Map<string, NewAnswer>()
  private temporizador?: ReturnType<typeof setTimeout>
  private enVuelo: Promise<void> | null = null

  constructor(
    private readonly enviarLote: (lote: NewAnswer[]) => Promise<void>,
    private readonly alCambiarEstado: (estado: 'guardando' | 'guardado' | 'error') => void,
    private readonly alFallar: (fallo: unknown) => void,
    private readonly esperaMs = 500
  ) {}

  /** Encola una respuesta. La última de cada pregunta es la que vale. */
  encolar(respuesta: NewAnswer): void {
    this.pendientes.set(respuesta.question_id, respuesta)
    clearTimeout(this.temporizador)
    this.temporizador = setTimeout(() => void this.enviar(), this.esperaMs)
  }

  /** Manda ya lo que haya, sin esperar al temporizador. */
  async enviar(): Promise<void> {
    if (this.enVuelo) {
      // **Esperar, no rendirse.** Devolver aquí hacía creer que no había nada
      // que mandar cuando estaba de camino, y al entregar se le decía al
      // estudiante que su última respuesta podía perderse justo cuando sí se
      // estaba guardando.
      await this.enVuelo
      return
    }

    const lote = [...this.pendientes.values()]
    if (lote.length === 0) return
    this.pendientes.clear()

    this.alCambiarEstado('guardando')
    this.enVuelo = (async () => {
      try {
        await this.enviarLote(lote)
        this.alCambiarEstado(this.pendientes.size > 0 ? 'guardando' : 'guardado')
      } catch (fallo) {
        // Vuelve a la cola lo que no llegó, sin pisar nada más reciente: si el
        // estudiante cambió de opinión mientras se enviaba, vale lo nuevo.
        for (const respuesta of lote) {
          if (!this.pendientes.has(respuesta.question_id)) {
            this.pendientes.set(respuesta.question_id, respuesta)
          }
        }
        this.alCambiarEstado('error')
        this.alFallar(fallo)
      } finally {
        this.enVuelo = null
      }
    })()

    await this.enVuelo
  }

  /**
   * Para entregar: manda todo lo que quede y dice si se consiguió.
   *
   * Dos vueltas como mucho. La primera espera al envío en vuelo y la segunda
   * manda lo que se haya acumulado mientras tanto. Insistir más sería un bucle
   * con la red caída, y entregar un examen no puede quedarse esperando a eso.
   */
  async vaciar(): Promise<boolean> {
    clearTimeout(this.temporizador)
    for (let vuelta = 0; vuelta < 2 && this.pendientes.size > 0; vuelta += 1) {
      await this.enviar()
    }
    return this.pendientes.size === 0
  }

  /** Cuántas respuestas siguen sin guardarse. Para las pruebas y el estado. */
  get sinGuardar(): number {
    return this.pendientes.size
  }

  /** Al desmontar: cancela el temporizador pendiente. */
  destruir(): void {
    clearTimeout(this.temporizador)
  }
}
