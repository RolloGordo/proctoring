/**
 * Cliente de la API de proctoring.
 *
 * Los tipos reflejan `packages/contracts/event.schema.json` y los schemas de
 * `services/api`. Si la API cambia, esto tiene que cambiar en el mismo pull
 * request.
 */

const BASE = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export type EventType =
  | 'focus_lost'
  | 'gaze_away'
  | 'face_absent'
  | 'extra_person'
  | 'extra_display'
  | 'suspicious_process'
  | 'screen_share'
  | 'speech_detected'
  | 'identity_check'

export type Severity = 'low' | 'medium' | 'high'
export type SessionStatus = 'draft' | 'scheduled' | 'in_progress' | 'finished'
export type SupervisionPreset = 'basic' | 'standard' | 'strict' | 'custom'

export interface ExamSessionSummary {
  id: string
  title: string
  starts_at: string
  duration_minutes: number
  access_code: string
  preset: SupervisionPreset
  status: SessionStatus
}

export interface ExamSession extends ExamSessionSummary {
  teacher_id: string
  course_id: string | null
  description: string | null
  ends_at: string
  entry_tolerance_minutes: number
  max_attempts: number
  shuffle_questions: boolean
  shuffle_options: boolean
  allow_back_navigation: boolean
  modules: Record<string, Record<string, unknown>>
}

export interface ProctoringEvent {
  id: string
  session_id: string
  student_id: string
  question_id: string | null
  event_type: EventType
  started_at: string
  duration_ms: number
  metadata: Record<string, unknown>
  evidence_path: string | null
  severity: Severity
}

export interface Alert {
  id: string
  event_id: string
  session_id: string
  student_id: string
  severity: Severity
  reason: string
  created_at: string
}

/** Lo que el estudiante recibe al teclear su codigo de acceso. */
export interface JoinedExam {
  session_id: string
  title: string
  description: string | null
  starts_at: string
  ends_at: string
  duration_minutes: number
  entry_tolerance_minutes: number
  can_enter_now: boolean
  modules: Record<string, Record<string, unknown>>
}

export interface NewExamSession {
  title: string
  starts_at: string
  duration_minutes: number
  description?: string | null
  entry_tolerance_minutes?: number
  preset?: SupervisionPreset
}

/** Error de la API con su código, para poder distinguir 401 de 403 de 400. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit, token?: string): Promise<T> {
  const headers = new Headers(init?.headers)
  headers.set('Content-Type', 'application/json')
  // La API acepta peticiones sin token solo con AUTH_ENABLED=false, que es el
  // modo de desarrollo local. En cuanto se active, sin token responde 401.
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${BASE}${path}`, { ...init, headers })

  if (!response.ok) {
    throw new ApiError(response.status, await describeError(response))
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** Saca el mensaje del cuerpo, que la API devuelve en `detail`. */
async function describeError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
    // 422 de Pydantic: `detail` es una lista de errores por campo.
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((item) => {
          const e = item as { loc?: unknown[]; msg?: string }
          const campo = Array.isArray(e.loc) ? e.loc.slice(1).join('.') : ''
          return campo ? `${campo}: ${e.msg}` : (e.msg ?? '')
        })
        .filter(Boolean)
        .join(' · ')
    }
  } catch {
    // Cuerpo vacío o no JSON: se usa el texto del estado.
  }
  return `${response.status} ${response.statusText}`
}

export const api = {
  health: (): Promise<{ status: string; env: string; version: string; auth: string }> =>
    request('/health'),

  listSessions: (token?: string): Promise<ExamSessionSummary[]> =>
    request('/api/v1/sessions', undefined, token),

  getSession: (id: string, token?: string): Promise<ExamSession> =>
    request(`/api/v1/sessions/${id}`, undefined, token),

  createSession: (data: NewExamSession, token?: string): Promise<ExamSession> =>
    request('/api/v1/sessions', { method: 'POST', body: JSON.stringify(data) }, token),

  joinExam: (accessCode: string, token?: string): Promise<JoinedExam> =>
    request(
      '/api/v1/sessions/join',
      { method: 'POST', body: JSON.stringify({ access_code: accessCode }) },
      token
    ),

  listEvents: (sessionId: string, token?: string): Promise<ProctoringEvent[]> =>
    request(`/api/v1/sessions/${sessionId}/events`, undefined, token),

  listAlerts: (sessionId: string, token?: string): Promise<Alert[]> =>
    request(`/api/v1/sessions/${sessionId}/alerts`, undefined, token)
}
