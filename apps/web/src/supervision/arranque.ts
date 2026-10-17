/**
 * Arrancar los detectores sin que uno solo pueda tumbar al resto.
 *
 * Se preparaban **en serie y sin límite de tiempo**:
 *
 * ```ts
 * for (const detector of detectores) await detector.preparar?.(...)
 * // el intervalo que observa fotogramas se creaba despues del bucle
 * ```
 *
 * Y el detector de habla es el último de la lista. Cuando el VAD se quedaba
 * colgado al arrancar —`MicVAD.new()` no resuelve ni rechaza si la carga del
 * worker de ONNX se atasca— el bucle no terminaba nunca, así que el intervalo
 * no llegaba a crearse: **los tres detectores de cámara no miraban un solo
 * fotograma y tampoco constaban como caídos**, porque nunca se les llegó a
 * preguntar. El estado se quedaba en «iniciando», el estudiante se quedaba sin
 * ver su propia cámara, y el expediente del docente quedaba vacío.
 *
 * Dos cambios, y los dos importan:
 *
 * - **A la vez, no en fila.** Prepararlos en paralelo cuesta lo mismo y quita
 *   el orden de la lista de en medio: que la voz vaya después de la mirada no
 *   puede decidir si hay supervisión de mirada.
 * - **Con límite de tiempo.** Una promesa que no vuelve es peor que un error,
 *   porque un error al menos se ve. Pasado el plazo, ese detector consta como
 *   caído, con su motivo, y los demás siguen.
 */

import type { Detector, DetectorContext } from './tipos'

/**
 * Cuánto se espera a que un detector arranque.
 *
 * Quince segundos son de sobra: MediaPipe crea el modelo en ~1,5 s medido en
 * producción, y el VAD carga unos 13 MB de WASM. Pasarse de generoso aquí no
 * es prudencia, es dejar al estudiante mirando una pantalla que no le dice
 * nada.
 */
export const LIMITE_ARRANQUE_MS = 15_000

/** El resultado de intentar arrancar un detector. */
export interface Arranque {
  detector: Detector
  listo: boolean
  /** Por qué no arrancó. Va al diagnóstico, así que se guarda corto. */
  motivo?: string
}

/** Rechaza si la promesa no se resuelve a tiempo. No la cancela: no se puede. */
export async function conLimite<T>(promesa: Promise<T>, ms: number): Promise<T> {
  let reloj: ReturnType<typeof setTimeout> | undefined
  try {
    return await Promise.race([
      promesa,
      new Promise<never>((_, rechazar) => {
        reloj = setTimeout(() => rechazar(new Error(`No arrancó en ${ms} ms.`)), ms)
      })
    ])
  } finally {
    clearTimeout(reloj)
  }
}

/**
 * Prepara todos los detectores a la vez y dice cuáles quedaron listos.
 *
 * Nunca lanza: un detector que no arranca es información, no una excepción que
 * deba interrumpir el examen. Al que falla se le llama `detener()` para que no
 * deje el micrófono o un worker encendido.
 */
export async function prepararDetectores(
  detectores: readonly Detector[],
  contexto: DetectorContext,
  limiteMs = LIMITE_ARRANQUE_MS
): Promise<Arranque[]> {
  return Promise.all(
    detectores.map(async (detector): Promise<Arranque> => {
      try {
        await conLimite(Promise.resolve(detector.preparar?.(contexto)), limiteMs)
        return { detector, listo: true }
      } catch (fallo) {
        try {
          detector.detener?.()
        } catch {
          // Si ni apagarse puede, no hay nada mejor que hacer aqui.
        }
        return {
          detector,
          listo: false,
          motivo: fallo instanceof Error ? fallo.message.slice(0, 200) : 'desconocido'
        }
      }
    })
  )
}
