import { describe, expect, it, vi } from 'vitest'
import { CapturasPorCondicion } from './capturasVision'

const activo = { activa: true }
const inactivo = { activa: false }

describe('captura puntual por episodio (TA-018)', () => {
  it('no captura antes del mínimo, ni una vez por fotograma', async () => {
    const captura = vi.fn().mockResolvedValue(new Blob(['jpeg'], { type: 'image/jpeg' }))
    const s = new CapturasPorCondicion(3000)
    expect(s.actualizar(activo, 0, captura)).toBe(false)
    expect(s.actualizar(activo, 2900, captura)).toBe(false)
    expect(s.actualizar(activo, 3000, captura)).toBe(true)
    expect(s.actualizar(activo, 4000, captura)).toBe(false)
    expect(await s.consumir()).toBeInstanceOf(Blob)
    expect(captura).toHaveBeenCalledTimes(1)
  })
  it('captura una vez por evento nuevo, pero no durante un parpadeo', async () => {
    const captura = vi.fn().mockResolvedValue(new Blob(['foto']))
    const s = new CapturasPorCondicion(1000)
    s.actualizar(activo, 0, captura)
    expect(s.actualizar(activo, 1000, captura)).toBe(true)
    s.actualizar(inactivo, 1100, captura)
    expect(s.actualizar(activo, 1250, captura)).toBe(false)
    await s.consumir()
    s.actualizar(activo, 2000, captura)
    expect(s.actualizar(activo, 3000, captura)).toBe(true)
    await s.consumir()
    expect(captura).toHaveBeenCalledTimes(2)
  })
  it('no inventa capturas cuando la condición fue breve', () => {
    const s = new CapturasPorCondicion(5000)
    const captura = vi.fn()
    s.actualizar(activo, 0, captura)
    s.actualizar(inactivo, 600, captura)
    s.reiniciar()
    expect(s.consumir()).toBeUndefined()
    expect(captura).not.toHaveBeenCalled()
  })
})
