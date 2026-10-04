/**
 * Guarda el examen al que entró el estudiante para sobrevivir a una recarga.
 *
 * El examen llega de `POST /sessions/join`, que necesita el código de acceso.
 * Si el estudiante recarga la página, el estado de navegación se pierde y pedir
 * el código otra vez a mitad de un examen sería una pequeña crueldad. Se guarda
 * en `sessionStorage` y no en `localStorage` a propósito: al cerrar la ventana
 * desaparece, así que el siguiente que use ese equipo no encuentra nada.
 *
 * No guarda nada sensible: título, horas y qué módulos están activos. Las
 * preguntas y las respuestas nunca pasan por aquí, siempre vienen de la API.
 */

import type { JoinedExam } from './api'

const PREFIJO = 'proctoring.examen.'

export function recordarExamen(examen: JoinedExam): void {
  try {
    sessionStorage.setItem(PREFIJO + examen.session_id, JSON.stringify(examen))
  } catch {
    // Modo privado o almacenamiento lleno: no es grave, solo se pierde el
    // atajo de la recarga.
  }
}

export function recuperarExamen(sessionId: string): JoinedExam | null {
  try {
    const guardado = sessionStorage.getItem(PREFIJO + sessionId)
    if (!guardado) return null
    const examen = JSON.parse(guardado) as JoinedExam
    // Lo mínimo para no confiar en algo que alguien editó a mano.
    return examen.session_id === sessionId && typeof examen.title === 'string' ? examen : null
  } catch {
    return null
  }
}
