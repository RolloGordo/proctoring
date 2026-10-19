import { afterEach, expect, it, vi } from 'vitest'
import { uploadAudio } from './audioUpload'

afterEach(() => vi.unstubAllGlobals())
it('sends only metadata to API and audio directly to signed storage without JWT', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        path: 's/u/a.webm',
        url: 'https://example.supabase.co/storage/v1/object/upload/sign/audio-segments/s/u/a.webm?token=test'
      })
    })
    .mockResolvedValueOnce({ ok: true })
  vi.stubGlobal('fetch', fetch)
  const blob = new Blob(['audio'], { type: 'audio/webm' })
  expect(
    await uploadAudio(blob, { sessionId: 's', studentId: 'u', questionId: 'q', token: 'test' })
  ).toBe('s/u/a.webm')
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
    session_id: 's',
    student_id: 'u',
    kind: 'audio',
    extension: 'webm'
  })
  expect(fetch.mock.calls[1][1].body).toBe(blob)
  expect(fetch.mock.calls[1][1].headers).not.toHaveProperty('Authorization')
})
it('does not treat a failed storage upload as evidence', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ path: 's/u/a.webm', url: 'https://example.supabase.co/a' })
      })
      .mockResolvedValueOnce({ ok: false, status: 403 })
  )
  await expect(
    uploadAudio(new Blob(['a']), { sessionId: 's', studentId: 'u', questionId: 'q' })
  ).rejects.toThrow('Storage upload failed')
})

it('manda el token de la URL firmada, como hace la subida de imagen', async () => {
  // **El 404 que dejo el proyecto entero sin un solo fragmento de voz.** La API
  // devuelve `{path, url, token}`; aqui se declaraba el tipo sin `token`, asi
  // que se tiraba en silencio. Supabase contesta 404 a una URL firmada sin su
  // token, y las capturas de imagen subian bien porque ese camino si lo anade.
  const llamadas: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (entrada: RequestInfo | URL, init?: RequestInit) => {
      const url = String(entrada)
      llamadas.push(url)
      if (url.includes('/evidence/upload-url')) {
        return new Response(
          JSON.stringify({
            path: 's/u/frag.webm',
            url: 'https://supabase.ejemplo/storage/v1/object/upload/sign/audio-segments/s/u/frag.webm',
            token: 'el-token-firmado',
            expires_in_seconds: 60
          }),
          { status: 201 }
        )
      }
      expect(init?.method).toBe('PUT')
      return new Response(null, { status: 200 })
    })
  )

  const ruta = await uploadAudio(new Blob(['x'], { type: 'audio/webm' }), {
    sessionId: 's',
    studentId: 'u',
    questionId: 'q1'
  })

  expect(ruta).toBe('s/u/frag.webm')
  const subida = llamadas.find((u) => u.includes('/storage/'))
  expect(subida).toContain('token=el-token-firmado')
})
