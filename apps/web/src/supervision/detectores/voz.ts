/** Silero VAD + bounded WebM recording using the consented shared stream. */
import type { Detector, DetectorContext, Observacion, SenalDetectada, Veredicto } from '../tipos'

export interface AjustesVoz {
  speech_ratio?: number
  min_duration_ms?: number
}
interface VadHandle {
  start(): Promise<void>
  pause(): Promise<void>
  destroy(): Promise<void>
}

export class DetectorHabla implements Detector {
  readonly nombre = 'habla'
  readonly evento = 'speech_detected' as const
  readonly ownsSegments = true
  readonly minimoMs: number
  private readonly threshold: number
  private vad?: VadHandle
  private context?: DetectorContext
  private recorder?: MediaRecorder
  private timer?: ReturnType<typeof setTimeout>
  private speaking = false
  private stopped = false
  private startedAt = 0
  private chunks: Blob[] = []
  private sender?: (signal: SenalDetectada) => void
  private discard = false
  private stopping?: Promise<void>
  private sampleRate = 0
  private generation = 0
  /**
   * Cuantas veces oyo, cerro y descarto. **El dato que faltaba.**
   *
   * El resumen del docente decia «0 episodios emitidos» para este detector,
   * pero ese contador vive en el bucle de fotogramas y este detector no pasa
   * por ahi (`ownsSegments`): era siempre cero, oyera o no oyera. Asi no se
   * podia distinguir «el microfono no oyo nada» de «oyo y la senal se perdio
   * por el camino», que se arreglan en sitios distintos.
   */
  private oidas = 0
  private enviadas = 0
  private descartadas = 0

  constructor(settings: AjustesVoz = {}) {
    this.minimoMs = settings.min_duration_ms ?? 500
    this.threshold = settings.speech_ratio ?? 0.6
    if (
      !Number.isFinite(this.threshold) ||
      this.threshold <= 0 ||
      this.threshold >= 1 ||
      !Number.isFinite(this.minimoMs) ||
      this.minimoMs < 100 ||
      this.minimoMs > 10000
    ) {
      throw new Error('Configuración de voz inválida.')
    }
  }

  /**
   * Las condiciones que el VAD necesita, en una línea.
   *
   * Va dentro del motivo del fallo porque el examen corre en una ventana en
   * modo kiosco de Electron, donde no hay consola que abrir. Probado contra la
   * web desplegada desde un navegador normal, `MicVAD.new()` y `start()` tardan
   * medio segundo; dentro de la aplicación se pasa de los quince. La diferencia
   * está en alguna de estas condiciones, y adivinar cuál ya costó bastante.
   */
  private entorno(context?: DetectorContext): string {
    const pista = context?.stream.getAudioTracks()[0]
    const ajustes = pista?.getSettings() ?? {}
    return [
      `isolated=${self.crossOriginIsolated}`,
      `sab=${typeof SharedArrayBuffer}`,
      `cores=${navigator.hardwareConcurrency ?? '?'}`,
      `pistas=${context?.stream.getAudioTracks().length ?? 0}`,
      `rate=${ajustes.sampleRate ?? '?'}`,
      `canales=${ajustes.channelCount ?? '?'}`,
      `estado=${pista?.readyState ?? '?'}`
    ].join(' ')
  }

  /**
   * Noventa segundos, y no quince.
   *
   * **Medido, no supuesto.** Antes de poder decir una palabra, este detector
   * baja 12,93 MB: 10,69 del runtime de ONNX multihilo y 2,22 del modelo
   * Silero. A 5 Mbps son casi veintidos segundos solo de descarga, y a 3 Mbps
   * mas de treinta y seis, antes de compilar el WASM.
   *
   * El limite anterior eran quince, elegidos razonando sobre MediaPipe, que
   * tarda segundo y medio. Por eso cada examen registraba «no arranco en 15000
   * ms» con todas las condiciones en orden: no fallaba, no le daba tiempo.
   *
   * Que sea tan largo no retrasa a nadie: los detectores arrancan a la vez y
   * cada uno se incorpora en cuanto esta listo.
   */
  readonly limiteArranqueMs = 90_000

  /** Lo que `prepararDetectores` pregunta cuando se agota el tiempo. */
  diagnostico(): string {
    return `${this.entorno(this.context)} oidas=${this.oidas} enviadas=${this.enviadas} descartadas=${this.descartadas}`
  }

  async preparar(context?: DetectorContext): Promise<void> {
    const generation = ++this.generation
    if (!context?.stream.getAudioTracks().length) throw new Error('Falta la pista de micrófono.')
    if (!MediaRecorder.isTypeSupported('audio/webm;codecs=opus'))
      throw new Error('WebM/Opus no disponible.')
    this.context = context
    this.stopped = false
    this.sampleRate = context.stream.getAudioTracks()[0].getSettings().sampleRate ?? 0
    const { MicVAD } = await import('@ricky0123/vad-web')
    if (this.stopped || generation !== this.generation) return

    // Cada etapa por separado: «no arrancó» no dice lo mismo si se quedó
    // cargando el modelo que si se quedó al abrir la pista de audio, y hasta
    // ahora las dos daban el mismo mensaje.
    let etapa = 'cargando el modelo'
    try {
      const vad = await MicVAD.new({
        model: 'v5',
        startOnLoad: false,
        baseAssetPath: '/vad/',
        onnxWASMBasePath: '/vad/',
        getStream: async () => new MediaStream(context.stream.getAudioTracks()),
        pauseStream: async () => {},
        resumeStream: async () => new MediaStream(context.stream.getAudioTracks()),
        positiveSpeechThreshold: this.threshold,
        negativeSpeechThreshold: Math.max(0.05, this.threshold - 0.15),
        minSpeechMs: this.minimoMs,
        redemptionMs: 400,
        preSpeechPadMs: 0,
        submitUserSpeechOnPause: false,
        onSpeechStart: () => {
          if (this.stopped || generation !== this.generation) return
          this.oidas += 1
          this.speaking = true
          context.onSpeechStart?.()
          this.startSegment()
        },
        onSpeechEnd: () => {
          if (generation !== this.generation) return
          this.speaking = false
          void this.finishSegment()
        },
        onVADMisfire: () => {
          if (generation !== this.generation) return
          this.speaking = false
          void this.finishSegment(true)
        }
      })
      if (this.stopped || generation !== this.generation) {
        await vad.destroy()
        return
      }
      this.vad = vad
      etapa = 'abriendo la pista de audio'
      await vad.start()
    } catch (fallo) {
      const causa = fallo instanceof Error ? fallo.message : String(fallo)
      throw new Error(`${etapa}: ${causa} [${this.entorno(context)}]`)
    }
  }

  private startSegment(): void {
    if (this.stopped || this.recorder || !this.context) return
    this.startedAt = Date.now()
    this.sender = this.context.captureSender()
    this.chunks = []
    this.discard = false
    this.recorder = new MediaRecorder(new MediaStream(this.context.stream.getAudioTracks()), {
      mimeType: 'audio/webm;codecs=opus',
      audioBitsPerSecond: 32000
    })
    this.recorder.ondataavailable = (event) => {
      if (event.data.size) this.chunks.push(event.data)
    }
    this.recorder.onerror = () => {
      void this.finishSegment(true)
    }
    this.recorder.start()
    this.timer = setTimeout(() => {
      // Reset Silero's own PCM buffer too, not only MediaRecorder's buffer.
      this.speaking = false
      void (async () => {
        await this.finishSegment()
        await this.vad?.pause()
        if (!this.stopped) await this.vad?.start()
      })().catch(() => {
        this.detener()
      })
    }, 10000)
  }

  private finishSegment(discard = false): Promise<void> {
    this.discard ||= discard
    if (this.stopping) return this.stopping
    const recorder = this.recorder
    if (!recorder) return Promise.resolve()
    clearTimeout(this.timer)
    const duration = Date.now() - this.startedAt
    this.stopping = new Promise<void>((resolve) => {
      recorder.onstop = () => {
        const audio = new Blob(this.chunks, { type: 'audio/webm' })
        if (this.discard || duration < this.minimoMs || !audio.size) {
          // Se descarta a proposito: demasiado corto, sin audio, o el propio
          // VAD lo dio por falsa alarma. Se cuenta para poder leer despues
          // «oyo cinco veces y descarto cinco» en vez de un cero sin explicar.
          if (this.oidas > 0) this.descartadas += 1
        }
        if (!this.discard && duration >= this.minimoMs && audio.size) {
          this.enviadas += 1
          this.sender?.({
            evento: 'speech_detected',
            inicioMs: this.startedAt,
            duracionMs: duration,
            audio,
            metadata: {
              source: 'silero_vad_v5',
              speech_ratio_threshold: this.threshold,
              capture_sample_rate: this.sampleRate,
              vad_sample_rate: 16000,
              max_segment_ms: 10000,
              min_duration_ms: this.minimoMs
            }
          })
        }
        this.chunks = []
        this.recorder = undefined
        this.stopping = undefined
        resolve()
        if (this.speaking && !this.stopped) this.startSegment()
      }
      if (recorder.state !== 'inactive') recorder.stop()
    })
    return this.stopping
  }

  observar(_observation: Observacion): Veredicto {
    return { activa: this.speaking, metadata: { source: 'silero_vad_v5' } }
  }

  detener(): void {
    ++this.generation
    this.stopped = true
    this.speaking = false
    void this.finishSegment(true)
    void this.vad?.destroy()
  }
}
