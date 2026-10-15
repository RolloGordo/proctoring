/** TA-018: imagen JPEG de alerta hacia el bucket privado mediante URL firmada. */
import { api } from '../lib/api'
import { urlDeSubidaFirmada } from '../lib/identidad'
import type { ContextoEmision } from './emisor'

const MAX_BYTES = 2 * 1024 * 1024

export async function uploadImage(image: Blob, context: ContextoEmision): Promise<string> {
  if (image.type !== 'image/jpeg' || image.size === 0 || image.size > MAX_BYTES) {
    throw new Error('La captura JPEG debe tener entre 1 byte y 2 MiB.')
  }
  const permiso = await api.identityPhotoUpload(
    context.sessionId,
    context.studentId,
    'image',
    context.token
  )
  if (!permiso.path.startsWith(`${context.sessionId}/${context.studentId}/`)) {
    throw new Error('La API devolvió una ruta de evidencia fuera del estudiante actual.')
  }
  const signedUrl = new URL(urlDeSubidaFirmada(permiso.url, permiso.token))
  if (
    signedUrl.protocol !== 'https:' &&
    !(signedUrl.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(signedUrl.hostname))
  ) {
    throw new Error('La URL firmada debe usar HTTPS (o localhost durante desarrollo).')
  }
  const response = await fetch(signedUrl, {
    method: 'PUT',
    headers: { 'Content-Type': 'image/jpeg' },
    body: image,
    signal: AbortSignal.timeout(15_000)
  })
  if (!response.ok) throw new Error(`Storage rechazó la captura (HTTP ${response.status}).`)
  return permiso.path
}
