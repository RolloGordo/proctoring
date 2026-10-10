import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'

afterEach(() => vi.unstubAllGlobals())

describe('contrato HU-006 contra API', () => {
  it('pide referencia, registra ruta y encola la comprobación con rutas distintas', async () => {
    const espia = vi.fn(async (url: string) => {
      const cuerpo = url.endsWith('/upload-url')
        ? { path: 'ruta-ref.jpg', url: 'https://storage.example.com/signed', token: null, expires_in_seconds: 7200 }
        : url.endsWith('/reference-face')
          ? { storage_path: 'ruta-ref.jpg' }
          : { id: 'p1', can_take_exam: false, verification_status: 'pending' }
      return new Response(JSON.stringify(cuerpo), {
        status: url.endsWith('/identity/check') ? 202 : 201,
        headers: { 'Content-Type': 'application/json' }
      })
    })
    vi.stubGlobal('fetch', espia)

    await api.identityPhotoUpload('sesion-uno', 'alumno-uno', 'reference_face', 'jwt')
    await api.registerReferenceFace('ruta-ref.jpg', 'jwt')
    await api.requestIdentityCheck('sesion-uno', 'captura-actual.jpg', 'jwt')

    const llamadas = espia.mock.calls as unknown as Array<[string, RequestInit]>
    expect(llamadas).toHaveLength(3)
    expect(llamadas[0][0]).toContain('/api/v1/evidence/upload-url')
    expect(JSON.parse(String(llamadas[0][1].body))).toEqual({
      session_id: 'sesion-uno', student_id: 'alumno-uno',
      kind: 'reference_face', extension: 'jpg'
    })
    expect(JSON.parse(String(llamadas[1][1].body))).toEqual({ storage_path: 'ruta-ref.jpg' })
    expect(llamadas[2][0]).toContain('/api/v1/exam/sesion-uno/identity/check')
    expect(JSON.parse(String(llamadas[2][1].body))).toEqual({ capture_path: 'captura-actual.jpg' })
    for (const [, init] of llamadas) {
      expect(init.method).toBe('POST')
      expect(new Headers(init.headers).get('Authorization')).toBe('Bearer jwt')
    }
  })
})
