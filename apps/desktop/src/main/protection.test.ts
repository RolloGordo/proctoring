import type { BrowserWindow } from 'electron'
import { describe, expect, it, vi } from 'vitest'
import { applyWindowProtection } from './protection'

type Handler = (...args: unknown[]) => void

function ventanaFalsa(): {
  ventana: BrowserWindow
  handler: (name: string) => Handler | undefined
} {
  const handlers = new Map<string, Handler>()
  const ventana = {
    setContentProtection: vi.fn(),
    webContents: {
      on: vi.fn((name: string, callback: Handler) => handlers.set(name, callback))
    }
  } as unknown as BrowserWindow
  return { ventana, handler: (name) => handlers.get(name) }
}

function simularTecla(
  handler: Handler | undefined,
  input: Record<string, unknown>
): ReturnType<typeof vi.fn> {
  const evento = { preventDefault: vi.fn() }
  handler?.(evento, input)
  return evento.preventDefault
}

describe('applyWindowProtection', () => {
  it('bloquea Ctrl+C y reporta un intento de copia', () => {
    const { ventana, handler } = ventanaFalsa()
    const alCopiar = vi.fn()
    applyWindowProtection(ventana, alCopiar)

    const prevenir = simularTecla(handler('before-input-event'), {
      type: 'keyDown',
      key: 'c',
      control: true,
      meta: false,
      alt: false,
      shift: false,
      isAutoRepeat: false
    })

    expect(prevenir).toHaveBeenCalledOnce()
    expect(alCopiar).toHaveBeenCalledWith('Ctrl+C')
  })

  it('bloquea pegar sin registrarlo como intento de copiar', () => {
    const { ventana, handler } = ventanaFalsa()
    const alCopiar = vi.fn()
    applyWindowProtection(ventana, alCopiar)

    const prevenir = simularTecla(handler('before-input-event'), {
      type: 'keyDown',
      key: 'v',
      control: true,
      meta: false,
      alt: false,
      shift: false,
      isAutoRepeat: false
    })

    expect(prevenir).toHaveBeenCalledOnce()
    expect(alCopiar).not.toHaveBeenCalled()
  })

  it('ignora repeticiones de tecla para no duplicar la infracción', () => {
    const { ventana, handler } = ventanaFalsa()
    const alCopiar = vi.fn()
    applyWindowProtection(ventana, alCopiar)

    const prevenir = simularTecla(handler('before-input-event'), {
      type: 'keyDown',
      key: 'c',
      control: true,
      meta: false,
      alt: false,
      shift: false,
      isAutoRepeat: true
    })

    expect(prevenir).not.toHaveBeenCalled()
    expect(alCopiar).not.toHaveBeenCalled()
  })
})
