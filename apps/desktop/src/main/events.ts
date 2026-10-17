import type { ExamContext } from './context'

export interface DisplayInfo {
  id: number
  bounds: { width: number; height: number }
  scaleFactor: number
}

/**
 * focus_lost: UN solo evento al cerrarse la condicion (cuando la ventana
 * recupera el foco), con su duracion. Si la app se cierra estando fuera,
 * se emite con returned: false.
 */
export function buildFocusLostEvent(
  ctx: ExamContext,
  blurStartedAtMs: number,
  endedAtMs: number,
  returned: boolean
): ProctoringEvent {
  return {
    session_id: ctx.session_id,
    student_id: ctx.student_id,
    question_id: null,
    event_type: 'focus_lost',
    started_at: new Date(blurStartedAtMs).toISOString(),
    duration_ms: Math.max(0, Math.round(endedAtMs - blurStartedAtMs)),
    metadata: { source: 'electron_main', trigger: 'window_blur', returned },
    evidence_path: null
  }
}

/** extra_display: evento instantaneo (duration_ms = 0). */
export function buildExtraDisplayEvent(
  ctx: ExamContext,
  displays: DisplayInfo[],
  detectedOn: string,
  nowMs: number
): ProctoringEvent {
  return {
    session_id: ctx.session_id,
    student_id: ctx.student_id,
    question_id: null,
    event_type: 'extra_display',
    started_at: new Date(nowMs).toISOString(),
    duration_ms: 0,
    metadata: {
      source: 'electron_screen',
      display_count: displays.length,
      displays: displays.map((d) => ({
        id: d.id,
        bounds: { width: d.bounds.width, height: d.bounds.height },
        scale_factor: d.scaleFactor
      })),
      detected_on: detectedOn
    },
    evidence_path: null
  }
}

/** suspicious_process: evento instantaneo (duration_ms = 0). Solo viaja el proceso detectado, nunca la lista completa. */
export function buildSuspiciousProcessEvent(
  ctx: ExamContext,
  match: { processName: string; category: string; pid: number },
  detectedOn: string,
  nowMs: number
): ProctoringEvent {
  return {
    session_id: ctx.session_id,
    student_id: ctx.student_id,
    question_id: null,
    event_type: 'suspicious_process',
    started_at: new Date(nowMs).toISOString(),
    duration_ms: 0,
    metadata: {
      source: 'electron_processes',
      process_name: match.processName,
      category: match.category,
      pid: match.pid,
      detected_on: detectedOn
    },
    evidence_path: null
  }
}
