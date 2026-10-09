import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { DetectorHabla } from './voz'

const vad = vi.hoisted(() => ({
  options: {} as Record<string, () => void>,
  start: vi.fn(),
  pause: vi.fn(),
  destroy: vi.fn()
}))
vi.mock('@ricky0123/vad-web', () => ({
  MicVAD: {
    new: async (options: typeof vad.options) => {
      vad.options = options
      return vad
    }
  }
}))

class Recorder {
  static instances: Recorder[] = []
  static isTypeSupported() {
    return true
  }
  ondataavailable?: (event: { data: Blob }) => void
  onstop?: () => void
  onerror?: () => void
  constructor() {
    Recorder.instances.push(this)
  }
  start() {}
  stop() {
    queueMicrotask(() => {
      this.ondataavailable?.({ data: new Blob(['webm-test']) })
      this.onstop?.()
    })
  }
}
beforeEach(() => {
  Recorder.instances = []
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] })
  vi.stubGlobal('MediaRecorder', Recorder)
  vi.stubGlobal(
    'MediaStream',
    class {
      constructor(public tracks: unknown[]) {}
    }
  )
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

async function setup() {
  const send = vi.fn()
  const detector = new DetectorHabla({ min_duration_ms: 100 })
  const stream = {
    getAudioTracks: () => [{ getSettings: () => ({ sampleRate: 48000 }) }]
  } as unknown as MediaStream
  await detector.preparar({ stream, captureSender: () => send })
  return { detector, send }
}
it('records only after voice starts and sends one fragment when it ends', async () => {
  const { detector, send } = await setup()
  expect(Recorder.instances).toHaveLength(0)
  vad.options.onSpeechStart()
  await vi.advanceTimersByTimeAsync(500)
  vad.options.onSpeechEnd()
  await Promise.resolve()
  expect(send).toHaveBeenCalledTimes(1)
  expect(send.mock.calls[0][0].audio.size).toBeGreaterThan(0)
  detector.detener()
})
it('discards misfires and open audio when supervision stops', async () => {
  const { detector, send } = await setup()
  vad.options.onSpeechStart()
  await vi.advanceTimersByTimeAsync(500)
  vad.options.onVADMisfire()
  await Promise.resolve()
  vad.options.onSpeechStart()
  detector.detener()
  await Promise.resolve()
  expect(send).not.toHaveBeenCalled()
})
it('caps a long utterance and resets the VAD buffer', async () => {
  const { detector, send } = await setup()
  vad.options.onSpeechStart()
  await vi.advanceTimersByTimeAsync(10000)
  expect(send).toHaveBeenCalledTimes(1)
  expect(vad.pause).toHaveBeenCalled()
  detector.detener()
})
