import { describe, expect, it } from 'vitest'
import { siglaDeCurso, tonoDeCurso } from './curso'

describe('siglaDeCurso', () => {
  it.each([
    ['Taller Integrador 1', 'TI1'],
    ['Administración de proyectos', 'AP'],
    ['Sistemas de Información para la Gestión', 'SIG'],
    ['Física', 'F'],
    ['   ', '·']
  ])('%s → %s', (nombre, sigla) => {
    expect(siglaDeCurso(nombre)).toBe(sigla)
  })

  it('no pasa de cuatro letras', () => {
    expect(siglaDeCurso('Uno Dos Tres Cuatro Cinco Seis')).toBe('UDTC')
  })
})

describe('tonoDeCurso', () => {
  it('da el mismo tono al mismo curso', () => {
    const id = '9ecad950-b74d-42ca-bce3-509cd0b6c9e4'
    expect(tonoDeCurso(id)).toBe(tonoDeCurso(id))
  })

  it('reparte los cursos entre varios tonos', () => {
    const tonos = new Set(
      Array.from({ length: 40 }, (_, i) => tonoDeCurso(`curso-${i}-${i * 7919}`))
    )
    expect(tonos.size).toBeGreaterThan(3)
  })
})
