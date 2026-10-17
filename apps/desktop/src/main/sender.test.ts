import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
  vi.resetModules()
})

describe('event sender authentication', () => {
  it('refreshes the Supabase session after a 401 and retries the event', async () => {
    vi.stubEnv('PROCTORING_SESSION_ID', '3f1a7c20-9b4e-4d2a-8f6c-1e2d3a4b5c60')
    vi.stubEnv('PROCTORING_STUDENT_ID', '7b2e4d10-5c6f-4a8b-9d0e-2f3a4b5c6d71')
    vi.stubEnv('SUPABASE_URL', 'https://example.supabase.co')
    vi.stubEnv('SUPABASE_PUBLISHABLE_KEY', 'public-test-key')

    const requests: Array<{ url: string; authorization: string | null }> = []
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input)
      const authorization = new Headers(init?.headers).get('Authorization')
      requests.push({ url, authorization })

      if (url.includes('/auth/v1/token?grant_type=refresh_token')) {
        return Response.json({ access_token: 'fresh-token', refresh_token: 'rotated-token' })
      }
      if (authorization === 'Bearer fresh-token') {
        return new Response('{}', { status: 201 })
      }
      return new Response(null, { status: 401 })
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.resetModules()

    const { sendEvent, setAuthSession } = await import('./sender')
    setAuthSession({ accessToken: 'expired-token', refreshToken: 'refresh-token' })
    sendEvent({
      session_id: '3f1a7c20-9b4e-4d2a-8f6c-1e2d3a4b5c60',
      student_id: '7b2e4d10-5c6f-4a8b-9d0e-2f3a4b5c6d71',
      question_id: null,
      event_type: 'focus_lost',
      started_at: '2026-10-03T14:21:05.120Z',
      duration_ms: 1000,
      metadata: {},
      evidence_path: null
    })

    await vi.waitFor(() => {
      expect(requests.filter((request) => request.url.endsWith('/api/v1/events'))).toHaveLength(2)
    })
    expect(requests[0]?.authorization).toBe('Bearer expired-token')
    expect(requests[1]?.url).toContain('/auth/v1/token?grant_type=refresh_token')
    expect(requests[2]?.authorization).toBe('Bearer fresh-token')
  })

  it('uploads evidence directly to Storage and returns its path', async () => {
    vi.stubEnv('PROCTORING_SESSION_ID', '3f1a7c20-9b4e-4d2a-8f6c-1e2d3a4b5c60')
    vi.stubEnv('PROCTORING_STUDENT_ID', '7b2e4d10-5c6f-4a8b-9d0e-2f3a4b5c6d71')
    vi.stubEnv('SUPABASE_URL', 'https://example.supabase.co')
    vi.stubEnv('SUPABASE_PUBLISHABLE_KEY', 'public-test-key')

    const requests: Array<{ url: string; method: string | undefined; body?: string }> = []
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input)
      requests.push({
        url,
        method: init?.method,
        body: typeof init?.body === 'string' ? init.body : undefined
      })
      if (url.endsWith('/api/v1/evidence/upload-url')) {
        return Response.json(
          {
            path: 'session/student/evidence.jpg',
            url: '/object/upload/sign/evidences/session/student/evidence.jpg',
            token: 'signed-upload-token',
            expires_in_seconds: 7200
          },
          { status: 201 }
        )
      }
      if (url.endsWith('/api/v1/events')) return new Response('{}', { status: 201 })
      // Storage. Se imita lo que hace Supabase de verdad: la URL firmada acepta
      // PUT y responde 400 a un POST. Sin esto el simulacro aceptaba cualquier
      // metodo y la prueba pasaba con una subida que en produccion nunca
      // funciono.
      if (init?.method !== 'PUT') {
        return Response.json(
          { statusCode: '400', message: "headers must have required property 'authorization'" },
          { status: 400 }
        )
      }
      return new Response(null, { status: 200 })
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.resetModules()

    const { sendEvent, setAuthSession } = await import('./sender')
    const event: ProctoringEvent = {
      session_id: '3f1a7c20-9b4e-4d2a-8f6c-1e2d3a4b5c60',
      student_id: '7b2e4d10-5c6f-4a8b-9d0e-2f3a4b5c6d71',
      question_id: null,
      event_type: 'suspicious_process',
      started_at: '2026-10-03T14:21:05.120Z',
      duration_ms: 0,
      metadata: {},
      evidence_path: null
    }
    setAuthSession({ accessToken: 'access-token', refreshToken: 'refresh-token' })
    sendEvent(event, Buffer.from('jpeg-data'))

    await vi.waitFor(() => {
      expect(requests.at(-1)?.url).toBe('http://localhost:8000/api/v1/events')
    })
    // Pedir la URL y mandar el evento son POST a la API; **subir a Storage es
    // PUT**. Si esto vuelve a decir POST, la subida devolvera 400 contra el
    // Storage real y el evento se guardara sin captura sin que nadie se entere.
    expect(requests.map((request) => request.method)).toEqual(['POST', 'PUT', 'POST'])
    expect(requests[0]?.url).toBe('http://localhost:8000/api/v1/evidence/upload-url')
    expect(requests[1]?.url).toBe(
      'https://example.supabase.co/storage/v1/object/upload/sign/evidences/session/student/evidence.jpg?token=signed-upload-token'
    )
    expect(JSON.parse(requests[2]?.body ?? '{}')).toMatchObject({
      event_type: 'suspicious_process',
      evidence_path: 'session/student/evidence.jpg'
    })
  })
})
