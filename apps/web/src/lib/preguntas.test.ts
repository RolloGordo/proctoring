import { describe, expect, it } from 'vitest'
import { LLEVA_OPCIONES, nombreDeTipo, sinCorrectaHuerfana } from './preguntas'

describe('sinCorrectaHuerfana', () => {
  it('quita la opción indicada', () => {
    const opciones = [
      { option_text: 'a', is_correct: true },
      { option_text: 'b', is_correct: false },
      { option_text: 'c', is_correct: false }
    ]

    expect(sinCorrectaHuerfana(opciones, 1).map((o) => o.option_text)).toEqual(['a', 'c'])
  })

  it('no toca la correcta si la borrada era otra', () => {
    const opciones = [
      { option_text: 'a', is_correct: false },
      { option_text: 'b', is_correct: true },
      { option_text: 'c', is_correct: false }
    ]

    const restantes = sinCorrectaHuerfana(opciones, 0)

    expect(restantes.filter((o) => o.is_correct).map((o) => o.option_text)).toEqual(['b'])
  })

  it('marca la primera cuando se borra la correcta', () => {
    // Sin esto la pregunta se queda sin ninguna correcta y la API la rechaza
    // con un error que el docente no sabe de dónde viene.
    const opciones = [
      { option_text: 'a', is_correct: true },
      { option_text: 'b', is_correct: false },
      { option_text: 'c', is_correct: false }
    ]

    const restantes = sinCorrectaHuerfana(opciones, 0)

    expect(restantes.filter((o) => o.is_correct).map((o) => o.option_text)).toEqual(['b'])
  })

  it('deja exactamente una correcta en cualquier caso', () => {
    const opciones = [
      { option_text: 'a', is_correct: false },
      { option_text: 'b', is_correct: true }
    ]

    for (let i = 0; i < opciones.length; i += 1) {
      expect(sinCorrectaHuerfana(opciones, i).filter((o) => o.is_correct)).toHaveLength(1)
    }
  })

  it('no modifica el arreglo que recibe', () => {
    const opciones = [
      { option_text: 'a', is_correct: true },
      { option_text: 'b', is_correct: false }
    ]

    sinCorrectaHuerfana(opciones, 0)

    expect(opciones[0].is_correct).toBe(true)
    expect(opciones).toHaveLength(2)
  })
})

describe('tipos de pregunta', () => {
  it('solo opción múltiple y verdadero/falso llevan alternativas', () => {
    expect([...LLEVA_OPCIONES].sort()).toEqual(['multiple_choice', 'true_false'])
  })

  it('cada tipo tiene un nombre en español', () => {
    expect(nombreDeTipo('essay')).toBe('Desarrollo')
    expect(nombreDeTipo('numeric')).toBe('Respuesta numérica')
  })
})
