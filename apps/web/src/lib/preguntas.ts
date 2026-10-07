import type { QuestionType } from './api'

/**
 * Lo que saben las pantallas de preguntas sin ser pantallas.
 *
 * Vive fuera del componente por dos razones: así el editor se puede recargar en
 * caliente sin perder el estado, y así `sinCorrectaHuerfana` —que es la única
 * regla de verdad que hay aquí— se puede probar sin montar React.
 */

export const TIPOS: Array<{ valor: QuestionType; nombre: string; ayuda: string }> = [
  {
    valor: 'multiple_choice',
    nombre: 'Opción múltiple',
    ayuda: 'Varias alternativas, una correcta.'
  },
  { valor: 'true_false', nombre: 'Verdadero o falso', ayuda: 'Exactamente dos opciones.' },
  { valor: 'numeric', nombre: 'Respuesta numérica', ayuda: 'Se compara con el valor exacto.' },
  { valor: 'fill_blank', nombre: 'Completar', ayuda: 'Se compara con el texto esperado.' },
  { valor: 'essay', nombre: 'Desarrollo', ayuda: 'La califica el docente a mano.' }
]

/** Los tipos que se responden eligiendo una alternativa. */
export const LLEVA_OPCIONES = new Set<QuestionType>(['multiple_choice', 'true_false'])

export function nombreDeTipo(tipo: QuestionType): string {
  return TIPOS.find((t) => t.valor === tipo)?.nombre ?? tipo
}

export interface OpcionEditable {
  option_text: string
  is_correct: boolean
}

export const OPCIONES_INICIALES: OpcionEditable[] = [
  { option_text: '', is_correct: true },
  { option_text: '', is_correct: false }
]

/**
 * Quita una opción y, si era la correcta, marca la primera que queda.
 *
 * Sin esto, borrar la correcta dejaría la pregunta sin ninguna y la API la
 * rechazaría con un error que el docente no sabría de dónde viene.
 */
export function sinCorrectaHuerfana(
  opciones: OpcionEditable[],
  indice: number
): OpcionEditable[] {
  const restantes = opciones.filter((_, i) => i !== indice)
  if (restantes.some((o) => o.is_correct)) return restantes
  return restantes.map((o, i) => ({ ...o, is_correct: i === 0 }))
}
