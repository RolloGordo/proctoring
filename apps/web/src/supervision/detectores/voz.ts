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

  constructor(settings: AjustesVoz = {}) {
    this.minimoMs = settings.min_duration_ms ?? 1500
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
        this.speaking = true
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
    await vad.start()
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
        if (!this.discard && duration >= this.minimoMs && audio.size) {
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
