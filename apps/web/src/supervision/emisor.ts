/**
 * Manda las señales detectadas a la API.
 *
 * Con cola y reintento: durante un examen la red se cae, y una señal perdida es
 * evidencia perdida. Es la misma idea que ya usa el proceso principal de la app
 * de escritorio (`apps/desktop/src/main/sender.ts`).
 */

import { ApiError, api, type EventType } from '../lib/api'
import type { SenalDetectada } from './tipos'
import { uploadAudio } from './audioUpload'

/** Tope de la cola. Más que esto es que la red lleva mucho rato caída. */
const MAX_EN_COLA = 200
const REINTENTO_MS = 5_000

export interface ContextoEmision {
  sessionId: string
  /** Quién rinde. La API exige que coincida con el del token. */
  studentId: string
  /** La pregunta en curso. Obligatoria para `gaze_away` y `speech_detected`. */
  questionId: string | null
  token?: string
}

export class EmisorDeSenales {
  private readonly cola: Array<{ signal: SenalDetectada; context: ContextoEmision }> = []
  private enviando = false
  private temporizador: ReturnType<typeof setTimeout> | undefined
  private detenido = false

  constructor(private contexto: ContextoEmision) {}

  /** Cambia la pregunta en curso sin perder lo que esté en cola. */
  actualizarContexto(contexto: Partial<ContextoEmision>): void {
    this.contexto = { ...this.contexto, ...contexto }
  }

  emitir(senal: SenalDetectada): void {
    this.enqueue(senal, { ...this.contexto })
  }

  /** Capture question at speech onset before asynchronous work. */
  captureSender(): (signal: SenalDetectada) => void {
    const context = { ...this.contexto }
    return (signal) => this.enqueue(signal, context)
  }

  private enqueue(senal: SenalDetectada, context: ContextoEmision): void {
    if (this.detenido) return
    if (this.cola.length >= MAX_EN_COLA) {
      // Preserve the first entry while its upload/request is in flight.
      console.error('[supervisión] cola llena; señal descartada')
      return
    }
    if (
      senal.evento === 'speech_detected' &&
      (!context.questionId || (!senal.audio && !senal.evidencePath))
    )
      return
    if (senal.audio && this.cola.filter((entry) => entry.signal.audio).length >= 3) {
      console.error('[supervisión] cola de audio llena; fragmento descartado')
      return
    }
    this.cola.push({ signal: senal, context })
    void this.vaciar()
  }

  /** Manda lo que quede. Hay que llamarlo al salir del examen. */
  async cerrar(): Promise<void> {
    this.detenido = true
    clearTimeout(this.temporizador)
    await this.vaciar()
  }

  private async vaciar(): Promise<void> {
    if (this.enviando) return
    this.enviando = true
    try {
      while (this.cola.length > 0) {
        const { signal: senal, context } = this.cola[0]
        try {
          if (senal.audio && !senal.evidencePath) {
            senal.evidencePath = await uploadAudio(senal.audio, context)
            senal.audio = undefined
          }
          await api.registerEvent(
            {
              session_id: context.sessionId,
              student_id: context.studentId,
              question_id: context.questionId,
              event_type: senal.evento,
              started_at: new Date(senal.inicioMs).toISOString(),
              duration_ms: Math.round(senal.duracionMs),
              metadata: senal.metadata,
              evidence_path: senal.evidencePath
            },
            context.token
          )
          this.cola.shift()
        } catch (fallo) {
          // 4xx: la señal es inválida y reintentarla fallaría igual para siempre.
          // Se descarta y se sigue, o la cola se atasca con una sola señal mala.
          if (fallo instanceof ApiError && fallo.status < 500 && fallo.status !== 429) {
            console.error('[supervisión] señal rechazada por la API:', fallo.message, senal)
            this.cola.shift()
            continue
          }
          // Red caída o error del servidor: se reintenta sin perder nada.
          this.programarReintento()
          return
        }
      }
    } finally {
      this.enviando = false
    }
  }

  private programarReintento(): void {
    if (this.detenido || this.temporizador) return
    this.temporizador = setTimeout(() => {
      this.temporizador = undefined
      void this.vaciar()
    }, REINTENTO_MS)
  }
}

/** Los eventos que exigen saber en qué pregunta estaba el estudiante. */
export const EVENTOS_CON_PREGUNTA: ReadonlySet<EventType> = new Set<EventType>([
  'gaze_away',
  'speech_detected'
])
