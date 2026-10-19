/** TA-083: visible, auditable health errors. Not misconduct events. */
import type { SupabaseClient } from '@supabase/supabase-js'

export type DiagnosticCode =
  | 'camera_interrupted'
  | 'camera_no_image'
  | 'camera_recovered'
  | 'vision_module_failed'
  | 'vision_module_recovered'
  /** Cuanto observo un detector durante el examen. No es una incidencia. */
  | 'vision_module_summary'
  /** Se oyo habla pero el fragmento no llego a Storage: no hay senal que emitir. */
  | 'audio_segment_lost'
  /** La señal se guardo, pero no se pudo guardar su captura. */
  | 'image_evidence_lost'
  /** La API rechazo la senal y se descarto: queda el motivo, no la senal. */
  | 'signal_rejected'
  /** La cola lleva varios intentos sin avanzar: ese rato no se registro nada. */
  | 'signal_queue_stuck'

export interface DiagnosticEntry {
  session_id: string
  student_id: string
  code: DiagnosticCode
  module?: string
  details?: Record<string, string | number | boolean>
}

/** Records one transition, never a photograph. A failure is surfaced, not thrown into the exam. */
export async function recordDiagnostic(
  client: Pick<SupabaseClient, 'from'> | null,
  entry: DiagnosticEntry
): Promise<boolean> {
  if (!client) return false
  try {
    const { error } = await client.from('supervision_diagnostics').insert({
      session_id: entry.session_id,
      student_id: entry.student_id,
      code: entry.code,
      module: entry.module ?? null,
      details: entry.details ?? {}
    })
    if (error) {
      console.error('[supervision] could not persist diagnostic', entry.code, error.message)
      return false
    }
    return true
  } catch (error) {
    console.error('[supervision] diagnostic request failed', entry.code, error)
    return false
  }
}
