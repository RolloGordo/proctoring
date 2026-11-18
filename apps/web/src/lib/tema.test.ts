import { describe, expect, it } from 'vitest'
import { aplicarTema, CLAVE_TEMA, elegirTema, temaDelSistema, temaElegido, temaVigente } from './tema'

function almacen(inicial: Record<string, string> = {}) {
  const datos = new Map(Object.entries(inicial))
  return {
    getItem: (k: string) => datos.get(k) ?? null,
    setItem: (k: string, v: string) => void datos.set(k, v),
    datos
  }
}

const sistema = (claro: boolean) => ((_q: string) => ({ matches: claro }) as MediaQueryList)

describe('tema', () => {
  it('sin elección sigue al sistema', () => {
    expect(temaVigente(almacen(), sistema(true))).toBe('claro')
    expect(temaVigente(almacen(), sistema(false))).toBe('oscuro')
  })

  it('la elección guardada manda sobre el sistema', () => {
    expect(temaVigente(almacen({ [CLAVE_TEMA]: 'oscuro' }), sistema(true))).toBe('oscuro')
    expect(temaVigente(almacen({ [CLAVE_TEMA]: 'claro' }), sistema(false))).toBe('claro')
  })

  it('ignora valores que no son un tema', () => {
    expect(temaElegido(almacen({ [CLAVE_TEMA]: '<script>' }))).toBeNull()
  })

  it('sin matchMedia se queda en oscuro, el de siempre', () => {
    expect(temaDelSistema(undefined)).toBe('oscuro')
  })

  it('si el almacenamiento falla no rompe nada', () => {
    const roto = {
      getItem: () => {
        throw new Error('bloqueado')
      },
      setItem: () => {
        throw new Error('bloqueado')
      }
    }
    expect(temaElegido(roto)).toBeNull()
    expect(() => elegirTema('claro', roto)).not.toThrow()
  })

  it('elegir guarda la elección', () => {
    const a = almacen()
    elegirTema('claro', a)
    expect(a.datos.get(CLAVE_TEMA)).toBe('claro')
  })

  it('aplica el tema en el atributo de la raíz', () => {
    const raiz = { dataset: {} as Record<string, string> } as unknown as HTMLElement
    aplicarTema('claro', raiz)
    expect(raiz.dataset['tema']).toBe('claro')
  })
})
