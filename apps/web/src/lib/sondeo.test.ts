import { afterEach, describe, expect, it, vi } from 'vitest'
import { conMargen, sondear } from './sondeo'

afterEach(() => vi.useRealTimers())

describe('conMargen', () => {
  it('reparte en ±20 % alrededor del intervalo', () => {
    expect(conMargen(10_000, 0.2, () => 0)).toBe(8_000)
    expect(conMargen(10_000, 0.2, () => 0.5)).toBe(10_000)
    expect(conMargen(10_000, 0.2, () => 0.999999)).toBe(12_000)
  })

  it('dos estudiantes que entraron a la vez dejan de preguntar a la vez', () => {
    const esperas = new Set(Array.from({ length: 50 }, () => conMargen(10_000)))
    expect(esperas.size).toBeGreaterThan(30)
  })
})

describe('sondear', () => {
  it('pregunta enseguida y luego cada vuelta, hasta que se para', () => {
    vi.useFakeTimers()
    const consultar = vi.fn()

    const parar = sondear(consultar, 10_000)
    expect(consultar).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(12_001)
    expect(consultar).toHaveBeenCalledTimes(2)
    vi.advanceTimersByTime(12_001)
    expect(consultar).toHaveBeenCalledTimes(3)

    parar()
    vi.advanceTimersByTime(60_000)
    expect(consultar).toHaveBeenCalledTimes(3)
  })
})
