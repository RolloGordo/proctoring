import { describe, expect, it } from 'vitest'
import { EstadoConexion, FALLOS_PARA_CAER } from './conexion'

describe('EstadoConexion', () => {
  it('un sondeo lento suelto no bloquea el examen', () => {
    const estado = new EstadoConexion()
    expect(estado.sondeo(false)).toBeNull()
    expect(estado.conectado).toBe(true)
    expect(estado.sondeo(true)).toBeNull()
    expect(estado.sondeo(false)).toBeNull()
    expect(estado.conectado).toBe(true)
  })

  it('cae tras los fallos seguidos necesarios y lo dice una sola vez', () => {
    const estado = new EstadoConexion()
    const vistos = Array.from({ length: FALLOS_PARA_CAER + 2 }, () => estado.sondeo(false))
    expect(vistos.filter((x) => x === 'cayo')).toHaveLength(1)
    expect(estado.conectado).toBe(false)
  })

  it('sin red cae de inmediato, y vuelve con un sondeo bueno', () => {
    const estado = new EstadoConexion()
    expect(estado.sinRed()).toBe(true)
    expect(estado.sinRed()).toBe(false)
    expect(estado.conectado).toBe(false)
    expect(estado.sondeo(true)).toBe('volvio')
    expect(estado.conectado).toBe(true)
  })
})
