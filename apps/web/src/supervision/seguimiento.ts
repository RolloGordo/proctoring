/**
 * Convierte una condición que se evalúa muchas veces por segundo en **un solo
 * evento**, con cuánto duró.
 *
 * Es la pieza que más fácil se hace mal y la que más pesa en la meta de falsos
 * positivos. El contrato del proyecto lo dice:
 *
 * > Las detecciones con duración (`focus_lost`, `gaze_away`, `face_absent`,
 * > `screen_share`) emiten **un solo evento al cerrarse la condición**, con
 * > cuánto duró. Emitir uno por frame multiplica los falsos positivos y revienta
 * > la meta de FPR < 20 %.
 *
 * Dos reglas, y las dos importan:
 *
 * 1. **Duración mínima.** Mirar de reojo medio segundo no es mirar fuera de la
 *    pantalla. Por debajo del mínimo no se emite nada.
 * 2. **Tolerancia al parpadeo.** Un detector pierde el rostro un frame suelto
 *    todo el tiempo. Sin esta tolerancia, una sola ausencia de 20 segundos se
 *    convertiría en quince eventos cortos, ninguno de los cuales llega al
 *    mínimo, y el docente no vería nada.
 *
 * No sabe nada de cámaras ni de modelos: recibe `true`/`false` y una hora. Por
 * eso se puede probar entera, que es justo lo que hace falta aquí.
 */

/** Una condición que empezó y terminó. Es lo que se convierte en evento. */
export interface Episodio {
  /** Hora en que empezó, en milisegundos desde la época. */
  inicioMs: number
  /** Cuánto duró, descontando el parpadeo final. */
  duracionMs: number
}

export interface OpcionesSeguimiento {
  /** Por debajo de esto no se emite nada. */
  minimoMs: number
  /**
   * Cuánto puede desaparecer la condición sin que se considere terminada.
   *
   * Por defecto 400 ms: más que un frame perdido, menos de lo que tarda alguien
   * en volver a mirar la pantalla.
   */
  toleranciaParpadeoMs?: number
}

const TOLERANCIA_PARPADEO_MS = 400

/**
 * Sigue una condición a lo largo del tiempo.
 *
 * Uso: llamar a `actualizar(activa, ahora)` tan a menudo como se quiera. Cuando
 * devuelve un `Episodio`, hay que emitir el evento. Al terminar el examen, hay
 * que llamar a `cerrar()`: si no, una condición que seguía activa se perdería.
 */
export class SeguimientoCondicion {
  private readonly minimoMs: number
  private readonly toleranciaMs: number

  /** Cuándo empezó la condición en curso. `null` si no hay ninguna. */
  private inicioMs: number | null = null
  /** Última vez que se vio activa. Sirve para medir el parpadeo. */
  private ultimaActivaMs: number | null = null

  constructor({ minimoMs, toleranciaParpadeoMs = TOLERANCIA_PARPADEO_MS }: OpcionesSeguimiento) {
    this.minimoMs = minimoMs
    this.toleranciaMs = toleranciaParpadeoMs
  }

  /** Si ahora mismo hay una condición en curso (aunque sea demasiado corta). */
  get activa(): boolean {
    return this.inicioMs !== null
  }

  /**
   * Registra el estado de la condición.
   *
   * @returns el episodio si acaba de cerrarse y duró lo suficiente; `null` en
   *   cualquier otro caso.
   */
  actualizar(activa: boolean, ahora: number): Episodio | null {
    if (activa) {
      if (this.inicioMs === null) this.inicioMs = ahora
      this.ultimaActivaMs = ahora
      return null
    }

    if (this.inicioMs === null || this.ultimaActivaMs === null) return null

    // Todavía dentro de la tolerancia: puede ser un frame perdido, no el final.
    if (ahora - this.ultimaActivaMs < this.toleranciaMs) return null

    return this.terminar()
  }

  /**
   * Cierra la condición en curso, si la hay.
   *
   * Hay que llamarlo al terminar el examen o al apagar la cámara: una condición
   * abierta que no se cierra es evidencia que se pierde.
   */
  cerrar(): Episodio | null {
    return this.terminar()
  }

  private terminar(): Episodio | null {
    const inicio = this.inicioMs
    const ultima = this.ultimaActivaMs
    this.inicioMs = null
    this.ultimaActivaMs = null

    if (inicio === null || ultima === null) return null

    // La duración llega hasta la última vez que se vio activa, no hasta ahora:
    // el tiempo de parpadeo no es parte de la condición.
    const duracionMs = ultima - inicio
    return duracionMs >= this.minimoMs ? { inicioMs: inicio, duracionMs } : null
  }
}
