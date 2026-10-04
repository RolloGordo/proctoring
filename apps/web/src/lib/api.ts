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

export type QuestionType =
  | 'multiple_choice'
  | 'true_false'
  | 'numeric'
  | 'fill_blank'
  | 'essay'

export type VerificationStatus =
  | 'pending'
  | 'verified'
  | 'failed'
  | 'manually_approved'
  | 'rejected'

/** Opcion como la ve el estudiante: sin `is_correct`. */
export interface ExamOption {
  id: string
  position: number
  option_text: string
}

/** Pregunta como la ve el estudiante: sin respuestas correctas. */
export interface ExamQuestion {
  id: string
  position: number
  question_type: QuestionType
  statement: string
  points: string
  options: ExamOption[]
}

/** Opcion con la marca de correcta. Solo llega al docente. */
export interface QuestionOption extends ExamOption {
  is_correct: boolean
}

/** Pregunta con su respuesta correcta. Solo llega al docente. */
export interface Question extends Omit<ExamQuestion, 'options'> {
  session_id: string
  options: QuestionOption[]
  correct_numeric_answer: string | null
  numeric_tolerance: string | null
  correct_text_answer: string | null
}

export interface NewQuestion {
  question_type: QuestionType
  statement: string
  points?: string
  options?: Array<{ option_text: string; is_correct: boolean }>
  correct_numeric_answer?: string | null
  correct_text_answer?: string | null
}

export interface Participant {
  id: string
  session_id: string
  student_id: string
  attempt: number
  verification_status: VerificationStatus
  consent_at: string | null
  verified_at: string | null
  started_at: string | null
  submitted_at: string | null
  can_take_exam: boolean
}

/** Una respuesta guardada. No lleva si acertó: eso no lo sabe el estudiante. */
export interface Answer {
  question_id: string
  selected_option_id: string | null
  text_answer: string | null
  numeric_answer: string | null
  answered_at: string
}

/** Una respuesta a guardar. Qué campo se usa depende del tipo de pregunta. */
export interface NewAnswer {
  question_id: string
  selected_option_id?: string | null
  text_answer?: string | null
  numeric_answer?: string | null
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

  listQuestions: (sessionId: string, token?: string): Promise<Question[]> =>
    request(`/api/v1/sessions/${sessionId}/questions`, undefined, token),

  addQuestions: (sessionId: string, questions: NewQuestion[], token?: string): Promise<Question[]> =>
    request(
      `/api/v1/sessions/${sessionId}/questions`,
      { method: 'POST', body: JSON.stringify({ questions }) },
      token
    ),

  examQuestions: (sessionId: string, token?: string): Promise<ExamQuestion[]> =>
    request(`/api/v1/exam/${sessionId}/questions`, undefined, token),

  enroll: (sessionId: string, acceptsSupervision: boolean, token?: string): Promise<Participant> =>
    request(
      `/api/v1/exam/${sessionId}/enroll`,
      { method: 'POST', body: JSON.stringify({ accepts_supervision: acceptsSupervision }) },
      token
    ),

  myEnrollment: (sessionId: string, token?: string): Promise<Participant> =>
    request(`/api/v1/exam/${sessionId}/me`, undefined, token),

  saveAnswers: (sessionId: string, answers: NewAnswer[], token?: string): Promise<Answer[]> =>
    request(
      `/api/v1/exam/${sessionId}/answers`,
      { method: 'PUT', body: JSON.stringify({ answers }) },
      token
    ),

  myAnswers: (sessionId: string, token?: string): Promise<Answer[]> =>
    request(`/api/v1/exam/${sessionId}/answers`, undefined, token),

  submitExam: (sessionId: string, token?: string): Promise<Participant> =>
    request(`/api/v1/exam/${sessionId}/submit`, { method: 'POST' }, token),

  listParticipants: (sessionId: string, token?: string): Promise<Participant[]> =>
    request(`/api/v1/sessions/${sessionId}/participants`, undefined, token),

  reviewIdentity: (
    sessionId: string,
    studentId: string,
    approve: boolean,
    token?: string
  ): Promise<Participant> =>
    request(
      `/api/v1/sessions/${sessionId}/participants/${studentId}/identity`,
      { method: 'POST', body: JSON.stringify({ approve }) },
      token
    ),

  listEvents: (sessionId: string, token?: string): Promise<ProctoringEvent[]> =>
    request(`/api/v1/sessions/${sessionId}/events`, undefined, token),

  listAlerts: (sessionId: string, token?: string): Promise<Alert[]> =>
    request(`/api/v1/sessions/${sessionId}/alerts`, undefined, token)
}
