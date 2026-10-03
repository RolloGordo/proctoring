import { examContext } from './context'

const API_URL = process.env['PROCTORING_API_URL'] ?? 'http://localhost:8000/api/v1/events'
const RETRY_MS = 5_000
const MAX_QUEUE = 500
const NIL_UUID = '00000000-0000-0000-0000-000000000000'

const queue: ProctoringEvent[] = []
let sending = false
let timer: NodeJS.Timeout | undefined
let unauthorizedEvent: ProctoringEvent | null = null
let authSession: AuthSession | null = null

// Sin IDs reales la API rechazaria el evento: solo se muestra en el panel local.
function canSend(): boolean {
  return examContext.session_id !== NIL_UUID && examContext.student_id !== NIL_UUID
}

function scheduleRetry(): void {
  if (timer) return
  timer = setTimeout(() => {
    timer = undefined
    void flush()
  }, RETRY_MS)
}

async function refreshAccessToken(event: ProctoringEvent): Promise<boolean> {
  const supabaseUrl = process.env['SUPABASE_URL']
  const publishableKey = process.env['SUPABASE_PUBLISHABLE_KEY']
  if (!authSession || !supabaseUrl || !publishableKey) {
    if (unauthorizedEvent !== event) {
      unauthorizedEvent = event
      console.error(
        '[sender] no se puede renovar la sesion: faltan los tokens de Supabase o su configuracion',
        event.event_type
      )
    }
    return false
  }

  let response: Response
  try {
    response = await fetch(
      `${supabaseUrl.replace(/\/$/, '')}/auth/v1/token?grant_type=refresh_token`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          apikey: publishableKey
        },
        body: JSON.stringify({ refresh_token: authSession.refreshToken }),
        signal: AbortSignal.timeout(5_000)
      }
    )
  } catch (error) {
    console.error('[sender] fallo la renovacion de la sesion de Supabase', error)
    scheduleRetry()
    return false
  }

  if (!response.ok) {
    console.error('[sender] Supabase rechazo la renovacion de la sesion', response.status)
    if (response.status >= 500) scheduleRetry()
    else unauthorizedEvent = event
    return false
  }

  let refreshed: unknown
  try {
    refreshed = await response.json()
  } catch (error) {
    console.error('[sender] respuesta invalida al renovar la sesion de Supabase', error)
    return false
  }

  if (
    typeof refreshed !== 'object' ||
    refreshed === null ||
    !('access_token' in refreshed) ||
    typeof refreshed.access_token !== 'string' ||
    !('refresh_token' in refreshed) ||
    typeof refreshed.refresh_token !== 'string'
  ) {
    console.error('[sender] respuesta incompleta al renovar la sesion de Supabase')
    return false
  }

  authSession = {
    accessToken: refreshed.access_token,
    refreshToken: refreshed.refresh_token
  }
  return true
}

async function flush(): Promise<void> {
  if (sending) return
  sending = true
  let retriedAfterRefresh: ProctoringEvent | null = null
  try {
    while (queue.length > 0) {
      const event = queue[0]
      let response: Response
      try {
        response = await fetch(API_URL, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(authSession ? { Authorization: `Bearer ${authSession.accessToken}` } : {})
          },
          body: JSON.stringify(event),
          signal: AbortSignal.timeout(5_000)
        })
      } catch (error) {
        // Sin red o API caida: se conserva el evento y se reintenta
        console.error('[sender] no se pudo enviar el evento; se conserva en cola', error)
        scheduleRetry()
        return
      }

      if (response.ok) {
        if (queue[0] === unauthorizedEvent) unauthorizedEvent = null
        queue.shift()
      } else if (response.status === 401) {
        if (retriedAfterRefresh === event) {
          unauthorizedEvent = event
          console.error(
            '[sender] la API sigue rechazando el evento tras renovar la sesion; se conserva en cola',
            event.event_type
          )
          return
        }
        if (await refreshAccessToken(event)) {
          retriedAfterRefresh = event
          continue
        }
        return
      } else if (response.status >= 500) {
        scheduleRetry()
        return
      } else {
        // 4xx: reintentar no sirve (validacion, permisos). Se descarta y se avisa.
        console.error('[sender] la API rechazo el evento', response.status, event.event_type)
        queue.shift()
      }
    }
  } finally {
    sending = false
  }
}

export function setAuthSession(session: AuthSession | null): void {
  authSession = session
  unauthorizedEvent = null
  if (timer) {
    clearTimeout(timer)
    timer = undefined
  }
  void flush()
}

export function sendEvent(event: ProctoringEvent): void {
  if (!canSend()) return
  if (queue.length >= MAX_QUEUE) {
    console.error('[sender] cola llena; se descarta el evento mas antiguo')
    queue.shift()
  }
  queue.push(event)
  void flush()
}
