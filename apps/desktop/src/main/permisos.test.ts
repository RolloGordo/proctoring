import { describe, expect, it, vi } from 'vitest'
import { applyPermissionPolicy } from './permisos'

const EXAMEN = 'http://localhost:5173'

interface SesionFalsa {
  /** Lo que responderia al pedir un permiso desde `url`. */
  pedir: (permiso: string, url: string) => boolean
  comprobar: (permiso: string, origen: string) => boolean
  dispositivos: () => boolean
}

/** Una sesion de Electron de mentira que guarda los handlers que se le ponen. */
function sesionFalsa(): SesionFalsa {
  const handlers: Record<string, (...args: never[]) => unknown> = {}
  const session = {
    setPermissionRequestHandler: vi.fn((h) => (handlers.request = h)),
    setPermissionCheckHandler: vi.fn((h) => (handlers.check = h)),
    setDevicePermissionHandler: vi.fn((h) => (handlers.device = h))
  }
  applyPermissionPolicy(session as never, EXAMEN)

  return {
    pedir(permiso: string, url: string): boolean {
      let respuesta = false
      const request = handlers.request as unknown as (
        c: { getURL: () => string },
        p: string,
        cb: (ok: boolean) => void
      ) => void
      request({ getURL: () => url }, permiso, (ok) => (respuesta = ok))
      return respuesta
    },
    comprobar(permiso: string, origen: string): boolean {
      const check = handlers.check as unknown as (c: unknown, p: string, o: string) => boolean
      return check(null, permiso, origen)
    },
    dispositivos(): boolean {
      return (handlers.device as unknown as () => boolean)()
    }
  }
}

describe('permisos de la ventana del examen', () => {
  it('concede camara y microfono al examen', () => {
    const s = sesionFalsa()

    expect(s.pedir('media', `${EXAMEN}/examen/abc/rendir`)).toBe(true)
    expect(s.pedir('videoCapture', `${EXAMEN}/examen/abc/rendir`)).toBe(true)
    expect(s.pedir('audioCapture', `${EXAMEN}/examen/abc/rendir`)).toBe(true)
  })

  it('NO se los concede a otro origen', () => {
    // Sin esto, cualquier sitio al que llegara la ventana podria encender la
    // camara del estudiante.
    const s = sesionFalsa()

    expect(s.pedir('media', 'https://otro.example/x')).toBe(false)
    expect(s.pedir('media', 'file:///C:/algo.html')).toBe(false)
    expect(s.pedir('media', '')).toBe(false)
  })

  it('un origen que solo se le parece tampoco', () => {
    const s = sesionFalsa()

    expect(s.pedir('media', 'http://localhost:5173.evil.example/x')).toBe(false)
    expect(s.pedir('media', 'https://localhost:5173/x')).toBe(false)
  })

  it('deniega lo que un examen no necesita', () => {
    const s = sesionFalsa()

    for (const permiso of ['geolocation', 'notifications', 'clipboard-read', 'midi']) {
      expect(s.pedir(permiso, `${EXAMEN}/examen/abc/rendir`)).toBe(false)
    }
  })

  it('la comprobacion sincrona sigue la misma regla', () => {
    const s = sesionFalsa()

    expect(s.comprobar('media', EXAMEN)).toBe(true)
    expect(s.comprobar('media', 'https://otro.example')).toBe(false)
    expect(s.comprobar('geolocation', EXAMEN)).toBe(false)
  })

  it('no deja enumerar los dispositivos del estudiante', () => {
    expect(sesionFalsa().dispositivos()).toBe(false)
  })
})
