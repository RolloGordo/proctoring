/** Formato de fechas, duraciones y nombres para la interfaz, que va en español. */

import type { EventType, SessionStatus, SupervisionPreset } from './api'

const LARGA = new Intl.DateTimeFormat('es-PE', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit'
})

const HORA = new Intl.DateTimeFormat('es-PE', {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit'
})

export function fechaLarga(iso: string): string {
  return LARGA.format(new Date(iso))
}

export function soloHora(iso: string): string {
  return HORA.format(new Date(iso))
}

export function duracion(ms: number): string {
  if (ms < 1000) return `${ms} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`
  const minutos = Math.floor(ms / 60_000)
  const segundos = Math.round((ms % 60_000) / 1000)
  return `${minutos} min ${segundos} s`
}

const PRESETS: Record<SupervisionPreset, string> = {
  basic: 'Básica',
  standard: 'Estándar',
  strict: 'Estricta',
  custom: 'Personalizada'
}

export function nombrePreset(preset: SupervisionPreset): string {
  return PRESETS[preset] ?? preset
}

/** Dónde está un examen respecto a la hora, que es lo que el usuario quiere saber. */
export type EstadoExamen = 'programado' | 'en_curso' | 'terminado'

/**
 * El estado real de un examen, calculado con la hora.
 *
 * No se usa el campo `status` que guarda la API: se escribe como "programado" al
 * crear la sesión y nada lo actualiza, así que un examen de ayer seguía
 * diciendo "Programado". La hora es la verdad; el campo guardado es solo un
 * borrador de intención.
 */
export function estadoExamen(
  inicioIso: string,
  duracionMinutos: number,
  ahora: number = Date.now()
): EstadoExamen {
  const inicio = new Date(inicioIso).getTime()
  const fin = inicio + duracionMinutos * 60_000
  if (ahora < inicio) return 'programado'
  return ahora <= fin ? 'en_curso' : 'terminado'
}

const ESTADOS_EXAMEN: Record<EstadoExamen, string> = {
  programado: 'Programado',
  en_curso: 'En curso',
  terminado: 'Terminado'
}

export function nombreEstadoExamen(estado: EstadoExamen): string {
  return ESTADOS_EXAMEN[estado]
}

/** "en 5 minutos", "en 3 horas", "en 2 días": cuánto falta para algo. */
export function cuandoEmpieza(ms: number): string {
  const minutos = Math.max(1, Math.ceil(ms / 60_000))
  if (minutos < 60) return `en ${minutos} minuto${minutos === 1 ? '' : 's'}`
  const horas = Math.floor(minutos / 60)
  if (horas < 24) return `en ${horas} hora${horas === 1 ? '' : 's'}`
  const dias = Math.floor(horas / 24)
  return `en ${dias} día${dias === 1 ? '' : 's'}`
}

const ESTADOS: Record<SessionStatus, string> = {
  draft: 'Borrador',
  scheduled: 'Programado',
  in_progress: 'En curso',
  finished: 'Terminado'
}

export function nombreEstado(estado: SessionStatus): string {
  return ESTADOS[estado] ?? estado
}

/**
 * Nombre legible de cada señal.
 *
 * Describe lo observado, nunca lo interpreta: el sistema es un auditor, no un
 * juez. Dice "salió de la ventana", no "hizo trampa".
 */
const EVENTOS: Record<EventType, string> = {
  focus_lost: 'Salió de la ventana',
  gaze_away: 'Mirada fuera de pantalla',
  face_absent: 'Rostro no detectado',
  extra_person: 'Otra persona en cámara',
  extra_display: 'Monitor adicional',
  suspicious_process: 'Aplicación sospechosa',
  screen_share: 'Pantalla compartida',
  speech_detected: 'Voz detectada',
  identity_check: 'Verificación de identidad'
}

export function nombreEvento(tipo: EventType): string {
  return EVENTOS[tipo] ?? tipo
}
