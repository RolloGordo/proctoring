import { beforeEach, describe, expect, it, vi } from 'vitest'
import { guardarEncuadre, leerEncuadre } from './encuadreSala'

// Las pruebas corren en Node: un sessionStorage en memoria basta.
const memoria = new Map<string, string>()
vi.stubGlobal('sessionStorage', {
  getItem: (k: string) => memoria.get(k) ?? null,
  setItem: (k: string, v: string) => void memoria.set(k, v),
  clear: () => memoria.clear()
})

describe('encuadre recordado en la sala', () => {
  beforeEach(() => sessionStorage.clear())

  it('se recuerda por examen y estudiante', () => {
    guardarEncuadre('s1', 'e1', 'passed')
    expect(leerEncuadre('s1', 'e1')).toBe('passed')
    expect(leerEncuadre('s2', 'e1')).toBeNull()
    expect(leerEncuadre('s1', 'e2')).toBeNull()
  })
  it('caduca', () => {
    guardarEncuadre('s1', 'e1', 'passed')
    vi.spyOn(Date, 'now').mockReturnValue(Date.now() + 7 * 60 * 60 * 1000)
    expect(leerEncuadre('s1', 'e1')).toBeNull()
    vi.restoreAllMocks()
  })
  it('un valor manipulado no vale', () => {
    sessionStorage.setItem('proctoring:framing-check:v1:s1:e1', '{"estado":"aprobado"}')
    expect(leerEncuadre('s1', 'e1')).toBeNull()
  })
})
