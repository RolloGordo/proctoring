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
  | 'network_disconnected'
  | 'network_reconnected'

export interface DiagnosticEntry {
  session_id: string
  student_id: string
  code: DiagnosticCode
  occurred_at?: string
  module?: string
  details?: Record<string, string | number | boolean>
}

/** Queue availability transitions across offline periods until Supabase returns. */
export async function recordNetworkDiagnostic(
  client: Pick<SupabaseClient, 'from'> | null,
  entry: DiagnosticEntry
): Promise<void> {
  if (entry.code !== 'network_disconnected' && entry.code !== 'network_reconnected') return
  const queueKey = `proctoring.network-diagnostics:${entry.student_id}`
  let queue: DiagnosticEntry[] = []
  try {
    queue = JSON.parse(localStorage.getItem(queueKey) ?? '[]') as DiagnosticEntry[]
  } catch {
    localStorage.removeItem(queueKey)
  }
  queue.push(entry)
  try {
    localStorage.setItem(queueKey, JSON.stringify(queue))
  } catch {
    console.error('[supervision] could not queue network diagnostic')
    return
  }
  if (!client) return
  const remaining: DiagnosticEntry[] = []
  for (const diagnostic of queue) {
    if (!(await recordDiagnostic(client, diagnostic))) remaining.push(diagnostic)
  }
  try {
    if (remaining.length) localStorage.setItem(queueKey, JSON.stringify(remaining))
    else localStorage.removeItem(queueKey)
  } catch (error) {
    console.error('[supervision] could not update network diagnostic queue', error)
  }
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
      ...(entry.occurred_at ? { created_at: entry.occurred_at } : {}),
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
