import { afterEach, expect, it, vi } from 'vitest'
import { uploadImage } from './imageUpload'
import { api } from '../lib/api'

const context = { sessionId: 's', studentId: 'u', questionId: 'q1', token: 'jwt' }
const image = new Blob(['jpg-bytes'], { type: 'image/jpeg' })

afterEach(() => vi.restoreAllMocks())

it('solicita URL firmada y sube captura JPEG mediante PUT', async () => {
  const sign = vi.spyOn(api, 'identityPhotoUpload').mockResolvedValue({
    path: 's/u/photo.jpg', url: 'https://example.org/storage/photo', token: 'signed', expires_in_seconds: 120
  })
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true, status: 200 } as Response)
  const result = await uploadImage(image, context)
  expect(result).toBe('s/u/photo.jpg')
  expect(sign).toHaveBeenCalledWith('s', 'u', 'image', 'jwt')
  expect(fetchMock).toHaveBeenCalledWith(expect.any(URL), expect.objectContaining({
    method: 'PUT', body: image
  }))
})

it('no devuelve una ruta si Storage falla', async () => {
  vi.spyOn(api, 'identityPhotoUpload').mockResolvedValue({
    path: 's/u/photo.jpg', url: 'https://example.org/storage/photo', token: null, expires_in_seconds: 120
  })
  vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: false, status: 400 } as Response)
  await expect(uploadImage(image, context)).rejects.toThrow('Storage rechazó')
})

it('bloquea rutas de otros estudiantes y archivos incorrectos', async () => {
  await expect(uploadImage(new Blob(['x'], { type: 'text/plain' }), context)).rejects.toThrow()
  vi.spyOn(api, 'identityPhotoUpload').mockResolvedValue({
    path: 's/otro/photo.jpg', url: 'https://example.org/storage/photo', token: null, expires_in_seconds: 120
  })
  await expect(uploadImage(image, context)).rejects.toThrow('fuera del estudiante')
})
