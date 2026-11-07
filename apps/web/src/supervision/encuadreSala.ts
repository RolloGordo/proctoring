/**
 * Lo que recuerda la sala de espera de la comprobación de encuadre (Jesús).
 *
 * Va en `sessionStorage`, por sesión de examen y estudiante, como la
 * calibración de la mirada. Es una comodidad para no repetir la prueba al
 * recargar; NO es la garantía: durante el examen `DetectorEncuadre` sigue
 * mirando, así que saltarse la sala no sirve de nada.
 */
export type EstadoEncuadreSala = 'passed' | 'unavailable'

const VIGENCIA_MS = 6 * 60 * 60 * 1000

function clave(sessionId: string, studentId: string): string {
  return `proctoring:framing-check:v1:${sessionId}:${studentId}`
}

export function guardarEncuadre(
  sessionId: string,
  studentId: string,
  estado: EstadoEncuadreSala
): void {
  try {
    sessionStorage.setItem(clave(sessionId, studentId), JSON.stringify({ estado, en: Date.now() }))
  } catch {
    // Sin almacenamiento solo se pierde la comodidad: se repite la prueba.
  }
}

export function leerEncuadre(sessionId: string, studentId: string): EstadoEncuadreSala | null {
  try {
    const valor: unknown = JSON.parse(sessionStorage.getItem(clave(sessionId, studentId)) ?? 'null')
    if (!valor || typeof valor !== 'object') return null
    const { estado, en } = valor as { estado?: unknown; en?: unknown }
    if (estado !== 'passed' && estado !== 'unavailable') return null
    if (typeof en !== 'number' || Date.now() - en > VIGENCIA_MS) return null
    return estado
  } catch {
    return null
  }
}
