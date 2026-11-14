import { describe, expect, it } from 'vitest'
import { acotarLista } from './lista-acotada'

const alumnos = Array.from({ length: 15 }, (_, i) => ({ correo: `alumno${i}@upao.edu.pe` }))

describe('acotarLista', () => {
  it('muestra solo los primeros del límite y cuenta todos', () => {
    const { visibles, coincidencias } = acotarLista(alumnos, (a) => a.correo, '', 6)
    expect(visibles).toHaveLength(6)
    expect(coincidencias).toBe(15)
  })

  it('filtra por correo sin importar mayúsculas ni espacios', () => {
    const { visibles, coincidencias } = acotarLista(alumnos, (a) => a.correo, '  ALUMNO1', 6)
    // alumno1, alumno10..alumno14
    expect(coincidencias).toBe(6)
    expect(visibles.map((a) => a.correo)).toContain('alumno12@upao.edu.pe')
  })

  it('ignora las tildes y los elementos sin texto', () => {
    const lista = [{ correo: 'jesús@upao.edu.pe' }, { correo: null }]
    expect(acotarLista(lista, (a) => a.correo, 'jesus', 6).coincidencias).toBe(1)
  })
})
