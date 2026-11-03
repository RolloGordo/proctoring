import type { Alert, Severity } from './api'

/**
 * La línea de un examen en curso: lo que ya pasó, lo que falta y dónde cayó
 * cada alerta, para dibujarla en el panel del docente.
 *
 * Todo en fracciones de 0 a 1 sobre la duración del examen, que es lo que la
 * vista necesita para colocar cada marca. Una alerta de antes de empezar (la
 * verificación de identidad, por ejemplo) se pega al inicio y una de después
 * del final, al final: se dibujan igual, solo que en el borde.
 */

export type MarcaAlerta = { id: string; en: number; severidad: Severity; motivo: string }

export type LineaExamen = {
  /** Cuánto del examen ha pasado, de 0 a 1. */
  transcurrido: number
  /** Minutos que faltan, redondeados hacia arriba; 0 si ya terminó. */
  faltan: number
  finMs: number
  marcas: MarcaAlerta[]
  /** La más reciente, para enseñarla en palabras junto a la línea. */
  ultima?: Alert
  cuenta: Record<Severity, number>
}

function entre0y1(valor: number): number {
  return Math.min(Math.max(valor, 0), 1)
}

export function lineaExamen(
  inicioIso: string,
  duracionMinutos: number,
  ahora: number,
  alertas: Alert[] = []
): LineaExamen {
  const inicio = new Date(inicioIso).getTime()
  const total = Math.max(duracionMinutos, 1) * 60_000
  const finMs = inicio + total
  const cuenta: Record<Severity, number> = { high: 0, medium: 0, low: 0 }
  const marcas = alertas
    .map((alerta) => {
      cuenta[alerta.severity] += 1
      return {
        id: alerta.id,
        en: entre0y1((new Date(alerta.created_at).getTime() - inicio) / total),
        severidad: alerta.severity,
        motivo: alerta.reason
      }
    })
    .sort((a, b) => a.en - b.en)
  const ultima = [...alertas].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )[0]
  return {
    transcurrido: entre0y1((ahora - inicio) / total),
    faltan: Math.max(0, Math.ceil((finMs - ahora) / 60_000)),
    finMs,
    marcas,
    ultima,
    cuenta
  }
}

/** «hace un momento», «hace 4 min», «hace 2 h»: cuándo pasó algo de hoy. */
export function haceCuanto(ms: number): string {
  const minutos = Math.floor(ms / 60_000)
  if (minutos < 1) return 'hace un momento'
  if (minutos < 60) return `hace ${minutos} min`
  return `hace ${Math.floor(minutos / 60)} h`
}
