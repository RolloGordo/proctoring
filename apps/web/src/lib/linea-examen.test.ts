import { describe, expect, it } from 'vitest'
import type { Alert } from './api'
import { haceCuanto, lineaExamen } from './linea-examen'

const INICIO = '2026-11-03T13:00:00.000Z'
const inicioMs = new Date(INICIO).getTime()
const min = 60_000

function alerta(id: string, minuto: number, severity: Alert['severity']): Alert {
  return {
    id,
    event_id: `e-${id}`,
    session_id: 's',
    student_id: 'u',
    severity,
    reason: `motivo ${id}`,
    created_at: new Date(inicioMs + minuto * min).toISOString()
  }
}

describe('lineaExamen', () => {
  it('sabe cuánto pasó y cuánto falta', () => {
    const linea = lineaExamen(INICIO, 90, inicioMs + 30 * min)
    expect(linea.transcurrido).toBeCloseTo(1 / 3)
    expect(linea.faltan).toBe(60)
    expect(linea.finMs).toBe(inicioMs + 90 * min)
  })

  it('coloca cada alerta en su minuto y cuenta las severidades', () => {
    const linea = lineaExamen(INICIO, 60, inicioMs + 40 * min, [
      alerta('b', 30, 'medium'),
      alerta('a', 15, 'high'),
      alerta('c', 33, 'high')
    ])
    expect(linea.marcas.map((m) => m.id)).toEqual(['a', 'b', 'c'])
    expect(linea.marcas[0].en).toBeCloseTo(0.25)
    expect(linea.cuenta).toEqual({ high: 2, medium: 1, low: 0 })
    expect(linea.ultima?.id).toBe('c')
  })

  it('pega al borde lo que cae fuera del examen', () => {
    const linea = lineaExamen(INICIO, 60, inicioMs + 70 * min, [
      alerta('antes', -5, 'low'),
      alerta('despues', 65, 'low')
    ])
    expect(linea.marcas.map((m) => m.en)).toEqual([0, 1])
    expect(linea.transcurrido).toBe(1)
    expect(linea.faltan).toBe(0)
  })

  it('sin alertas no hay última y todo está a cero', () => {
    const linea = lineaExamen(INICIO, 45, inicioMs)
    expect(linea.ultima).toBeUndefined()
    expect(linea.cuenta).toEqual({ high: 0, medium: 0, low: 0 })
    expect(linea.faltan).toBe(45)
  })
})

describe('haceCuanto', () => {
  it('dice el tiempo en palabras', () => {
    expect(haceCuanto(20_000)).toBe('hace un momento')
    expect(haceCuanto(4 * min)).toBe('hace 4 min')
    expect(haceCuanto(130 * min)).toBe('hace 2 h')
  })
})
