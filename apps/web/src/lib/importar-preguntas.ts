import type { NewQuestion, QuestionType } from './api'

export type FormatoArchivoPreguntas = 'csv' | 'json' | 'txt'

export function parsearTextoPdf(contenido: string): NewQuestion[] {
  if (!/^\s*PREGUNTA\s+\d+\s*:/im.test(contenido)) {
    throw new Error(
      'No se encontraron preguntas con el formato requerido. Usa títulos "PREGUNTA 1:", alternativas A), B), etc. y una clave de respuestas. Los PDF escaneados no se pueden procesar.'
    )
  }
  return parsearTxt(contenido)
}

export function dividirEnLotes<T>(valores: T[], tamaño: number): T[][] {
  if (!Number.isInteger(tamaño) || tamaño < 1) {
    throw new Error('El tamaño del lote debe ser un entero positivo.')
  }
  const lotes: T[][] = []
  for (let inicio = 0; inicio < valores.length; inicio += tamaño) {
    lotes.push(valores.slice(inicio, inicio + tamaño))
  }
  return lotes
}

const TIPOS_VALIDOS: QuestionType[] = [
  'multiple_choice',
  'true_false',
  'numeric',
  'fill_blank',
  'essay'
]

export function parsearArchivoPreguntas(
  contenido: string,
  formato: FormatoArchivoPreguntas
): NewQuestion[] {
  if (formato === 'txt') {
    return parsearTxt(contenido)
  }

  if (formato === 'json') return parsearJson(contenido)
  return parsearCsv(contenido)
}

function parsearTxt(contenido: string): NewQuestion[] {
  const lineas = contenido.replace(/^\uFEFF/, '').split(/\r?\n/)
  const bloques: { numero: number; lineas: string[] }[] = []
  const respuestas = new Map<number, string>()
  let bloqueActual: { numero: number; lineas: string[] } | undefined
  let enClave = false

  for (const linea of lineas) {
    if (/^\s*CLAVE\s+DE\s+RESPUESTAS\s*$/i.test(linea)) {
      enClave = true
      bloqueActual = undefined
      continue
    }

    if (enClave) {
      const respuesta = linea.match(/^\s*(\d+)[.)]\s*Respuesta:\s*([A-Z])\s*$/i)
      if (respuesta) {
        const numero = Number(respuesta[1])
        if (respuestas.has(numero)) {
          throw new Error(`La clave de respuestas repite la pregunta ${numero}.`)
        }
        respuestas.set(numero, respuesta[2].toUpperCase())
      }
      continue
    }

    const inicioPregunta = linea.match(/^\s*PREGUNTA\s+(\d+)\s*:\s*(.*)$/i)
    if (inicioPregunta) {
      bloqueActual = { numero: Number(inicioPregunta[1]), lineas: [] }
      bloques.push(bloqueActual)
      if (inicioPregunta[2].trim()) bloqueActual.lineas.push(inicioPregunta[2].trim())
    } else if (bloqueActual) {
      bloqueActual.lineas.push(linea)
    }
  }

  if (bloques.length === 0) {
    const preguntas = lineas
      .map((linea) => linea.trim())
      .filter(Boolean)
      .map((statement) => ({ question_type: 'essay' as const, statement, points: '1' }))
    if (preguntas.length === 0) throw new Error('El archivo TXT no contiene preguntas.')
    return preguntas
  }

  const numeros = new Set<number>()
  const preguntas = bloques.map(({ numero, lineas: lineasBloque }) => {
    if (numeros.has(numero)) throw new Error(`El TXT repite el número de pregunta ${numero}.`)
    numeros.add(numero)

    const enunciado: string[] = []
    const opciones: { letra: string; texto: string }[] = []
    let opcionActual: { letra: string; texto: string } | undefined

    for (const linea of lineasBloque) {
      const texto = linea.trim()
      if (!texto || /^[=_-]{3,}$/.test(texto)) continue

      const alternativa = texto.match(/^([A-Z])[).]\s*(.+)$/i)
      if (alternativa) {
        opcionActual = { letra: alternativa[1].toUpperCase(), texto: alternativa[2].trim() }
        opciones.push(opcionActual)
      } else if (opcionActual) {
        opcionActual.texto += ` ${texto}`
      } else {
        enunciado.push(texto)
      }
    }

    const statement = enunciado.join(' ').trim()
    if (!statement) throw new Error(`Pregunta ${numero}: falta el enunciado.`)

    if (opciones.length === 1) {
      throw new Error(`Pregunta ${numero}: agrega al menos dos alternativas.`)
    }
    if (opciones.length === 0) {
      return { question_type: 'essay' as const, statement, points: '1' }
    }

    const letraCorrecta = respuestas.get(numero)
    if (!letraCorrecta) {
      throw new Error(`Pregunta ${numero}: falta su respuesta en la clave de respuestas.`)
    }
    if (!opciones.some((opcion) => opcion.letra === letraCorrecta)) {
      throw new Error(
        `Pregunta ${numero}: la alternativa ${letraCorrecta} no existe en sus opciones.`
      )
    }
    if (new Set(opciones.map((opcion) => opcion.letra)).size !== opciones.length) {
      throw new Error(`Pregunta ${numero}: hay letras de alternativas repetidas.`)
    }

    return {
      question_type: 'multiple_choice' as const,
      statement,
      points: '1',
      options: opciones.map(({ letra, texto }) => ({
        option_text: texto,
        is_correct: letra === letraCorrecta
      }))
    }
  })

  for (const numero of respuestas.keys()) {
    if (!numeros.has(numero)) {
      throw new Error(`La clave de respuestas incluye la pregunta ${numero}, que no existe.`)
    }
  }

  return preguntas
}

function parsearJson(contenido: string): NewQuestion[] {
  let datos: unknown
  try {
    datos = JSON.parse(contenido)
  } catch {
    throw new Error('El archivo JSON no tiene una sintaxis válida.')
  }
  if (!Array.isArray(datos) || datos.length === 0) {
    throw new Error('El JSON debe ser una lista con al menos una pregunta.')
  }
  return datos.map((item, indice) => validarPregunta(item, `Pregunta ${indice + 1}`))
}

function parsearCsv(contenido: string): NewQuestion[] {
  const filas = leerCsv(contenido.replace(/^\uFEFF/, ''))
  while (filas.length > 0 && filas.at(-1)?.every((celda) => !celda.trim())) filas.pop()
  if (filas.length < 2) throw new Error('El CSV debe incluir encabezados y al menos una pregunta.')

  const encabezados = filas[0].map((celda) => celda.trim().toLowerCase())
  const duplicados = encabezados.filter((nombre, indice) => encabezados.indexOf(nombre) !== indice)
  if (duplicados.length > 0) {
    throw new Error(`El CSV repite el encabezado "${duplicados[0]}".`)
  }
  for (const requerido of ['question_type', 'statement']) {
    if (!encabezados.includes(requerido)) {
      throw new Error(`Al CSV le falta el encabezado obligatorio "${requerido}".`)
    }
  }

  return filas.slice(1).map((fila, indice) => {
    if (fila.length > encabezados.length) {
      throw new Error(`Fila ${indice + 2}: hay más columnas que encabezados.`)
    }
    const celdas = Object.fromEntries(encabezados.map((nombre, i) => [nombre, fila[i] ?? '']))
    const tipo = celdas.question_type.trim()
    const puntos = (celdas.points ?? '').trim() || '1'
    const respuesta = (celdas.correct_answer ?? '').trim()
    const opciones = (celdas.options ?? '')
      .split('|')
      .map((opcion) => opcion.trim())
      .filter(Boolean)

    const pregunta: Record<string, unknown> = {
      question_type: tipo,
      statement: celdas.statement,
      points: puntos
    }

    if (tipo === 'multiple_choice' || tipo === 'true_false') {
      pregunta.options = opciones.map((option_text) => ({
        option_text,
        is_correct: option_text === respuesta
      }))
    } else if (tipo === 'numeric') {
      pregunta.correct_numeric_answer = respuesta
    } else if (tipo === 'fill_blank') {
      pregunta.correct_text_answer = respuesta
    }

    return validarPregunta(pregunta, `Fila ${indice + 2}`)
  })
}

function validarPregunta(valor: unknown, referencia: string): NewQuestion {
  if (!esObjeto(valor)) throw new Error(`${referencia}: se esperaba un objeto de pregunta.`)
  const tipo = valor.question_type
  if (typeof tipo !== 'string' || !TIPOS_VALIDOS.includes(tipo as QuestionType)) {
    throw new Error(`${referencia}: "question_type" no es un tipo de pregunta válido.`)
  }
  if (typeof valor.statement !== 'string' || !valor.statement.trim()) {
    throw new Error(`${referencia}: falta el enunciado "statement".`)
  }

  const points = valor.points === undefined ? '1' : String(valor.points)
  const puntosNumero = Number(points)
  if (!Number.isFinite(puntosNumero) || puntosNumero < 0 || puntosNumero > 100) {
    throw new Error(`${referencia}: "points" debe ser un número entre 0 y 100.`)
  }

  const question_type = tipo as QuestionType
  const pregunta: NewQuestion = {
    question_type,
    statement: valor.statement.trim(),
    points
  }

  if (question_type === 'multiple_choice' || question_type === 'true_false') {
    if (!Array.isArray(valor.options)) {
      throw new Error(`${referencia}: "options" debe ser una lista de alternativas.`)
    }
    const options = valor.options.map((option, indice) => {
      if (!esObjeto(option) || typeof option.option_text !== 'string') {
        throw new Error(`${referencia}: la alternativa ${indice + 1} no tiene "option_text".`)
      }
      if (typeof option.is_correct !== 'boolean') {
        throw new Error(
          `${referencia}: la alternativa ${indice + 1} debe tener is_correct true o false.`
        )
      }
      return { option_text: option.option_text.trim(), is_correct: option.is_correct }
    })
    if (options.length < 2 || options.some((option) => !option.option_text)) {
      throw new Error(`${referencia}: agrega al menos dos alternativas con texto.`)
    }
    if (question_type === 'true_false' && options.length !== 2) {
      throw new Error(
        `${referencia}: una pregunta verdadero/falso debe tener exactamente dos alternativas.`
      )
    }
    if (options.filter((option) => option.is_correct).length !== 1) {
      throw new Error(`${referencia}: marca exactamente una alternativa correcta.`)
    }
    pregunta.options = options
  }

  if (question_type === 'numeric') {
    const answer = valor.correct_numeric_answer
    if (
      (typeof answer !== 'string' && typeof answer !== 'number') ||
      !Number.isFinite(Number(answer))
    ) {
      throw new Error(`${referencia}: falta una "correct_numeric_answer" numérica válida.`)
    }
    pregunta.correct_numeric_answer = String(answer)
  }

  if (question_type === 'fill_blank') {
    if (typeof valor.correct_text_answer !== 'string' || !valor.correct_text_answer.trim()) {
      throw new Error(`${referencia}: falta "correct_text_answer".`)
    }
    pregunta.correct_text_answer = valor.correct_text_answer.trim()
  }

  return pregunta
}

function leerCsv(contenido: string): string[][] {
  const filas: string[][] = []
  let fila: string[] = []
  let celda = ''
  let entreComillas = false

  for (let i = 0; i < contenido.length; i += 1) {
    const caracter = contenido[i]
    if (entreComillas) {
      if (caracter === '"' && contenido[i + 1] === '"') {
        celda += '"'
        i += 1
      } else if (caracter === '"') {
        entreComillas = false
      } else {
        celda += caracter
      }
    } else if (caracter === '"' && celda.length === 0) {
      entreComillas = true
    } else if (caracter === ',') {
      fila.push(celda)
      celda = ''
    } else if (caracter === '\n' || caracter === '\r') {
      if (caracter === '\r' && contenido[i + 1] === '\n') i += 1
      fila.push(celda)
      filas.push(fila)
      fila = []
      celda = ''
    } else {
      celda += caracter
    }
  }

  if (entreComillas) throw new Error('El CSV tiene un campo entre comillas que no se cerró.')
  fila.push(celda)
  if (fila.some((valor) => valor.length > 0) || filas.length === 0) filas.push(fila)
  return filas
}

function esObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === 'object' && valor !== null && !Array.isArray(valor)
}
