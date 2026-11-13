/**
 * Mensajes entre la página y el motor de visión (`motor.worker.ts`).
 * Solo tipos: lo importan las dos puntas, así no pueden desfasarse.
 */
import type { RostroCompactoCore } from './vision-core'
import type { PuntoPose } from './encuadre-core'

export type ModeloVision = 'rostro' | 'objetos' | 'pose'

export interface TareasCuadro {
  rostro: boolean
  objetos: boolean
  pose: boolean
}

export type MensajeAlMotor =
  | { tipo: 'cargar'; id: number; modelo: ModeloVision; numFaces?: number; umbral?: number }
  | { tipo: 'cuadro'; id: number; imagen: ImageBitmap; tareas: TareasCuadro }

/** Lo mínimo del rostro que usan las reglas de `vision.ts` (ver `compactarRostro`). */
export type RostroCompacto = RostroCompactoCore

export interface ResultadoCuadro {
  id: number
  rostro?: RostroCompacto
  objetos?: Array<{ nombre: string; score: number }>
  pose?: PuntoPose[][]
  /** Cuánto tardó cada modelo dentro del worker. */
  ms: Partial<Record<ModeloVision, number>>
}

export type MensajeDelMotor =
  | { tipo: 'cargado'; id: number; modelo: ModeloVision }
  | { tipo: 'resultado'; resultado: ResultadoCuadro }
  | { tipo: 'error'; id: number; detalle: string }
