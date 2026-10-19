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

it('does not report speech when its fragment never reached Storage', async () => {
  // Para la voz el fragmento **es** la evidencia: las dos condiciones que
  // exige el proyecto las calcula el worker a partir del audio. Un
  // `speech_detected` sin fragmento seria una «voz detectada» que nadie puede
  // comprobar nunca, y leer en voz alta no es una infraccion.
  vi.mocked(uploadAudio).mockRejectedValueOnce(new Error('storage caido'))
  const err = vi.spyOn(console, 'error').mockImplementation(() => undefined)
  const register = vi.spyOn(api, 'registerEvent').mockResolvedValue({ id: 'e', severity: 'low' })
  const perdidos: string[] = []
  const emitter = new EmisorDeSenales({ sessionId: 's', studentId: 'u', questionId: 'q' }, (m) =>
    perdidos.push(m)
  )
  emitter.emitir({
    evento: 'speech_detected',
    inicioMs: 0,
    duracionMs: 2000,
    metadata: {},
    audio: new Blob(['x'])
  })
  await emitter.cerrar()

  expect(register).not.toHaveBeenCalled()
  // Pero no desaparece sin dejar rastro: queda como fallo de disponibilidad.
  expect(perdidos).toEqual(['storage caido'])
  err.mockRestore()
})

it('a lost fragment does not jam the queue behind it', async () => {
  vi.mocked(uploadAudio)
    .mockRejectedValueOnce(new Error('storage caido'))
    .mockResolvedValueOnce('s/u/segundo.webm')
  const err = vi.spyOn(console, 'error').mockImplementation(() => undefined)
  const register = vi.spyOn(api, 'registerEvent').mockResolvedValue({ id: 'e', severity: 'low' })
  const emitter = new EmisorDeSenales({ sessionId: 's', studentId: 'u', questionId: 'q' })
  emitter.emitir({ evento: 'speech_detected', inicioMs: 0, duracionMs: 2000, metadata: {}, audio: new Blob(['a']) })
  emitter.emitir({ evento: 'speech_detected', inicioMs: 3000, duracionMs: 2000, metadata: {}, audio: new Blob(['b']) })
  await emitter.cerrar()

  expect(register).toHaveBeenCalledTimes(1)
  expect(register.mock.calls[0][0]).toMatchObject({ evidence_path: 's/u/segundo.webm' })
  err.mockRestore()
})

it('a speech fragment dropped before the queue says why', async () => {
  // **El sexto silencio de la misma familia.** Sin pregunta en curso, un
  // fragmento que el VAD si oyo desaparecia antes de entrar en la cola, y en
  // el expediente se leia igual que si nadie hubiera hablado.
  const err = vi.spyOn(console, 'error').mockImplementation(() => undefined)
  const register = vi.spyOn(api, 'registerEvent').mockResolvedValue({ id: 'e', severity: 'low' })
  const descartes: string[] = []
  const emitter = new EmisorDeSenales(
    { sessionId: 's', studentId: 'u', questionId: null },
    undefined,
    undefined,
    undefined,
    undefined,
    (motivo) => descartes.push(motivo)
  )

  emitter.emitir({
    evento: 'speech_detected',
    inicioMs: 0,
    duracionMs: 2000,
    metadata: {},
    audio: new Blob(['x'])
  })
  await emitter.cerrar()

  expect(register).not.toHaveBeenCalled()
  expect(descartes).toEqual(['sin pregunta en curso'])
  err.mockRestore()
})

it('distingue no tener audio de no tener pregunta', async () => {
  const err = vi.spyOn(console, 'error').mockImplementation(() => undefined)
  const descartes: string[] = []
  const emitter = new EmisorDeSenales(
    { sessionId: 's', studentId: 'u', questionId: 'q1' },
    undefined,
    undefined,
    undefined,
    undefined,
    (motivo) => descartes.push(motivo)
  )

  emitter.emitir({ evento: 'speech_detected', inicioMs: 0, duracionMs: 2000, metadata: {} })
  await emitter.cerrar()

  expect(descartes).toEqual(['sin audio'])
  err.mockRestore()
})
