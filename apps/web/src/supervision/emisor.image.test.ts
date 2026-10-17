import { afterEach, expect, it, vi } from 'vitest'
import { EmisorDeSenales } from './emisor'
import { api } from '../lib/api'
import { uploadImage } from './imageUpload'

vi.mock('./imageUpload', () => ({ uploadImage: vi.fn().mockResolvedValue('s/u/evidence.jpg') }))
afterEach(() => vi.restoreAllMocks())

it('adjunta una captura al evento y conserva pregunta inicial', async () => {
  const register = vi.spyOn(api, 'registerEvent').mockResolvedValue({ id: 'e' } as never)
  const emisor = new EmisorDeSenales({ sessionId: 's', studentId: 'u', questionId: 'q1' })
  emisor.emitir({ evento: 'extra_person', inicioMs: 0, duracionMs: 3000, metadata: {}, image: Promise.resolve(new Blob(['x'], { type: 'image/jpeg' })) })
  emisor.actualizarContexto({ questionId: 'q2' })
  await vi.waitFor(() => expect(register).toHaveBeenCalledTimes(1))
  expect(uploadImage).toHaveBeenCalledTimes(1)
  expect(register.mock.calls[0][0]).toMatchObject({ question_id: 'q1', evidence_path: 's/u/evidence.jpg' })
  await emisor.cerrar()
})

it('records the detected event even if its JPEG upload fails', async () => {
  const { uploadImage } = await import('./imageUpload')
  vi.mocked(uploadImage).mockRejectedValueOnce(new Error('storage unavailable'))
  const err = vi.spyOn(console, 'error').mockImplementation(() => undefined)
  const register = vi.spyOn(api, 'registerEvent').mockResolvedValue({ id: 'e' } as never)
  const emisor = new EmisorDeSenales({ sessionId: 's', studentId: 'u', questionId: 'q1' })
  emisor.emitir({ evento: 'gaze_away', inicioMs: Date.now(), duracionMs: 4000, metadata: {}, image: Promise.resolve(new Blob(['x'], {type:'image/jpeg'})) })
  await vi.waitFor(() => expect(register).toHaveBeenCalledTimes(1))
  expect(register.mock.calls[0][0]).toMatchObject({
    event_type: 'gaze_away', metadata: { capture_error: 'upload_failed' }, evidence_path: undefined
  })
  await emisor.cerrar()
  err.mockRestore()
})

it('a capture that never resolves does not kill the queue', async () => {
  // **El fallo que dejo el proyecto entero sin una sola captura.**
  // `capturarFotograma` envuelve `canvas.toBlob`, que si no llama de vuelta no
  // resuelve ni rechaza nunca. El `while` de vaciar() se quedaba ahi con
  // `enviando` en true, y a partir de ese momento ninguna senal volvia a
  // salir. Sin catch, asi que sin una linea en consola.
  vi.useFakeTimers()
  const err = vi.spyOn(console, 'error').mockImplementation(() => undefined)
  const register = vi.spyOn(api, 'registerEvent').mockResolvedValue({ id: 'e' } as never)
  const emisor = new EmisorDeSenales({ sessionId: 's', studentId: 'u', questionId: 'q1' })

  // La primera trae una captura que no llega nunca.
  emisor.emitir({
    evento: 'face_absent',
    inicioMs: 1,
    duracionMs: 5000,
    metadata: {},
    image: new Promise<Blob | null>(() => {})
  })
  // La segunda va detras, sin imagen.
  emisor.emitir({ evento: 'face_absent', inicioMs: 9000, duracionMs: 5000, metadata: {} })

  await vi.advanceTimersByTimeAsync(21_000)
  await emisor.cerrar()

  // Las dos llegan: la primera sin foto pero con el motivo apuntado.
  expect(register).toHaveBeenCalledTimes(2)
  expect(register.mock.calls[0][0]).toMatchObject({
    event_type: 'face_absent',
    metadata: { capture_error: 'capture_timeout' }
  })
  expect(register.mock.calls[1][0]).toMatchObject({ event_type: 'face_absent' })
  err.mockRestore()
  vi.useRealTimers()
})

it('an upload that hangs still lets the event through', async () => {
  vi.useFakeTimers()
  const { uploadImage } = await import('./imageUpload')
  vi.mocked(uploadImage).mockReturnValueOnce(new Promise<string>(() => {}))
  const err = vi.spyOn(console, 'error').mockImplementation(() => undefined)
  const register = vi.spyOn(api, 'registerEvent').mockResolvedValue({ id: 'e' } as never)
  const emisor = new EmisorDeSenales({ sessionId: 's', studentId: 'u', questionId: 'q1' })

  emisor.emitir({
    evento: 'gaze_away',
    inicioMs: 1,
    duracionMs: 4000,
    metadata: {},
    image: Promise.resolve(new Blob(['x'], { type: 'image/jpeg' }))
  })

  await vi.advanceTimersByTimeAsync(21_000)
  await emisor.cerrar()

  expect(register).toHaveBeenCalledTimes(1)
  expect(register.mock.calls[0][0]).toMatchObject({
    event_type: 'gaze_away',
    metadata: { capture_error: 'upload_failed' },
    evidence_path: undefined
  })
  err.mockRestore()
  vi.useRealTimers()
})
