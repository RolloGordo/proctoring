/**
 * El contrato que cumple un detector.
 *
 * **Esto es lo que hay que implementar para añadir una detección.** Un detector
 * no sabe nada de la API, ni de histéresis, ni de cuándo emitir: solo mira un
 * fotograma (o un fragmento de audio) y dice si la condición se cumple **ahora
 * mismo**. De agrupar eso en un evento con duración se encarga
 * `SeguimientoCondicion`, y de enviarlo, el emisor.
 *
 * Así quien escriba el detector de mirada solo tiene que resolver el problema de
 * la mirada.
 */

import type { EventType } from '../lib/api'

/** Lo que un detector observa en un instante. */
export interface Observacion {
  /** El fotograma actual. `null` si el detector no necesita vídeo. */
  video: HTMLVideoElement | null
  /** Hora del fotograma, en milisegundos. Viene de fuera para poder probar. */
  ahoraMs: number
}

/** El veredicto instantáneo de un detector. */
export interface Veredicto {
  /** Si la condición se cumple **en este instante**. */
  activa: boolean
  /**
   * Los números que midió, tal cual.
   *
   * Van a `metadata` del evento y son lo que después sostiene el informe de
   * accuracy y de FPR: guarda los umbrales usados y los valores medidos, no solo
   * la conclusión. Por ejemplo `{ yaw_deg: 31.2, threshold_deg: 25 }`.
   */
  metadata?: Record<string, unknown>
}

export interface Detector {
  /** Identificador corto, para los registros. */
  readonly nombre: string
  /** Qué evento emite cuando la condición se cierra. */
  readonly evento: EventType
  /**
   * Cuánto tiene que durar la condición para que valga la pena contarla.
   *
   * Sale de la configuración del módulo en la sesión, no se escribe fijo aquí.
   */
  readonly minimoMs: number
  /**
   * Prepara lo que haga falta (cargar el modelo, por ejemplo).
   *
   * Se llama una vez, antes del primer `observar`. Si falla, el detector se
   * descarta y el examen **sigue**: un modelo que no carga no puede dejar a un
   * estudiante sin rendir.
   */
  preparar?(): Promise<void>
  /** Mira el instante actual. Tiene que ser rápido: corre muchas veces por segundo. */
  observar(observacion: Observacion): Veredicto
  /** Libera lo que haya reservado. */
  detener?(): void
}

/** Lo que el emisor manda a la API cuando una condición se cierra. */
export interface SenalDetectada {
  evento: EventType
  inicioMs: number
  duracionMs: number
  metadata: Record<string, unknown>
}
