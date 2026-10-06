import { describe, expect, it } from 'vitest'
import { SeguimientoCondicion } from './seguimiento'

/**
 * Un detector corre a ~15 fotogramas por segundo. Esta ayuda simula eso: una
 * lista de tramos `[activa, cuántos ms]` que se reproducen en orden.
 */
function reproducir(
  seguimiento: SeguimientoCondicion,
  tramos: Array<[boolean, number]>,
  pasoMs = 66
): Array<{ inicioMs: number; duracionMs: number }> {
  const episodios = []
  let ahora = 0
  for (const [activa, duracion] of tramos) {
    const hasta = ahora + duracion
    while (ahora < hasta) {
      const episodio = seguimiento.actualizar(activa, ahora)
      if (episodio) episodios.push(episodio)
      ahora += pasoMs
    }
  }
  return episodios
}

describe('duración mínima', () => {
  it('una condición breve no emite nada', () => {
    // Mirar de reojo medio segundo no es mirar fuera de la pantalla.
    const s = new SeguimientoCondicion({ minimoMs: 3000 })

    expect(
      reproducir(s, [
        [false, 500],
        [true, 500],
        [false, 2000]
      ])
    ).toEqual([])
  })

  it('una condición sostenida emite un solo evento con su duración', () => {
    const s = new SeguimientoCondicion({ minimoMs: 3000 })

    const episodios = reproducir(s, [
      [true, 5000],
      [false, 2000]
    ])

    expect(episodios).toHaveLength(1)
    // La duración se mide hasta la última vez que se vio activa, así que cae
    // dentro del tramo con el margen de un fotograma.
    expect(episodios[0].duracionMs).toBeGreaterThanOrEqual(4900)
    expect(episodios[0].duracionMs).toBeLessThanOrEqual(5000)
  })

  it('justo en el mínimo cuenta', () => {
    const s = new SeguimientoCondicion({ minimoMs: 1000 })

    s.actualizar(true, 0)
    s.actualizar(true, 1000)
    const episodio = s.cerrar()

    expect(episodio).toEqual({ inicioMs: 0, duracionMs: 1000 })
  })

  it('un milisegundo por debajo no', () => {
    const s = new SeguimientoCondicion({ minimoMs: 1000 })

    s.actualizar(true, 0)
    s.actualizar(true, 999)

    expect(s.cerrar()).toBeNull()
  })
})

describe('un evento por condición, no uno por fotograma', () => {
  it('cien fotogramas seguidos siguen siendo un evento', () => {
    // Es la regla del contrato: emitir por fotograma reventaría la meta de FPR.
    const s = new SeguimientoCondicion({ minimoMs: 1000 })

    const episodios = reproducir(s, [
      [true, 6600],
      [false, 1000]
    ])

    expect(episodios).toHaveLength(1)
  })

  it('dos condiciones separadas son dos eventos', () => {
    const s = new SeguimientoCondicion({ minimoMs: 1000 })

    const episodios = reproducir(s, [
      [true, 2000],
      [false, 2000],
      [true, 2000],
      [false, 2000]
    ])

    expect(episodios).toHaveLength(2)
  })
})

describe('tolerancia al parpadeo', () => {
  it('un fotograma perdido no parte la condición en dos', () => {
    // Sin esto, una ausencia real se convertiría en muchos eventos cortos,
    // ninguno llegaría al mínimo, y el docente no vería nada.
    const s = new SeguimientoCondicion({ minimoMs: 3000, toleranciaParpadeoMs: 400 })

    const episodios = reproducir(s, [
      [true, 2000],
      [false, 66], // el detector pierde el rostro un fotograma
      [true, 2000],
      [false, 1000]
    ])

    expect(episodios).toHaveLength(1)
    expect(episodios[0].duracionMs).toBeGreaterThan(3000)
  })

  it('una pausa mayor que la tolerancia sí la parte', () => {
    const s = new SeguimientoCondicion({ minimoMs: 1000, toleranciaParpadeoMs: 400 })

    const episodios = reproducir(s, [
      [true, 2000],
      [false, 1500], // volvió a mirar la pantalla de verdad
      [true, 2000],
      [false, 1000]
    ])

    expect(episodios).toHaveLength(2)
  })

  it('el tiempo del parpadeo no se cuenta como parte de la condición', () => {
    const s = new SeguimientoCondicion({ minimoMs: 100, toleranciaParpadeoMs: 400 })

    s.actualizar(true, 0)
    s.actualizar(true, 1000)
    // Desaparece y no vuelve: el final es el último instante en que se vio.
    s.actualizar(false, 1100)
    const episodio = s.actualizar(false, 1500)

    expect(episodio).toEqual({ inicioMs: 0, duracionMs: 1000 })
  })
})

describe('cerrar', () => {
  it('una condición abierta al terminar el examen no se pierde', () => {
    const s = new SeguimientoCondicion({ minimoMs: 1000 })
    s.actualizar(true, 0)
    s.actualizar(true, 4000)

    expect(s.cerrar()).toEqual({ inicioMs: 0, duracionMs: 4000 })
  })

  it('cerrar sin condición abierta no inventa un evento', () => {
    const s = new SeguimientoCondicion({ minimoMs: 1000 })

    expect(s.cerrar()).toBeNull()
  })

  it('cerrar dos veces no duplica el evento', () => {
    const s = new SeguimientoCondicion({ minimoMs: 1000 })
    s.actualizar(true, 0)
    s.actualizar(true, 4000)

    expect(s.cerrar()).not.toBeNull()
    expect(s.cerrar()).toBeNull()
  })

  it('una condición abierta demasiado corta tampoco emite al cerrar', () => {
    const s = new SeguimientoCondicion({ minimoMs: 3000 })
    s.actualizar(true, 0)
    s.actualizar(true, 500)

    expect(s.cerrar()).toBeNull()
  })
})

describe('activa', () => {
  it('dice si hay una condición en curso', () => {
    const s = new SeguimientoCondicion({ minimoMs: 1000 })

    expect(s.activa).toBe(false)
    s.actualizar(true, 0)
    expect(s.activa).toBe(true)
    s.actualizar(false, 5000)
    expect(s.activa).toBe(false)
  })
})
