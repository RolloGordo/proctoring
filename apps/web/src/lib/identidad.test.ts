import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import { subirFotoDeIdentidad, urlDeSubidaFirmada } from './identidad'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('subida de fotografía HU-006', () => {
  const foto = new Blob(['jpeg-demo'], { type: 'image/jpeg' })

  it('hace PUT a Storage y solo después devuelve la ruta', async () => {
    const firma = vi.spyOn(api, 'identityPhotoUpload').mockResolvedValue({
      path: 'sesion/estudiante/foto.jpg',
      url: 'https://storage.example.com/upload?token=firmado',
      token: 'firmado',
      expires_in_seconds: 7200
    })
    const solicitud = vi.fn(async () => new Response(null, { status: 200 }))
    vi.stubGlobal('fetch', solicitud)

    const ruta = await subirFotoDeIdentidad({
      sessionId: 'sesion', studentId: 'estudiante', kind: 'reference_face', foto,
      token: 'jwt-de-estudiante'
    })

    expect(ruta).toBe('sesion/estudiante/foto.jpg')
    expect(firma).toHaveBeenCalledWith('sesion', 'estudiante', 'reference_face', 'jwt-de-estudiante')
    expect(solicitud).toHaveBeenCalledTimes(1)
    const [url, init] = solicitud.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toContain('token=firmado')
    expect(init.method).toBe('PUT')
    expect(new Headers(init.headers).get('Content-Type')).toBe('image/jpeg')
    expect(new Headers(init.headers).has('Authorization')).toBe(false)
  })

  it('no registra ruta si Storage devuelve 400', async () => {
    vi.spyOn(api, 'identityPhotoUpload').mockResolvedValue({
      path: 'foto-inexistente.jpg', url: 'https://storage.example.com/upload',
      token: null, expires_in_seconds: 7200
    })
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 400 })))
    await expect(subirFotoDeIdentidad({
      sessionId: 'sesion', studentId: 'estudiante', kind: 'image', foto
    })).rejects.toThrow('HTTP 400')
  })

  it('rechaza archivos vacíos sin pedir una URL', async () => {
    const firma = vi.spyOn(api, 'identityPhotoUpload')
    await expect(subirFotoDeIdentidad({
      sessionId: 'sesion', studentId: 'estudiante', kind: 'image',
      foto: new Blob([], { type: 'image/jpeg' })
    })).rejects.toThrow('JPEG válida')
    expect(firma).not.toHaveBeenCalled()
  })

  it('agrega token separado sin repetir un token ya presente', () => {
    expect(urlDeSubidaFirmada('https://storage.example.com/x', 'secreto'))
      .toBe('https://storage.example.com/x?token=secreto')
    expect(urlDeSubidaFirmada('https://storage.example.com/x?token=existente', 'secreto'))
      .toBe('https://storage.example.com/x?token=existente')
  })
})
