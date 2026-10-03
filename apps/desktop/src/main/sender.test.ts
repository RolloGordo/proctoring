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
})
