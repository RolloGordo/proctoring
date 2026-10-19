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
import { conLimite } from './arranque'

/** Tope de la cola. Más que esto es que la red lleva mucho rato caída. */
const MAX_EN_COLA = 200
const REINTENTO_MS = 5_000

/**
 * Cuánto se espera por la evidencia de una señal antes de mandarla sin ella.
 *
 * **Nada de esto puede esperarse para siempre.** `capturarFotograma` envuelve
 * `canvas.toBlob`, que no rechaza nunca si no llama de vuelta, y las peticiones
 * a la API no traían tiempo límite. Una espera que no vuelve dejaba el `while`
 * de `vaciar()` parado con `enviando` en true, y a partir de ahí **todas** las
 * señales siguientes se encolaban sin que nadie las sacara. Sin `catch`, así
 * que sin una sola línea en consola.
 *
 * Es la explicación de que en todo el historial del proyecto no haya ni un
 * `evidence_path`: la primera captura mataba la cola.
 */
const LIMITE_EVIDENCIA_MS = 20_000

/**
 * Cuánto se espera a que la API acepte el evento.
 *
 * Más generoso porque el plan gratuito duerme el servicio y despertarlo pasa
 * del minuto. Pasado el plazo se reintenta, que es lo correcto: el evento no se
 * pierde, solo tarda.
 */
const LIMITE_API_MS = 70_000

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
  private enVuelo: Promise<void> | null = null
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
    private readonly alPerderAudio?: (motivo: string) => void,
    private readonly alPerderImagen?: (motivo: string) => void,
    /**
     * Avisa de que la API rechazo una senal y se descarto.
     *
     * Existe porque el motivo moria en `console.error`, y en una ventana en
     * modo kiosco nadie abre la consola. Una senal observada que desaparece
     * sin dejar constancia es el peor fallo posible aqui: en el expediente se
     * lee igual que si no hubiera pasado nada.
     */
    private readonly alRechazar?: (evento: EventType, motivo: string) => void,
    /** Avisa de que la cola lleva mucho rato sin avanzar. */
    private readonly alAtascarse?: (intentos: number, pendientes: number) => void,
    /** Avisa de que un fragmento de voz no llego ni a entrar en la cola. */
    private readonly alDescartarVoz?: (motivo: string) => void
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
    ) {
      // **No en silencio.** Esto devolvia sin mas: un fragmento de voz que el
      // VAD si oyo desaparecia antes de salir, y en el expediente se leia
      // igual que si nadie hubiera hablado. El motivo importa: sin pregunta en
      // curso el worker no tiene con que comparar, y sin audio no hay nada que
      // analizar, pero son dos problemas distintos.
      const motivo = !context.questionId ? 'sin pregunta en curso' : 'sin audio'
      console.error('[supervisión] fragmento de voz descartado antes de salir:', motivo)
      this.alDescartarVoz?.(motivo)
      return
    }
    if (senal.audio && this.cola.filter((entry) => entry.signal.audio).length >= 3) {
      console.error('[supervisión] cola de audio llena; fragmento descartado')
      return
    }
    this.cola.push({ signal: senal, context })
    void this.vaciar()
  }

  /**
   * Manda lo que quede. Hay que llamarlo al salir del examen.
   *
   * Dos vueltas: la primera espera al envio que ya estuviera en curso, la
   * segunda manda lo que se haya encolado mientras tanto. `detenido` impide
   * que entre nada nuevo, asi que con dos basta.
   */
  async cerrar(): Promise<void> {
    this.detenido = true
    clearTimeout(this.temporizador)
    for (let vuelta = 0; vuelta < 2 && this.cola.length > 0; vuelta += 1) {
      await this.vaciar()
    }
  }

  /**
   * Vacia la cola, o espera al vaciado que ya estuviera en curso.
   *
   * **Esperar, no rendirse.** Esto devolvia nada mas ver un envio en vuelo, asi
   * que `cerrar()` podia volver con senales todavia sin mandar y la pantalla se
   * desmontaba encima. Es el mismo fallo que perdia la ultima respuesta del
   * estudiante, en otro fichero.
   */
  private async vaciar(): Promise<void> {
    if (this.enVuelo) {
      await this.enVuelo
      return
    }
    this.enVuelo = this.drenar()
    try {
      await this.enVuelo
    } finally {
      this.enVuelo = null
    }
  }

  private async drenar(): Promise<void> {
    {
      while (this.cola.length > 0) {
        const { signal: senal, context } = this.cola[0]
        try {
          if (senal.audio && !senal.evidencePath) {
            try {
              senal.evidencePath = await conLimite(
                uploadAudio(senal.audio, context),
                LIMITE_EVIDENCIA_MS
              )
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
              // Se conserva la señal en la línea de tiempo, marcada como
              // evidencia no disponible. El backend no encolará análisis sin
              // audio. Así el docente puede distinguir habla detectada de
              // silencio aunque Storage haya fallado.
              console.error(
                '[supervisión] fragmento de audio perdido; se registra la señal sin evidencia',
                falloSubida
              )
              const motivo = falloSubida instanceof Error
                ? falloSubida.message.slice(0, 200)
                : 'desconocido'
              this.alPerderAudio?.(motivo)
              senal.metadata = { ...senal.metadata, audio_evidence_error: motivo }
              senal.audio = undefined
            }
            senal.audio = undefined
          }
          if (senal.image && !senal.evidencePath) {
            // También la captura en sí: `toBlob` no rechaza si no responde.
            let image: Blob | null = null
            try {
              image = await conLimite(Promise.resolve(senal.image), LIMITE_EVIDENCIA_MS)
            } catch (falloCaptura) {
              console.error('[supervisión] la captura no llegó a tiempo', falloCaptura)
              senal.metadata = { ...senal.metadata, capture_error: 'capture_timeout' }
              this.alPerderImagen?.('capture_timeout')
            }
            if (image) {
              try {
                senal.evidencePath = await conLimite(
                  uploadImage(image, context),
                  LIMITE_EVIDENCIA_MS
                )
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
                this.alPerderImagen?.(
                  falloSubida instanceof Error ? falloSubida.message.slice(0, 200) : 'upload_failed'
                )
              }
              senal.image = undefined
            } else {
              if (!senal.metadata?.capture_error) {
                senal.metadata = { ...senal.metadata, capture_error: 'no_jpeg' }
              }
              const captureError = senal.metadata?.capture_error
              this.alPerderImagen?.(typeof captureError === 'string' ? captureError : 'no_jpeg')
              senal.image = undefined
            }
          }
          await conLimite(
            api.registerEvent(
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
            ),
            LIMITE_API_MS
          )
          this.cola.shift()
          this.fallosSeguidos = 0
        } catch (fallo) {
          // 4xx: la señal es inválida y reintentarla fallaría igual para siempre.
          // Se descarta y se sigue, o la cola se atasca con una sola señal mala.
          if (fallo instanceof ApiError && fallo.status < 500 && fallo.status !== 429) {
            console.error('[supervisión] señal rechazada por la API:', fallo.message, senal)
            this.alRechazar?.(senal.evento, `${fallo.status}: ${fallo.message}`.slice(0, 200))
            this.cola.shift()
            this.fallosSeguidos = 0
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
          // A la tercera deja de ser un bache de red y pasa a ser algo que el
          // docente tiene que saber al revisar: durante ese rato no se estuvo
          // registrando nada.
          if (this.fallosSeguidos === 3) {
            this.alAtascarse?.(this.fallosSeguidos, this.cola.length)
          }
          this.programarReintento()
          return
        }
      }
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
