import { describe, expect, it } from 'vitest'
import { dividirEnLotes, parsearArchivoPreguntas, parsearTextoPdf } from './importar-preguntas'

describe('importar preguntas desde archivos', () => {
  it('lee CSV con alternativas y respuesta correcta aunque el enunciado tenga coma', () => {
    const preguntas = parsearArchivoPreguntas(
      'question_type,statement,points,options,correct_answer\r\n' +
        'multiple_choice,"¿Cuánto es 2 + 2?",1,"3|4|5",4',
      'csv'
    )

    expect(preguntas).toEqual([
      {
        question_type: 'multiple_choice',
        statement: '¿Cuánto es 2 + 2?',
        points: '1',
        options: [
          { option_text: '3', is_correct: false },
          { option_text: '4', is_correct: true },
          { option_text: '5', is_correct: false }
        ]
      }
    ])
  })

  it('informa fila si el CSV no tiene exactamente una alternativa correcta', () => {
    expect(() =>
      parsearArchivoPreguntas(
        'question_type,statement,options,correct_answer\n' +
          'multiple_choice,Capital de Perú,Lima|Cusco,Arequipa',
        'csv'
      )
    ).toThrow('Fila 2: marca exactamente una alternativa correcta.')
  })

  it('lee JSON con preguntas tipadas y alternativas', () => {
    const preguntas = parsearArchivoPreguntas(
      JSON.stringify([
        {
          question_type: 'true_false',
          statement: 'La Tierra orbita el Sol.',
          options: [
            { option_text: 'Verdadero', is_correct: true },
            { option_text: 'Falso', is_correct: false }
          ]
        }
      ]),
      'json'
    )

    expect(preguntas[0]).toMatchObject({ question_type: 'true_false', points: '1' })
  })

  it('mantiene el formato sencillo de una pregunta de desarrollo por línea en TXT', () => {
    const preguntas = parsearArchivoPreguntas(
      'Explica el ciclo del agua.\r\n\r\nDefine energía.',
      'txt'
    )

    expect(preguntas).toEqual([
      { question_type: 'essay', statement: 'Explica el ciclo del agua.', points: '1' },
      { question_type: 'essay', statement: 'Define energía.', points: '1' }
    ])
  })

  it('agrupa preguntas, alternativas y clave de respuestas en TXT', () => {
    const preguntas = parsearArchivoPreguntas(
      [
        'Título del banco',
        'PREGUNTA 1:',
        '¿Cuál es la capital del Perú?',
        'A) Lima',
        'B) Cusco',
        'C) Arequipa',
        '',
        'PREGUNTA 2:',
        '¿Cuánto es 2 + 2?',
        'A) 3',
        'B) 4',
        'C) 5',
        'CLAVE DE RESPUESTAS',
        '1. Respuesta: A',
        '2. Respuesta: B'
      ].join('\n'),
      'txt'
    )

    expect(preguntas).toEqual([
      {
        question_type: 'multiple_choice',
        statement: '¿Cuál es la capital del Perú?',
        points: '1',
        options: [
          { option_text: 'Lima', is_correct: true },
          { option_text: 'Cusco', is_correct: false },
          { option_text: 'Arequipa', is_correct: false }
        ]
      },
      {
        question_type: 'multiple_choice',
        statement: '¿Cuánto es 2 + 2?',
        points: '1',
        options: [
          { option_text: '3', is_correct: false },
          { option_text: '4', is_correct: true },
          { option_text: '5', is_correct: false }
        ]
      }
    ])
  })

  it('no importa opciones TXT sin respuesta correcta indicada', () => {
    expect(() =>
      parsearArchivoPreguntas(
        'PREGUNTA 1:\nElige una respuesta.\nA) Sí\nB) No',
        'txt'
      )
    ).toThrow('Pregunta 1: falta su respuesta en la clave de respuestas.')
  })

  it('lee preguntas de opción múltiple extraídas de un PDF de texto', () => {
    const preguntas = parsearTextoPdf(
      [
        'BANCO DE PRUEBA',
        'PREGUNTA 1:',
        '¿Cuál es la capital del Perú?',
        'A) Lima',
        'B) Cusco',
        'CLAVE DE RESPUESTAS',
        '1. Respuesta: A'
      ].join('\n')
    )

    expect(preguntas).toEqual([
      {
        question_type: 'multiple_choice',
        statement: '¿Cuál es la capital del Perú?',
        points: '1',
        options: [
          { option_text: 'Lima', is_correct: true },
          { option_text: 'Cusco', is_correct: false }
        ]
      }
    ])
  })

  it('explica que el PDF debe tener estructura y texto seleccionable', () => {
    expect(() => parsearTextoPdf('Documento escaneado sin texto extraíble')).toThrow(
      'No se encontraron preguntas con el formato requerido.'
    )
  })

  it('rechaza una pregunta incompleta en vez de importarla parcialmente', () => {
    expect(() =>
      parsearArchivoPreguntas(
        JSON.stringify([{ question_type: 'numeric', statement: '¿Cuánto es 2 + 2?' }]),
        'json'
      )
    ).toThrow('Pregunta 1: falta una "correct_numeric_answer" numérica válida.')
  })

  it('divide archivos grandes en grupos de hasta 50 preguntas', () => {
    const preguntas = Array.from({ length: 115 }, (_, indice) => indice)
    const lotes = dividirEnLotes(preguntas, 50)

    expect(lotes.map((lote) => lote.length)).toEqual([50, 50, 15])
    expect(lotes.flat()).toEqual(preguntas)
  })

  it('no acepta un tamaño de lote inválido', () => {
    expect(() => dividirEnLotes([1, 2], 0)).toThrow(
      'El tamaño del lote debe ser un entero positivo.'
    )
  })
})
