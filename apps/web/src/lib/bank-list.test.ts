import { describe, expect, it } from 'vitest'
import type { QuestionBank } from './api'
import { BANCOS_SIN_CURSO, filtrarBancosPorCurso, TODOS_LOS_CURSOS } from './bank-list'

const bancos: QuestionBank[] = [
  {
    id: 'bank-1',
    name: 'Banco A',
    course_id: 'course-1',
    description: null,
    created_at: '2026-10-15T00:00:00Z',
    question_count: 2
  },
  {
    id: 'bank-2',
    name: 'Banco B',
    course_id: 'course-2',
    description: null,
    created_at: '2026-10-15T00:00:00Z',
    question_count: 1
  },
  {
    id: 'bank-3',
    name: 'Banco sin curso',
    course_id: null,
    description: null,
    created_at: '2026-10-15T00:00:00Z',
    question_count: 0
  }
]

describe('filtrar bancos por curso', () => {
  it('muestra todos los bancos sin cambiar su orden', () => {
    expect(filtrarBancosPorCurso(bancos, TODOS_LOS_CURSOS)).toEqual(bancos)
  })

  it('muestra solo los bancos asociados al curso elegido', () => {
    expect(filtrarBancosPorCurso(bancos, 'course-2')).toEqual([bancos[1]])
  })

  it('mantiene accesibles los bancos existentes que no tienen curso', () => {
    expect(filtrarBancosPorCurso(bancos, BANCOS_SIN_CURSO)).toEqual([bancos[2]])
  })

  it('devuelve una lista vacía si el curso no tiene bancos', () => {
    expect(filtrarBancosPorCurso(bancos, 'course-empty')).toEqual([])
  })
})
