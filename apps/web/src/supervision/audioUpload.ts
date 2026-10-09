/** Upload audio straight to Storage. The API receives only JSON. */
import { ApiError } from '../lib/api'
import type { ContextoEmision } from './emisor'

const BASE = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export async function uploadAudio(audio: Blob, context: ContextoEmision): Promise<string> {
  if (!audio.size || audio.size > 8_000_000) throw new ApiError(400, 'Fragmento de audio inválido.')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (context.token) headers.Authorization = `Bearer ${context.token}`
  const response = await fetch(`${BASE}/api/v1/evidence/upload-url`, {
    method: 'POST',
    headers,
    signal: AbortSignal.timeout(15000),
    body: JSON.stringify({
      session_id: context.sessionId,
      student_id: context.studentId,
      kind: 'audio',
      extension: 'webm'
    })
  })
  if (!response.ok) throw new ApiError(response.status, 'No se pudo autorizar la subida de audio.')
  const data = (await response.json()) as { path: string; url: string }
  if (
    typeof data.path !== 'string' ||
    !data.path.startsWith(`${context.sessionId}/${context.studentId}/`)
  ) {
    throw new ApiError(400, 'Ruta de evidencia inválida.')
  }
  const url = new URL(data.url)
  if (
    url.protocol !== 'https:' &&
    !(url.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(url.hostname))
  ) {
    throw new ApiError(400, 'URL de Storage inválida.')
  }
  const upload = await fetch(url, {
    method: 'PUT',
    body: audio,
    headers: { 'Content-Type': 'audio/webm' },
    signal: AbortSignal.timeout(15000)
  })
  if (!upload.ok) throw new Error(`Storage upload failed (${upload.status})`)
  return data.path
}
