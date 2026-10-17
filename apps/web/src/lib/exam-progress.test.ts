import { describe, expect, it } from 'vitest'
import { formatRemainingTime, pageTitle, unansweredCount } from './exam-progress'

describe('exam progress helpers', () => {
  it('counts unanswered questions without returning a negative value', () => {
    expect(unansweredCount(10, 7)).toBe(3)
    expect(unansweredCount(10, 12)).toBe(0)
  })

  it('formats remaining time as mm:ss or hh:mm:ss', () => {
    expect(formatRemainingTime(65_000)).toBe('01:05')
    expect(formatRemainingTime(3_661_000)).toBe('01:01:01')
    expect(formatRemainingTime(-1)).toBe('00:00')
  })

  it('uses a neutral exam title while retaining the teacher title on teacher routes', () => {
    expect(pageTitle('/examen/abc/rendir')).toBe('Proctoring — Examen')
    expect(pageTitle('/sesiones/abc/resultados')).toBe('Proctoring — Resultados')
    expect(pageTitle('/sesiones/nueva')).toBe('Proctoring — Crear examen')
    expect(pageTitle('/docente')).toBe('Proctoring — Panel del docente')
  })
})
