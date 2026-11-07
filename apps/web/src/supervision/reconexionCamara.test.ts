import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { escucharReconexionCamara, type DispositivosMedia } from './reconexionCamara'

class DispositivosFalsos implements DispositivosMedia {
  escuchas = new Set<() => void>()
  lista: Array<{ kind: string }> = []
  addEventListener(_: 'devicechange', escucha: () => void): void {
    this.escuchas.add(escucha)
  }
  removeEventListener(_: 'devicechange', escucha: () => void): void {
    this.escuchas.delete(escucha)
  }
  enumerateDevices(): Promise<Array<{ kind: string }>> {
    return Promise.resolve(this.lista)
  }
  cambiar(): void {
    for (const escucha of this.escuchas) escucha()
  }
}

describe('escucharReconexionCamara', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('reintenta cuando vuelve a haber una cámara', async () => {
    const dispositivos = new DispositivosFalsos()
    const alReconectar = vi.fn()
    escucharReconexionCamara(dispositivos, alReconectar, { esperaMs: 100 })
    dispositivos.lista = [{ kind: 'videoinput' }]
    dispositivos.cambiar()
    await vi.advanceTimersByTimeAsync(100)
    expect(alReconectar).toHaveBeenCalledTimes(1)
  })

  it('no reintenta si lo que se conectó no es una cámara', async () => {
    const dispositivos = new DispositivosFalsos()
    const alReconectar = vi.fn()
    escucharReconexionCamara(dispositivos, alReconectar, { esperaMs: 100 })
    dispositivos.lista = [{ kind: 'audioinput' }]
    dispositivos.cambiar()
    await vi.advanceTimersByTimeAsync(100)
    expect(alReconectar).not.toHaveBeenCalled()
  })

  it('agrupa los avisos seguidos de un mismo enchufe', async () => {
    const dispositivos = new DispositivosFalsos()
    const alReconectar = vi.fn()
    escucharReconexionCamara(dispositivos, alReconectar, { esperaMs: 100 })
    dispositivos.lista = [{ kind: 'videoinput' }]
    dispositivos.cambiar()
    await vi.advanceTimersByTimeAsync(50)
    dispositivos.cambiar()
    await vi.advanceTimersByTimeAsync(50)
    dispositivos.cambiar()
    await vi.advanceTimersByTimeAsync(100)
    expect(alReconectar).toHaveBeenCalledTimes(1)
  })

  it('respeta el tope de reintentos', async () => {
    const dispositivos = new DispositivosFalsos()
    const alReconectar = vi.fn()
    escucharReconexionCamara(dispositivos, alReconectar, { esperaMs: 10, maximo: 2 })
    dispositivos.lista = [{ kind: 'videoinput' }]
    for (let i = 0; i < 4; i += 1) {
      dispositivos.cambiar()
      await vi.advanceTimersByTimeAsync(10)
    }
    expect(alReconectar).toHaveBeenCalledTimes(2)
  })

  it('deja de escuchar al limpiar, aunque hubiera un reintento pendiente', async () => {
    const dispositivos = new DispositivosFalsos()
    const alReconectar = vi.fn()
    const dejar = escucharReconexionCamara(dispositivos, alReconectar, { esperaMs: 100 })
    dispositivos.lista = [{ kind: 'videoinput' }]
    dispositivos.cambiar()
    dejar()
    await vi.advanceTimersByTimeAsync(200)
    expect(alReconectar).not.toHaveBeenCalled()
    expect(dispositivos.escuchas.size).toBe(0)
  })

  it('sin mediaDevices no hace nada ni lanza', () => {
    expect(() => escucharReconexionCamara(undefined, vi.fn())()).not.toThrow()
  })
})
