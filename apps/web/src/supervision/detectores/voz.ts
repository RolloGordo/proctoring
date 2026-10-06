/**
 * Detección de habla (`speech_detected`). **Es una plantilla: no detecta nada.**
 *
 * Aquí se enchufa Silero VAD (SPEC-008, Pierreluiggi). Es el detector más
 * distinto de los demás, porque **no basta con emitir el evento**: hay que subir
 * el fragmento de audio, o el worker no tendrá nada que transcribir.
 *
 * ## El flujo completo
 *
 * 1. El VAD dice que hay voz → `activa: true`.
 * 2. Cuando la condición se cierra, hay que:
 *    a. pedir una URL firmada: `POST /api/v1/evidence/upload-url` con
 *       `kind: "audio"` y la extensión (`webm`),
 *    b. subir el fragmento **directo a Storage** con esa URL,
 *    c. mandar el evento con `evidence_path` = la ruta devuelta.
 * 3. La API encola `tasks.analyze_audio` y el worker hace el resto.
 *
 * El audio **nunca pasa por la API**: es la regla de ADR-0004 y lo que hace
 * viable el plan gratuito.
 *
 * ## Lo que no se graba
 *
 * Solo los fragmentos **con habla**, nunca el micrófono continuo. Un examen de
 * 90 minutos grabado entero son cientos de megas y, sobre todo, es grabar a
 * alguien en su casa durante hora y media.
 *
 * ## La regla que no se toca
 *
 * `speech_detected` nace siempre con severidad **baja**. Hablar en voz alta es
 * legítimo. Solo la API, con lo que mida el worker (parecido al enunciado **y**
 * segunda voz sintética), puede escalarlo. No intentes decidirlo aquí.
 */

import type { Detector, Observacion, Veredicto } from '../tipos'

export interface AjustesVoz {
  /** Proporción de habla a partir de la cual se considera que alguien habló. */
  speech_ratio?: number
  min_duration_ms?: number
}

export class DetectorHabla implements Detector {
  readonly nombre = 'habla'
  readonly evento = 'speech_detected' as const
  readonly minimoMs: number
  private readonly umbralHabla: number

  constructor(ajustes: AjustesVoz = {}) {
    this.minimoMs = ajustes.min_duration_ms ?? 1500
    this.umbralHabla = ajustes.speech_ratio ?? 0.6
  }

  async preparar(): Promise<void> {
    // TODO(SPEC-008, Pierreluiggi): cargar Silero VAD (onnxruntime-web) y abrir
    //   un MediaRecorder sobre la pista de audio, para tener el fragmento listo
    //   cuando la condición se cierre.
  }

  observar(_observacion: Observacion): Veredicto {
    // TODO(SPEC-008, Pierreluiggi): devolver `activa: true` mientras el VAD
    //   detecte voz, con metadata { source: 'silero_vad', sample_rate,
    //   speech_ratio }.
    return { activa: false, metadata: { speech_ratio_threshold: this.umbralHabla } }
  }

  detener(): void {
    // TODO(SPEC-008): parar el MediaRecorder y liberar el modelo.
  }
}
