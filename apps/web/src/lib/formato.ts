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
