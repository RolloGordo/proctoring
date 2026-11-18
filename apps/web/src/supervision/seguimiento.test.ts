import { describe, expect, it } from 'vitest'
import {
  SeguimientoCondicion,
  senalDeEpisodio,
  siguienteReporteMs,
  type Episodio,
  type OpcionesSeguimiento
} from './seguimiento'

/** Ids predecibles: `e1`, `e2`… en el orden en que se piden. */
function seguimiento(opciones: OpcionesSeguimiento): SeguimientoCondicion {
  let n = 0
  return new SeguimientoCondicion({ generarId: () => `e${++n}`, ...opciones })
}

/**
 * Un detector corre a ~15 fotogramas por segundo. Esta ayuda simula eso: una
 * lista de tramos `[activa, cuántos ms]` que se reproducen en orden.
 */
function reproducir(
  s: SeguimientoCondicion,
  tramos: Array<[boolean, number]>,
  pasoMs = 66
): Episodio[] {
  const episodios: Episodio[] = []
  let ahora = 0
  for (const [activa, duracion] of tramos) {
    const hasta = ahora + duracion
    while (ahora < hasta) {
      const episodio = s.actualizar(activa, ahora)
      if (episodio) episodios.push(episodio)
      ahora += pasoMs
    }
  }
  return episodios
}

/** Los ids distintos: cuántos episodios ve la API, no cuántos informes. */
function episodiosDistintos(informes: Episodio[]): string[] {
  return [...new Set(informes.map((e) => e.id))]
}

/** Lo que el servidor cuenta de un episodio: su informe más largo. */
function duracionFinal(informes: Episodio[], id: string): number {
  return Math.max(...informes.filter((e) => e.id === id).map((e) => e.duracionMs))
}

// Umbrales de services/api/src/proctoring_api/domain/severity.py.
const FACE_ABSENT_MEDIUM_MS = 5_000
const FACE_ABSENT_HIGH_MS = 15_000

describe('duración mínima', () => {
  it('una condición breve no emite nada', () => {
    // Mirar de reojo medio segundo no es mirar fuera de la pantalla.
    const s = seguimiento({ minimoMs: 3000 })

    expect(
      reproducir(s, [
        [false, 500],
        [true, 500],
        [false, 2000]
      ])
    ).toEqual([])
  })

  it('una condición sostenida se informa al cumplir el mínimo, sin esperar a que termine', () => {
    const s = seguimiento({ minimoMs: 3000 })

    const informes = reproducir(s, [[true, 3100]])

    expect(informes).toHaveLength(1)
    expect(informes[0].cerrado).toBe(false)
    expect(informes[0].duracionMs).toBeGreaterThanOrEqual(3000)
    expect(informes[0].duracionMs).toBeLessThanOrEqual(3100)
  })

  it('justo en el mínimo cuenta', () => {
    const s = seguimiento({ minimoMs: 1000 })

    s.actualizar(true, 0)
    const episodio = s.actualizar(true, 1000)

    expect(episodio).toEqual({ id: 'e1', inicioMs: 0, duracionMs: 1000, cerrado: false })
  })

  it('un milisegundo por debajo no', () => {
    const s = seguimiento({ minimoMs: 1000 })

    s.actualizar(true, 0)
    expect(s.actualizar(true, 999)).toBeNull()

    expect(s.cerrar()).toBeNull()
  })
})

describe('la duración real llega al servidor (prueba de carga del 18/11/2026)', () => {
  it('tres minutos sin rostro terminan en un episodio que cruza el umbral alto', () => {
    // El fallo: se emitía una vez a los 3 s y nunca más. El servidor veía
    // «3 s, leve» y el docente no recibía ninguna alerta.
    const s = seguimiento({ minimoMs: 3000 })

    const informes = reproducir(s, [
      [true, 180_000],
      [false, 1000]
    ])

    expect(episodiosDistintos(informes)).toEqual(['e1'])
    const final = informes.at(-1)!
    expect(final.cerrado).toBe(true)
    expect(final.duracionMs).toBeGreaterThan(179_000)
    expect(final.duracionMs).toBeGreaterThanOrEqual(FACE_ABSENT_HIGH_MS)
  })

  it('el informe final sale también al terminar el examen con la condición abierta', () => {
    const s = seguimiento({ minimoMs: 3000 })
    reproducir(s, [[true, 180_000]])

    const final = s.cerrar()

    expect(final?.id).toBe('e1')
    expect(final?.cerrado).toBe(true)
    expect(final?.duracionMs).toBeGreaterThan(179_000)
  })

  it('mientras sigue abierta, se informa al cruzar cada umbral del servidor, no al final', () => {
    // El docente tiene que enterarse en < 5 s, no cuando el estudiante vuelve.
    const s = seguimiento({ minimoMs: 3000 })

    const informes = reproducir(s, [[true, 20_000]])

    const abiertos = informes.filter((e) => !e.cerrado)
    expect(abiertos).toHaveLength(informes.length)
    const primeroMedio = abiertos.find((e) => e.duracionMs >= FACE_ABSENT_MEDIUM_MS)!
    const primeroAlto = abiertos.find((e) => e.duracionMs >= FACE_ABSENT_HIGH_MS)!
    // A 15 fps, a lo sumo un fotograma después de cruzar el umbral.
    expect(primeroMedio.duracionMs - FACE_ABSENT_MEDIUM_MS).toBeLessThan(100)
    expect(primeroAlto.duracionMs - FACE_ABSENT_HIGH_MS).toBeLessThan(100)
  })

  it('los informes parciales son pocos: no uno por fotograma', () => {
    // 3, 5, 10, 15, 20, 25, 30, 60, 90, 120, 150, 180 s y el cierre.
    const s = seguimiento({ minimoMs: 3000 })

    const informes = reproducir(s, [
      [true, 180_100],
      [false, 1000]
    ])

    expect(informes).toHaveLength(13)
    const duraciones = informes.map((e) => e.duracionMs)
    expect(duraciones).toEqual([...duraciones].sort((a, b) => a - b))
  })

  it('el ritmo de informe: cada 5 s hasta los 30 s, luego cada 30 s', () => {
    expect(siguienteReporteMs(3000)).toBe(5000)
    expect(siguienteReporteMs(5000)).toBe(10_000)
    expect(siguienteReporteMs(29_990)).toBe(30_000)
    expect(siguienteReporteMs(30_000)).toBe(60_000)
    expect(siguienteReporteMs(61_000)).toBe(90_000)
  })

  it('un episodio corto se informa al cumplir el mínimo y al cerrarse, con el mismo id', () => {
    const s = seguimiento({ minimoMs: 3000 })

    const informes = reproducir(s, [
      [true, 4000],
      [false, 1000]
    ])

    expect(informes.map((e) => [e.id, e.cerrado])).toEqual([
      ['e1', false],
      ['e1', true]
    ])
    expect(duracionFinal(informes, 'e1')).toBeGreaterThan(3800)
  })
})

describe('un episodio por condición, no uno por fotograma', () => {
  it('cien fotogramas seguidos siguen siendo un episodio', () => {
    // Es la regla del contrato: emitir por fotograma reventaría la meta de FPR.
    const s = seguimiento({ minimoMs: 1000 })

    const informes = reproducir(s, [
      [true, 6600],
      [false, 1000]
    ])

    expect(episodiosDistintos(informes)).toHaveLength(1)
  })

  it('dos condiciones separadas son dos episodios', () => {
    const s = seguimiento({ minimoMs: 1000 })

    const informes = reproducir(s, [
      [true, 2000],
      [false, 2000],
      [true, 2000],
      [false, 2000]
    ])

    expect(episodiosDistintos(informes)).toEqual(['e1', 'e2'])
  })
})

describe('tolerancia al parpadeo', () => {
  it('un fotograma perdido no parte la condición en dos', () => {
    // Sin esto, una ausencia real se convertiría en muchos eventos cortos,
    // ninguno llegaría al mínimo, y el docente no vería nada.
    const s = seguimiento({ minimoMs: 3000, toleranciaParpadeoMs: 400 })

    const informes = reproducir(s, [
      [true, 2000],
      [false, 66], // el detector pierde el rostro un fotograma
      [true, 2000],
      [false, 1000]
    ])

    expect(episodiosDistintos(informes)).toEqual(['e1'])
    expect(duracionFinal(informes, 'e1')).toBeGreaterThan(3000)
  })

  it('parpadeos repartidos en tres minutos siguen siendo un solo episodio', () => {
    const s = seguimiento({ minimoMs: 3000, toleranciaParpadeoMs: 400 })
    const tramos: Array<[boolean, number]> = []
    for (let i = 0; i < 36; i++) tramos.push([true, 5000], [false, 132])
    tramos.push([false, 1000])

    const informes = reproducir(s, tramos)

    expect(episodiosDistintos(informes)).toEqual(['e1'])
    expect(duracionFinal(informes, 'e1')).toBeGreaterThanOrEqual(FACE_ABSENT_HIGH_MS)
  })

  it('una pausa mayor que la tolerancia sí la parte', () => {
    const s = seguimiento({ minimoMs: 1000, toleranciaParpadeoMs: 400 })

    const informes = reproducir(s, [
      [true, 2000],
      [false, 1500], // volvió a mirar la pantalla de verdad
      [true, 2000],
      [false, 1000]
    ])

    expect(episodiosDistintos(informes)).toHaveLength(2)
  })

  it('el tiempo del parpadeo no se cuenta como parte de la condición', () => {
    const s = seguimiento({ minimoMs: 100, toleranciaParpadeoMs: 400 })

    s.actualizar(true, 0)
    s.actualizar(true, 1000)
    // Desaparece y no vuelve: el final es el último instante en que se vio.
    expect(s.actualizar(false, 1100)).toBeNull()
    const final = s.actualizar(false, 1400)

    expect(final).toEqual({ id: 'e1', inicioMs: 0, duracionMs: 1000, cerrado: true })
  })
})

describe('cerrar', () => {
  it('una condición abierta al terminar el examen no se pierde', () => {
    const s = seguimiento({ minimoMs: 1000 })
    s.actualizar(true, 0)
    s.actualizar(true, 4000)

    expect(s.cerrar()).toEqual({ id: 'e1', inicioMs: 0, duracionMs: 4000, cerrado: true })
  })

  it('cerrar sin condición abierta no inventa un evento', () => {
    const s = seguimiento({ minimoMs: 1000 })

    expect(s.cerrar()).toBeNull()
  })

  it('cerrar dos veces no duplica el evento', () => {
    const s = seguimiento({ minimoMs: 1000 })
    s.actualizar(true, 0)
    s.actualizar(true, 4000)

    expect(s.cerrar()).not.toBeNull()
    expect(s.cerrar()).toBeNull()
  })

  it('una condición abierta demasiado corta tampoco emite al cerrar', () => {
    const s = seguimiento({ minimoMs: 3000 })
    s.actualizar(true, 0)
    s.actualizar(true, 500)

    expect(s.cerrar()).toBeNull()
  })
})

describe('activa e informado', () => {
  it('dicen si hay una condición en curso y si ya se informó', () => {
    const s = seguimiento({ minimoMs: 1000 })

    expect(s.activa).toBe(false)
    s.actualizar(true, 0)
    expect(s.activa).toBe(true)
    expect(s.informado).toBe(false)
    s.actualizar(true, 1000)
    expect(s.informado).toBe(true)
    s.actualizar(false, 5000)
    expect(s.activa).toBe(false)
    expect(s.informado).toBe(false)
  })
})

describe('senalDeEpisodio', () => {
  it('lleva el id del episodio y si está cerrado, sin pisar la metadata del detector', () => {
    const senal = senalDeEpisodio(
      'face_absent',
      { id: 'e1', inicioMs: 10, duracionMs: 15_000, cerrado: true },
      { source: 'mediapipe', faces_detected: 0 }
    )

    expect(senal).toEqual({
      evento: 'face_absent',
      inicioMs: 10,
      duracionMs: 15_000,
      metadata: {
        source: 'mediapipe',
        faces_detected: 0,
        episode_id: 'e1',
        episode_closed: true
      }
    })
  })
})
