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
