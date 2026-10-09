import { afterEach, expect, it, vi } from 'vitest'
import { EmisorDeSenales } from './emisor'
import { api } from '../lib/api'
import { uploadAudio } from './audioUpload'

vi.mock('./audioUpload', () => ({ uploadAudio: vi.fn().mockResolvedValue('s/u/audio.webm') }))
afterEach(() => vi.restoreAllMocks())

it('keeps original question while upload is in progress and emits evidence_path', async () => {
  const register = vi.spyOn(api, 'registerEvent').mockResolvedValue({ id: 'e', severity: 'low' })
  const emitter = new EmisorDeSenales({ sessionId: 's', studentId: 'u', questionId: 'q1' })
  const send = emitter.captureSender()
  emitter.actualizarContexto({ questionId: 'q2' })
  send({
    evento: 'speech_detected',
    inicioMs: 0,
    duracionMs: 2000,
    metadata: {},
    audio: new Blob(['x'])
  })
  await vi.waitFor(() => expect(register).toHaveBeenCalledTimes(1))
  expect(uploadAudio).toHaveBeenCalled()
  expect(register.mock.calls[0][0]).toMatchObject({
    question_id: 'q1',
    evidence_path: 's/u/audio.webm'
  })
  await emitter.cerrar()
})
it('never emits a speech event without an audio file', async () => {
  const register = vi.spyOn(api, 'registerEvent').mockResolvedValue({ id: 'e', severity: 'low' })
  const emitter = new EmisorDeSenales({ sessionId: 's', studentId: 'u', questionId: 'q' })
  emitter.emitir({ evento: 'speech_detected', inicioMs: 0, duracionMs: 2000, metadata: {} })
  await emitter.cerrar()
  expect(register).not.toHaveBeenCalled()
})
