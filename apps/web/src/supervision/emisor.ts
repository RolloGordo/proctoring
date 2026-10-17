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
import { uploadImage } from './imageUpload'

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
  /** Intentos seguidos sin conseguir vaciar la cola. Solo para avisar. */
  private fallosSeguidos = 0

  /**
   * Avisa de que se perdió un fragmento de audio y la señal no se emitió.
   *
   * Opcional porque las pruebas del emisor no necesitan la base de datos, y
   * porque perder el fragmento no puede hacer fallar nada más.
   */
  constructor(
    private contexto: ContextoEmision,
    private readonly alPerderAudio?: (motivo: string) => void
  ) {}

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
            try {
              senal.evidencePath = await uploadAudio(senal.audio, context)
            } catch (falloSubida) {
              // **Con el audio no se hace lo mismo que con la imagen.**
              //
              // Para `gaze_away` la foto corrobora: el evento se sostiene solo
              // con su metadata (grados de yaw, número de caras), y perder la
              // captura no lo invalida. Para la voz, el fragmento **es** toda
              // la evidencia: las dos condiciones que exige el proyecto -que lo
              // dicho se parezca al enunciado y que responda una voz sintética-
              // las calcula el worker a partir del audio. Sin el fragmento
              // quedaría una «voz detectada» que nadie puede comprobar nunca,
              // y eso es exactamente la acusación sin respaldo que no se hace:
              // leer en voz alta no es una infracción.
              //
              // Se descarta la señal y se registra como lo que es, un fallo de
              // disponibilidad, para que el docente sepa que ese rato no se
              // estuvo oyendo.
              console.error('[supervisión] fragmento de audio perdido; no se emite voz', falloSubida)
              this.alPerderAudio?.(
                falloSubida instanceof Error ? falloSubida.message.slice(0, 200) : 'desconocido'
              )
              this.cola.shift()
              this.fallosSeguidos = 0
              continue
            }
            senal.audio = undefined
          }
          if (senal.image && !senal.evidencePath) {
            const image = await senal.image
            if (image) {
              try {
                senal.evidencePath = await uploadImage(image, context)
              } catch (falloSubida) {
                // **Que falle la evidencia no puede borrar la señal.** Si la
                // subida lanzaba, se perdía el evento entero: el docente no veía
                // la captura *ni* se enteraba de que había pasado algo. Y lo
                // segundo es lo que de verdad importa.
                console.error(
                  '[supervisión] no se pudo subir la captura; se manda el evento sin foto',
                  falloSubida
                )
                senal.metadata = { ...senal.metadata, capture_error: 'upload_failed' }
              }
              senal.image = undefined
            } else {
              senal.metadata = { ...senal.metadata, capture_error: 'no_jpeg' }
              senal.image = undefined
            }
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
          this.fallosSeguidos = 0
        } catch (fallo) {
          // 4xx: la señal es inválida y reintentarla fallaría igual para siempre.
          // Se descarta y se sigue, o la cola se atasca con una sola señal mala.
          if (fallo instanceof ApiError && fallo.status < 500 && fallo.status !== 429) {
            console.error('[supervisión] señal rechazada por la API:', fallo.message, senal)
            this.cola.shift()
            continue
          }
          // Red caída o error del servidor: se reintenta sin perder nada.
          //
          // Pero se dice. Esto reintentaba en silencio para siempre: con la
          // cola atascada en la primera señal, ninguna de las siguientes llegaba
          // nunca y no quedaba ni una línea en consola. Buscando por qué no se
          // registraba nada, descartar esto costó horas.
          this.fallosSeguidos += 1
          if (this.fallosSeguidos === 1 || this.fallosSeguidos % 5 === 0) {
            console.error(
              `[supervisión] la cola no avanza (${this.fallosSeguidos} intentos, ${this.cola.length} señales esperando):`,
              fallo
            )
          }
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
