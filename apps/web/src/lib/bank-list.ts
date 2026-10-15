import type { QuestionBank } from './api'

export const TODOS_LOS_CURSOS = 'todos'
export const BANCOS_SIN_CURSO = 'sin-curso'

export function filtrarBancosPorCurso(bancos: QuestionBank[], cursoId: string): QuestionBank[] {
  if (cursoId === TODOS_LOS_CURSOS) return bancos
  if (cursoId === BANCOS_SIN_CURSO) return bancos.filter((banco) => banco.course_id === null)
  return bancos.filter((banco) => banco.course_id === cursoId)
}
