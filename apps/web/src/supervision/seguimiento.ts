/**
 * Convierte una condición que se evalúa muchas veces por segundo en **un
 * episodio**, con cuánto duró.
 *
 * Es la pieza que más fácil se hace mal y la que más pesa en la meta de falsos
 * positivos. Emitir un evento por fotograma multiplica los falsos positivos y
 * revienta la meta de FPR < 20 %. Pero esperar a que la condición termine
 * tampoco sirve: el docente tiene que enterarse **mientras** pasa (alerta en
 * menos de 5 s, objetivo SMART).
 *
 * Por eso un episodio se **informa varias veces, siempre con el mismo id**:
 *
 * 1. al cumplirse el mínimo (`cerrado: false`), sin esperar a que termine;
 * 2. mientras sigue abierto, cada `REPORTE_CORTO_MS` hasta `CAMBIO_DE_RITMO_MS`
 *    y luego cada `REPORTE_LARGO_MS`, con la duración que lleva
 *    (`cerrado: false`);
 * 3. al cerrarse, o al terminar el examen con `cerrar()`, con la duración
 *    final (`cerrado: true`).
 *
 * La API cuenta cada `episode_id` **una sola vez**: el riesgo se queda con su
 * duración más larga y solo se avisa al docente cuando el episodio sube de
 * severidad. Los eventos siguen siendo de solo inserción: no se reescribe
 * evidencia, se añade.
 *
 * **El fallo que esto corrige** (prueba de carga del 18/11/2026): antes el
 * episodio se emitía una sola vez al cumplir el mínimo, con la duración del
 * mínimo, y al cerrarse no se emitía nada. Con mínimos de 3 s en el cliente y
 * umbrales de 5 s / 15 s en el servidor, una ausencia de rostro de tres minutos
 * llegaba como «3 s, leve» y el docente no recibía ninguna alerta.
 *
 * Y las dos reglas de siempre, que importan igual:
 *
 * - **Duración mínima.** Mirar de reojo medio segundo no es mirar fuera de la
 *   pantalla: por debajo del mínimo no se informa nada.
 * - **Tolerancia al parpadeo.** Un detector pierde el rostro un frame suelto
 *   todo el tiempo. Sin esta tolerancia, una sola ausencia de 20 segundos se
 *   convertiría en quince episodios cortos, ninguno de los cuales llega al
 *   mínimo, y el docente no vería nada.
 *
 * No sabe nada de cámaras ni de modelos: recibe `true`/`false` y una hora. Por
 * eso se puede probar entera, que es justo lo que hace falta aquí.
 */

import type { SenalDetectada } from './tipos'

/** Un informe de un episodio. Es lo que se convierte en evento. */
export interface Episodio {
  /** Igual en todos los informes del mismo episodio. Viaja como `episode_id`. */
  id: string
  /** Hora en que empezó, en milisegundos desde la época. */
  inicioMs: number
  /** Cuánto lleva (o cuánto duró, si está cerrado), descontando el parpadeo final. */
  duracionMs: number
  /** `true` en el último informe: la condición terminó o se cerró el examen. */
  cerrado: boolean
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
  /** Genera el id de cada episodio. Se inyecta para poder probar. */
  generarId?: () => string
}

const TOLERANCIA_PARPADEO_MS = 400

/**
 * Cada cuánto se vuelve a informar un episodio abierto, al principio.
 *
 * Los umbrales del servidor (`services/api/.../domain/severity.py`) caen en
 * múltiplos de 5 s (5, 10, 15 y 30 s), así que un episodio abierto se informa
 * en el mismo fotograma en que cruza cada umbral: la alerta sale a tiempo, no
 * al terminar.
 */
export const REPORTE_CORTO_MS = 5_000
/** A partir de aquí ya se cruzaron todos los umbrales; basta con menos ritmo. */
export const CAMBIO_DE_RITMO_MS = 30_000
/** Cada cuánto se informa un episodio abierto largo, para que la duración no se quede vieja. */
export const REPORTE_LARGO_MS = 30_000

/** La duración a la que toca el siguiente informe de un episodio abierto. */
export function siguienteReporteMs(informadoMs: number): number {
  const paso = informadoMs < CAMBIO_DE_RITMO_MS ? REPORTE_CORTO_MS : REPORTE_LARGO_MS
  return (Math.floor(informadoMs / paso) + 1) * paso
}

/**
 * La señal que se emite por un informe de episodio.
 *
 * `episode_id` y `episode_closed` van en `metadata` (el contrato la deja
 * abierta): con eso la API reconoce los informes del mismo episodio y lo
 * cuenta una sola vez.
 */
export function senalDeEpisodio(
  evento: SenalDetectada['evento'],
  episodio: Episodio,
  metadata: Record<string, unknown> | undefined,
  image?: Promise<Blob | null>
): SenalDetectada {
  return {
    evento,
    inicioMs: episodio.inicioMs,
    duracionMs: episodio.duracionMs,
    metadata: { ...metadata, episode_id: episodio.id, episode_closed: episodio.cerrado },
    ...(image ? { image } : {})
  }
}

function idAleatorio(): string {
  return globalThis.crypto.randomUUID()
}

/**
 * Sigue una condición a lo largo del tiempo.
 *
 * Uso: llamar a `actualizar(activa, ahora)` tan a menudo como se quiera. Cuando
 * devuelve un `Episodio`, hay que emitir el evento. Al terminar el examen, hay
 * que llamar a `cerrar()`: si había una condición abierta, devuelve su informe
 * final con la duración completa.
 */
export class SeguimientoCondicion {
  private readonly minimoMs: number
  private readonly toleranciaMs: number
  private readonly generarId: () => string

  /** Cuándo empezó la condición en curso. `null` si no hay ninguna. */
  private inicioMs: number | null = null
  /** Última vez que se vio activa. Sirve para medir el parpadeo. */
  private ultimaActivaMs: number | null = null
  /** Id del episodio en curso, desde que se informó por primera vez. */
  private idEpisodio: string | null = null
  /** Duración del último informe del episodio en curso. */
  private informadoMs = 0

  constructor({
    minimoMs,
    toleranciaParpadeoMs = TOLERANCIA_PARPADEO_MS,
    generarId = idAleatorio
  }: OpcionesSeguimiento) {
    this.minimoMs = minimoMs
    this.toleranciaMs = toleranciaParpadeoMs
    this.generarId = generarId
  }

  /** Si ahora mismo hay una condición en curso (aunque sea demasiado corta). */
  get activa(): boolean {
    return this.inicioMs !== null
  }

  /** Si el episodio en curso ya se informó al menos una vez. */
  get informado(): boolean {
    return this.idEpisodio !== null
  }

  /**
   * Registra el estado de la condición.
   *
   * @returns un informe del episodio si toca emitirlo (cumplió el mínimo,
   *   llegó a otro punto de informe o acaba de cerrarse); `null` en cualquier
   *   otro caso.
   */
  actualizar(activa: boolean, ahora: number): Episodio | null {
    if (activa) {
      if (this.inicioMs === null) this.inicioMs = ahora
      this.ultimaActivaMs = ahora
      const duracionMs = ahora - this.inicioMs
      if (duracionMs < this.minimoMs) return null
      if (this.idEpisodio !== null && duracionMs < siguienteReporteMs(this.informadoMs)) {
        return null
      }

      this.idEpisodio ??= this.generarId()
      this.informadoMs = duracionMs
      return { id: this.idEpisodio, inicioMs: this.inicioMs, duracionMs, cerrado: false }
    }

    if (this.inicioMs === null || this.ultimaActivaMs === null) return null

    // Todavía dentro de la tolerancia: puede ser un frame perdido, no el final.
    if (ahora - this.ultimaActivaMs < this.toleranciaMs) return null

    return this.terminar()
  }

  /**
   * Cierra la condición en curso, si la hay, y devuelve su informe final.
   *
   * Hay que llamarlo al terminar el examen o al apagar la cámara: una condición
   * abierta que no se cierra es evidencia que se pierde, y sin el informe
   * final la duración se queda en la del último informe parcial.
   */
  cerrar(): Episodio | null {
    return this.terminar()
  }

  private terminar(): Episodio | null {
    const inicio = this.inicioMs
    const ultima = this.ultimaActivaMs
    const id = this.idEpisodio
    this.inicioMs = null
    this.ultimaActivaMs = null
    this.idEpisodio = null
    this.informadoMs = 0

    if (inicio === null || ultima === null) return null

    // La duración llega hasta la última vez que se vio activa, no hasta ahora:
    // el tiempo de parpadeo no es parte de la condición.
    const duracionMs = ultima - inicio
    if (id === null && duracionMs < this.minimoMs) return null
    return { id: id ?? this.generarId(), inicioMs: inicio, duracionMs, cerrado: true }
  }
}
