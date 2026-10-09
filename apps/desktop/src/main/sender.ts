import { examContext } from './context'

const API_URL = process.env['PROCTORING_API_URL'] ?? 'http://localhost:8000/api/v1/events'
const RETRY_MS = 5_000
const MAX_QUEUE = 500
const MAX_EVIDENCE_RETRIES = 3
const NIL_UUID = '00000000-0000-0000-0000-000000000000'

interface QueuedEvent {
  event: ProctoringEvent
  jpeg?: Buffer
  evidenceRetries: number
}

const queue: QueuedEvent[] = []
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

function buildEvidenceUploadUrl(): string {
  const endpoint = new URL(API_URL)
  if (!endpoint.pathname.endsWith('/events')) {
    throw new Error('PROCTORING_API_URL debe terminar en /api/v1/events')
  }
  endpoint.pathname = endpoint.pathname.replace(/\/events$/, '/evidence/upload-url')
  return endpoint.toString()
}

function resolveStorageUploadUrl(url: string, token: string | null): string {
  let resolved: URL
  try {
    resolved = new URL(url)
  } catch {
    const supabaseUrl = process.env['SUPABASE_URL']
    if (!supabaseUrl) throw new Error('Falta SUPABASE_URL para resolver la URL firmada')
    const storagePath = url.startsWith('/object/') ? `/storage/v1${url}` : url
    resolved = new URL(storagePath, supabaseUrl)
  }
  if (token && !resolved.searchParams.has('token')) {
    resolved.searchParams.set('token', token)
  }
  return resolved.toString()
}

type EvidenceUploadResult =
  | { status: 'uploaded'; path: string }
  | { status: 'retry' }
  | { status: 'blocked' }
  | { status: 'unavailable' }

async function uploadEventEvidence(
  event: ProctoringEvent,
  jpeg: Buffer
): Promise<EvidenceUploadResult> {
  let uploadUrl: string
  try {
    uploadUrl = buildEvidenceUploadUrl()
  } catch (error) {
    console.error('[sender] no se pudo construir la URL para pedir evidencia', error)
    return { status: 'unavailable' }
  }

  const requestUploadUrl = async (): Promise<Response> => {
    return fetch(uploadUrl, {
      method: 'POST',
      headers: {
        ...(authSession ? { Authorization: `Bearer ${authSession.accessToken}` } : {}),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        session_id: event.session_id,
        student_id: event.student_id,
        kind: 'image',
        extension: 'jpg'
      }),
      signal: AbortSignal.timeout(5_000)
    })
  }

  let response: Response
  try {
    response = await requestUploadUrl()
    if (response.status === 401 && (await refreshAccessToken(event))) {
      response = await requestUploadUrl()
    } else if (response.status === 401) {
      return { status: 'blocked' }
    }
  } catch (error) {
    console.error('[sender] no se pudo pedir la URL firmada de evidencia', error)
    return { status: 'retry' }
  }

  if (!response.ok) {
    console.error('[sender] la API rechazo la URL firmada de evidencia', response.status)
    return response.status >= 500 ? { status: 'retry' } : { status: 'unavailable' }
  }

  let upload: unknown
  try {
    upload = await response.json()
  } catch (error) {
    console.error('[sender] respuesta invalida al pedir URL firmada de evidencia', error)
    return { status: 'unavailable' }
  }
  if (
    typeof upload !== 'object' ||
    upload === null ||
    !('path' in upload) ||
    typeof upload.path !== 'string' ||
    !('url' in upload) ||
    typeof upload.url !== 'string' ||
    ('token' in upload && upload.token !== null && typeof upload.token !== 'string')
  ) {
    console.error('[sender] respuesta incompleta al pedir URL firmada de evidencia')
    return { status: 'unavailable' }
  }

  const token = 'token' in upload && typeof upload.token === 'string' ? upload.token : null
  let storageUrl: string
  try {
    storageUrl = resolveStorageUploadUrl(upload.url, token)
  } catch (error) {
    console.error('[sender] URL firmada de Storage invalida', error)
    return { status: 'unavailable' }
  }

  let storageResponse: Response
  try {
    // PUT y no POST: la URL firmada de Supabase Storage responde 400
    // ("headers must have required property 'authorization'") a un POST, porque
    // esa ruta espera la cabecera de un cliente autenticado. Con PUT basta el
    // token de la propia URL. Comprobado contra el Storage real: POST -> 400,
    // PUT -> 200. El fallo era silencioso: la API devolvia 400, el remitente lo
    // tomaba por "no disponible" y mandaba el evento sin captura, asi que los
    // eventos llegaban y ninguna evidencia se guardaba nunca.
    storageResponse = await fetch(storageUrl, {
      method: 'PUT',
      headers: {
        'Content-Type': 'image/jpeg',
        'x-upsert': 'false',
        ...(process.env['SUPABASE_PUBLISHABLE_KEY']
          ? { apikey: process.env['SUPABASE_PUBLISHABLE_KEY'] }
          : {})
      },
      body: new Uint8Array(jpeg),
      signal: AbortSignal.timeout(10_000)
    })
  } catch (error) {
    console.error('[sender] no se pudo subir la captura directamente a Storage', error)
    return { status: 'retry' }
  }

  if (!storageResponse.ok) {
    console.error('[sender] Storage rechazo la captura', storageResponse.status)
    return storageResponse.status >= 500 ? { status: 'retry' } : { status: 'unavailable' }
  }
  return { status: 'uploaded', path: upload.path }
}

async function flush(): Promise<void> {
  if (sending) return
  sending = true
  let retriedAfterRefresh: ProctoringEvent | null = null
  try {
    while (queue.length > 0) {
      const queued = queue[0]
      let event = queued.event

      if (queued.jpeg) {
        const evidence = await uploadEventEvidence(event, queued.jpeg)
        if (evidence.status === 'blocked') return
        if (evidence.status === 'retry') {
          queued.evidenceRetries += 1
          if (queued.evidenceRetries < MAX_EVIDENCE_RETRIES) {
            scheduleRetry()
            return
          }
          console.error(
            '[sender] se agotaron los reintentos de evidencia; se envia el evento sin captura',
            event.event_type
          )
          queued.jpeg = undefined
        } else if (evidence.status === 'unavailable') {
          console.error(
            '[sender] no se pudo adjuntar evidencia; se envia el evento sin captura',
            event.event_type
          )
          queued.jpeg = undefined
        } else {
          event = { ...event, evidence_path: evidence.path }
          queued.event = event
          queued.jpeg = undefined
        }
      }

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
        if (queued.event === unauthorizedEvent) unauthorizedEvent = null
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

export function sendEvent(event: ProctoringEvent, jpeg?: Buffer): void {
  if (!canSend()) return
  if (queue.length >= MAX_QUEUE) {
    console.error('[sender] cola llena; se descarta el evento mas antiguo')
    queue.shift()
  }
  queue.push({ event, jpeg, evidenceRetries: 0 })
  void flush()
}
