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
