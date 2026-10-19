// Tipos globales de la app. Reflejan packages/contracts/event.schema.json:
// si cambia el esquema, cambia aqui en el mismo pull request.
type EventType =
  | 'focus_lost'
  | 'copy_attempt'
  | 'gaze_away'
  | 'face_absent'
  | 'extra_person'
  | 'extra_display'
  | 'suspicious_process'
  | 'screen_share'
  | 'speech_detected'
  | 'prohibited_object'
  | 'identity_check'

interface ProctoringEvent {
  session_id: string
  student_id: string
  question_id: string | null
  event_type: EventType
  /** ISO-8601 en UTC (sufijo Z) */
  started_at: string
  duration_ms: number
  metadata: Record<string, unknown>
  evidence_path: string | null
}

interface AuthSession {
  accessToken: string
  refreshToken: string
}
