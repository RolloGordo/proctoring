import type { Alert, Participant } from './api'

/**
 * Los números rojos de las pestañas del examen (HU-038).
 *
 * El docente no puede estar mirando la sala de espera y la actividad a la vez.
 * Sin esto, un estudiante esperando que lo admitan o una alerta nueva solo se
 * descubrían entrando a la pestaña y actualizando. Estas dos cuentas dicen,
 * desde cualquier pestaña, que hay algo que mirar.
 */

/**
 * Cuántos estudiantes esperan que el docente los deje pasar.
 *
 * Es una cuenta de trabajo pendiente, no de novedades: baja sola cuando se
 * admite o se rechaza a alguien, y no por haber abierto la pestaña. Un
 * rechazado ya tiene decisión, así que no cuenta.
 */
export function esperandoAdmision(participantes: readonly Participant[]): number {
  return participantes.filter(
    (p) => !p.can_take_exam && !p.submitted_at && p.verification_status !== 'rejected'
  ).length
}

/** Las alertas que el docente todavía no vio en la pestaña de actividad. */
export function alertasSinVer(alertas: readonly Alert[], vistas: ReadonlySet<string>): number {
  return alertas.filter((alerta) => !vistas.has(alerta.id)).length
}

/** Lo que se muestra en el globo: sin cero, y con tope para que no crezca. */
export function textoGlobo(cantidad: number): string | undefined {
  if (cantidad <= 0) return undefined
  return cantidad > 99 ? '99+' : String(cantidad)
}

const clave = (sessionId: string) => `proctoring:alertas-vistas:${sessionId}`

/**
 * Las alertas ya vistas se recuerdan en este navegador, para que recargar la
 * página no vuelva a marcar como nuevas las que el docente ya revisó. Es una
 * comodidad: si el almacenamiento no está disponible, solo se pierde eso.
 */
export function leerVistas(sessionId: string): Set<string> {
  try {
    const crudo = localStorage.getItem(clave(sessionId))
    const lista: unknown = crudo ? JSON.parse(crudo) : []
    return new Set(Array.isArray(lista) ? lista.filter((x): x is string => typeof x === 'string') : [])
  } catch {
    return new Set()
  }
}

export function guardarVistas(sessionId: string, vistas: ReadonlySet<string>): void {
  try {
    localStorage.setItem(clave(sessionId), JSON.stringify([...vistas]))
  } catch {
    // Sin almacenamiento la cuenta vuelve a empezar al recargar; nada más.
  }
}
