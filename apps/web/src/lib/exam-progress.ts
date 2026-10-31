export function unansweredCount(totalQuestions: number, answeredCount: number): number {
  return Math.max(0, totalQuestions - answeredCount)
}

export function formatRemainingTime(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  const pad = (value: number): string => String(value).padStart(2, '0')

  return hours > 0
    ? `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`
    : `${pad(minutes)}:${pad(seconds)}`
}

export function pageTitle(pathname: string): string {
  if (pathname.startsWith('/examen/')) return 'Proctoring — Examen'
  if (pathname === '/examen') return 'Proctoring — Acceso al examen'
  if (pathname === '/sesiones/nueva') return 'Proctoring — Crear examen'
  if (pathname.endsWith('/resultados')) return 'Proctoring — Resultados'
  if (pathname.includes('/estudiantes/')) return 'Proctoring — Revisión de caso'
  if (pathname.endsWith('/preguntas')) return 'Proctoring — Preguntas del examen'
  if (pathname.endsWith('/participantes')) return 'Proctoring — Participantes'
  if (pathname.endsWith('/editar')) return 'Proctoring — Configuración del examen'
  if (pathname.startsWith('/sesiones')) return 'Proctoring — Panel del docente'
  if (pathname.startsWith('/docente')) return 'Proctoring — Panel del docente'
  if (pathname.startsWith('/estudiante')) return 'Proctoring — Panel del estudiante'
  return 'Proctoring'
}
