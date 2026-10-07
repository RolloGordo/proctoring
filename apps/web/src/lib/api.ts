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
export type SessionStatus = 'draft' | 'scheduled' | 'in_progress' | 'finished' | 'cancelled'
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
  question_pool_size: number | null
  /** Sobre cuánto se califica. 20 por defecto: la escala peruana. */
  max_score: string
  /** Cuándo lo canceló el docente. `null` mientras siga en pie. */
  cancelled_at: string | null
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

/** Una señal a reportar. `student_id` tiene que ser el del token. */
export interface NewEvent {
  session_id: string
  student_id: string
  question_id?: string | null
  event_type: EventType
  /** ISO-8601 en UTC. */
  started_at: string
  duration_ms?: number
  metadata?: Record<string, unknown>
  evidence_path?: string | null
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

export type QuestionType = 'multiple_choice' | 'true_false' | 'numeric' | 'fill_blank' | 'essay'

export type VerificationStatus =
  'pending' | 'verified' | 'failed' | 'manually_approved' | 'rejected'

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
  /** Puntos ganados en lo que se corrige solo. `null` si aún no hay nota. */
  score: number | null
  /** Quién es. Solo lo trae la sala de espera del docente. */
  student_name?: string | null
  student_email?: string | null
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

/** Un examen del panel del estudiante: a cual entró y en qué punto está. */
export interface MyExam {
  session_id: string
  title: string
  description: string | null
  starts_at: string
  ends_at: string
  duration_minutes: number
  entry_tolerance_minutes: number
  can_enter_now: boolean
  modules: Record<string, Record<string, unknown>>
  verification_status: VerificationStatus
  can_take_exam: boolean
  consent_at: string | null
  submitted_at: string | null
  /** Puntos ganados en lo que se corrige solo. `null` si aún no hay nota. */
  score: number | null
  /** Si el docente retiró el examen. */
  cancelled: boolean
  /** Sobre cuánto se califica, para mostrar «13.5 de 20». */
  max_score: number | null
  /** Hay desarrollos que el docente todavía no califica: la nota es parcial. */
  pending_manual_review: boolean
}

export type DecisionType = 'confirmed' | 'dismissed' | 'retake'
export type RiskLevel = 'low' | 'medium' | 'high'

/** Lo que un tipo de señal aporta al riesgo. */
export interface SignalRisk {
  event_type: EventType
  count: number
  total_duration_ms: number
  points: number
  max_severity: Severity
}

/** Cuánta atención merece un caso y por qué. Un auditor: no es un veredicto. */
export interface Risk {
  score: number
  level: RiskLevel
  signals: SignalRisk[]
}

/** Una decisión del docente. Es evidencia: no se edita, se agrega otra. */
export interface Decision {
  id: string
  session_id: string
  student_id: string
  teacher_id: string
  decision: DecisionType
  justification: string
  decided_at: string
}

/** Todo lo que el docente necesita para decidir sobre un estudiante. */
export interface CaseFile {
  participant: Participant
  events: ProctoringEvent[]
  alerts: Alert[]
  /** De la más reciente a la más antigua: la primera es la vigente. */
  decisions: Decision[]
  risk: Risk
}

/** Un curso del docente. */
export interface Course {
  id: string
  name: string
  section: string | null
  created_at: string
  student_count: number
}

/** Un estudiante matriculado en un curso. */
export interface CourseMember {
  student_id: string
  /** `null` si la persona ya no tiene perfil: sigue matriculada, y se muestra. */
  email: string | null
  full_name: string | null
  enrolled_at: string
}

/** Un examen de una clase: cuándo es, sin el código para rendirlo. */
export interface MyCourseExam {
  session_id: string
  title: string
  starts_at: string
  ends_at: string
  duration_minutes: number
}

/** Una clase del estudiante, con los exámenes que le tocan. */
export interface MyCourse {
  id: string
  name: string
  section: string | null
  exams: MyCourseExam[]
}

export interface NewExamSession {
  title: string
  starts_at: string
  duration_minutes: number
  description?: string | null
  /** Curso al que pertenece. Tiene que ser del propio docente. */
  course_id?: string | null
  entry_tolerance_minutes?: number
  preset?: SupervisionPreset
  /**
   * Cuántas preguntas recibe cada estudiante de las que hay en los bancos
   * atados. `null` es "todas". Sin bancos no tiene efecto.
   */
  question_pool_size?: number | null
  /** Sobre cuánto se califica. 20 por defecto: es la escala peruana. */
  max_score?: string | number | null
}

/**
 * Lo que se quiere cambiar de un examen. Lo que no se envía no se toca.
 *
 * Para **vaciar** un campo opcional están los `clear_*`: `null` ya significa
 * "no lo cambies", así que con un solo mecanismo no habría forma de quitarle la
 * descripción a un examen que ya la tiene.
 */
export interface ExamSessionChanges {
  title?: string
  starts_at?: string
  duration_minutes?: number
  entry_tolerance_minutes?: number
  description?: string
  course_id?: string
  preset?: SupervisionPreset
  max_score?: string | number
  question_pool_size?: number
  shuffle_questions?: boolean
  shuffle_options?: boolean
  allow_back_navigation?: boolean
  clear_description?: boolean
  clear_course?: boolean
  clear_pool_size?: boolean
}

/** Lo que se quiere cambiar de una pregunta. Las opciones van enteras o no van. */
export interface QuestionChanges {
  statement?: string
  points?: string
  options?: Array<{ option_text: string; is_correct: boolean }>
  correct_numeric_answer?: string
  numeric_tolerance?: string
  correct_text_answer?: string
}

/** Un banco de preguntas reutilizable, con cuántas tiene. */
export interface QuestionBank {
  id: string
  name: string
  course_id: string | null
  description: string | null
  created_at: string
  question_count: number
}

export interface NewQuestionBank {
  name: string
  course_id?: string | null
  description?: string | null
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

  updateSession: (
    id: string,
    changes: ExamSessionChanges,
    token?: string
  ): Promise<ExamSession> =>
    request(`/api/v1/sessions/${id}`, { method: 'PATCH', body: JSON.stringify(changes) }, token),

  cancelSession: (id: string, token?: string): Promise<ExamSession> =>
    request(`/api/v1/sessions/${id}/cancel`, { method: 'POST' }, token),

  deleteSession: (id: string, token?: string): Promise<void> =>
    request(`/api/v1/sessions/${id}`, { method: 'DELETE' }, token),

  updateQuestion: (id: string, changes: QuestionChanges, token?: string): Promise<Question> =>
    request(`/api/v1/questions/${id}`, { method: 'PATCH', body: JSON.stringify(changes) }, token),

  deleteQuestion: (id: string, token?: string): Promise<void> =>
    request(`/api/v1/questions/${id}`, { method: 'DELETE' }, token),

  joinExam: (accessCode: string, token?: string): Promise<JoinedExam> =>
    request(
      '/api/v1/sessions/join',
      { method: 'POST', body: JSON.stringify({ access_code: accessCode }) },
      token
    ),

  reviewCase: (sessionId: string, studentId: string, token?: string): Promise<CaseFile> =>
    request(`/api/v1/sessions/${sessionId}/students/${studentId}/case`, undefined, token),

  decide: (
    sessionId: string,
    studentId: string,
    decision: DecisionType,
    justification: string,
    token?: string
  ): Promise<Decision> =>
    request(
      `/api/v1/sessions/${sessionId}/students/${studentId}/decision`,
      { method: 'POST', body: JSON.stringify({ decision, justification }) },
      token
    ),

  listDecisions: (sessionId: string, token?: string): Promise<Decision[]> =>
    request(`/api/v1/sessions/${sessionId}/decisions`, undefined, token),

  myExams: (token?: string): Promise<MyExam[]> => request('/api/v1/me/exams', undefined, token),

  myCourses: (token?: string): Promise<MyCourse[]> =>
    request('/api/v1/me/courses', undefined, token),

  listCourses: (token?: string): Promise<Course[]> => request('/api/v1/courses', undefined, token),

  // --- Bancos de preguntas ---

  listBanks: (token?: string): Promise<QuestionBank[]> =>
    request('/api/v1/question-banks', undefined, token),

  createBank: (data: NewQuestionBank, token?: string): Promise<QuestionBank> =>
    request('/api/v1/question-banks', { method: 'POST', body: JSON.stringify(data) }, token),

  listBankQuestions: (bankId: string, token?: string): Promise<Question[]> =>
    request(`/api/v1/question-banks/${bankId}/questions`, undefined, token),

  addBankQuestions: (
    bankId: string,
    questions: NewQuestion[],
    token?: string
  ): Promise<Question[]> =>
    request(
      `/api/v1/question-banks/${bankId}/questions`,
      { method: 'POST', body: JSON.stringify({ questions }) },
      token
    ),

  listSessionBanks: (sessionId: string, token?: string): Promise<QuestionBank[]> =>
    request(`/api/v1/sessions/${sessionId}/banks`, undefined, token),

  attachBank: (
    sessionId: string,
    bankId: string,
    token?: string
  ): Promise<{ bank_id: string; already_attached: boolean }> =>
    request(
      `/api/v1/sessions/${sessionId}/banks`,
      { method: 'POST', body: JSON.stringify({ bank_id: bankId }) },
      token
    ),

  detachBank: (sessionId: string, bankId: string, token?: string): Promise<void> =>
    request(`/api/v1/sessions/${sessionId}/banks/${bankId}`, { method: 'DELETE' }, token),

  getCourse: (id: string, token?: string): Promise<Course> =>
    request(`/api/v1/courses/${id}`, undefined, token),

  createCourse: (name: string, section: string | null, token?: string): Promise<Course> =>
    request('/api/v1/courses', { method: 'POST', body: JSON.stringify({ name, section }) }, token),

  listCourseMembers: (id: string, token?: string): Promise<CourseMember[]> =>
    request(`/api/v1/courses/${id}/students`, undefined, token),

  enrollStudent: (
    id: string,
    email: string,
    token?: string
  ): Promise<{ student: CourseMember; already_enrolled: boolean }> =>
    request(
      `/api/v1/courses/${id}/students`,
      { method: 'POST', body: JSON.stringify({ email }) },
      token
    ),

  listQuestions: (sessionId: string, token?: string): Promise<Question[]> =>
    request(`/api/v1/sessions/${sessionId}/questions`, undefined, token),

  addQuestions: (
    sessionId: string,
    questions: NewQuestion[],
    token?: string
  ): Promise<Question[]> =>
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

  registerEvent: (evento: NewEvent, token?: string): Promise<{ id: string; severity: Severity }> =>
    request('/api/v1/events', { method: 'POST', body: JSON.stringify(evento) }, token),

  listEvents: (sessionId: string, token?: string): Promise<ProctoringEvent[]> =>
    request(`/api/v1/sessions/${sessionId}/events`, undefined, token),

  listAlerts: (sessionId: string, token?: string): Promise<Alert[]> =>
    request(`/api/v1/sessions/${sessionId}/alerts`, undefined, token)
}

/**
 * Un examen del panel, con la forma que espera la sala de espera.
 *
 * Desde el panel el estudiante vuelve a la sala sin haber tecleado el código, y
 * la sala se pensó para lo que devuelve `joinExam`. Son los mismos datos.
 */
export function comoExamenUnido(examen: MyExam): JoinedExam {
  return {
    session_id: examen.session_id,
    title: examen.title,
    description: examen.description,
    starts_at: examen.starts_at,
    ends_at: examen.ends_at,
    duration_minutes: examen.duration_minutes,
    entry_tolerance_minutes: examen.entry_tolerance_minutes,
    can_enter_now: examen.can_enter_now,
    modules: examen.modules
  }
}
