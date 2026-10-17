import { describe, expect, it, vi } from 'vitest'
import { conLimite, prepararDetectores } from './arranque'
import type { Detector, DetectorContext } from './tipos'

// No hace falta un MediaStream de verdad: `prepararDetectores` solo lo pasa
// de largo, y en el entorno de pruebas la clase no existe.
const contexto = {
  stream: { getAudioTracks: () => [], getVideoTracks: () => [] },
  captureSender: () => () => undefined
} as unknown as DetectorContext

function detector(nombre: string, preparar?: Detector['preparar']): Detector {
  return {
    nombre,
    evento: 'gaze_away',
    minimoMs: 1000,
    preparar,
    observar: () => ({ activa: false }),
    detener: vi.fn()
  } as unknown as Detector
}

describe('el limite de tiempo', () => {
  it('deja pasar lo que responde a tiempo', async () => {
    await expect(conLimite(Promise.resolve('va'), 1000)).resolves.toBe('va')
  })

  it('rechaza lo que no vuelve nunca', async () => {
    vi.useFakeTimers()
    const nunca = new Promise<void>(() => {})
    const carrera = conLimite(nunca, 5000)
    const esperado = expect(carrera).rejects.toThrow('No arrancó en 5000 ms.')
    await vi.advanceTimersByTimeAsync(5001)
    await esperado
    vi.useRealTimers()
  })
})

describe('arrancar los detectores', () => {
  it('uno que se cuelga no impide que arranquen los demas', async () => {
    // **El fallo que dejaba el examen sin supervision de camara.** Se
    // preparaban en serie, y el de habla es el ultimo de la lista: con el VAD
    // colgado, el bucle no terminaba y el intervalo que mira fotogramas no
    // llegaba a crearse. Los tres detectores de vision no miraban nada y
    // tampoco constaban como caidos.
    vi.useFakeTimers()
    const mirada = detector('mirada', async () => undefined)
    const rostro = detector('rostro-ausente', async () => undefined)
    const habla = detector('habla', () => new Promise<void>(() => {}))

    const corriendo = prepararDetectores([mirada, rostro, habla], contexto, 15_000)
    await vi.advanceTimersByTimeAsync(15_001)
    const arranques = await corriendo

    expect(arranques.filter((a) => a.listo).map((a) => a.detector.nombre)).toEqual([
      'mirada',
      'rostro-ausente'
    ])
    const colgado = arranques.find((a) => a.detector.nombre === 'habla')
    expect(colgado?.listo).toBe(false)
    expect(colgado?.motivo).toContain('No arrancó')
    vi.useRealTimers()
  })

  it('al que no arranca se le apaga, para no dejar el microfono encendido', async () => {
    const roto = detector('habla', async () => {
      throw new Error('sin micrófono')
    })
    const [arranque] = await prepararDetectores([roto], contexto)

    expect(arranque.listo).toBe(false)
    expect(arranque.motivo).toBe('sin micrófono')
    expect(roto.detener).toHaveBeenCalled()
  })

  it('un detector sin preparar() cuenta como listo', async () => {
    const simple = detector('mirada')
    const [arranque] = await prepararDetectores([simple], contexto)
    expect(arranque.listo).toBe(true)
  })

  it('no lanza nunca: un detector caido es informacion, no una excepcion', async () => {
    const roto = detector('mirada', async () => {
      throw new Error('modelo no disponible')
    })
    await expect(prepararDetectores([roto], contexto)).resolves.toHaveLength(1)
  })
})
