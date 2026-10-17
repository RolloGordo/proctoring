/** HU-006: transferencia de una foto a Supabase sin hacer pasar el JPEG por la API. */
import { api, type IdentityPhotoKind } from './api'

/** La firma viaja en la URL; algunas versiones del SDK la devuelven aparte. */
export function urlDeSubidaFirmada(url: string, token: string | null): string {
  if (!token || /[?&]token=/.test(url)) return url
  const separador = url.includes('?') ? '&' : '?'
  return `${url}${separador}token=${encodeURIComponent(token)}`
}

export async function subirFotoDeIdentidad({
  sessionId,
  studentId,
  kind,
  foto,
  token
}: {
  sessionId: string
  studentId: string
  kind: IdentityPhotoKind
  foto: Blob
  token?: string
}): Promise<string> {
  if (foto.size === 0 || foto.type !== 'image/jpeg') {
    throw new Error('No se pudo obtener una fotografía JPEG válida. Inténtalo nuevamente.')
  }

  const permiso = await api.identityPhotoUpload(sessionId, studentId, kind, token)
  if (!permiso.url || !permiso.path) {
    throw new Error('La API no devolvió una URL de subida válida.')
  }

  // Importante: Storage exige PUT, no POST, y la URL firmada es la autorización.
  // No se envía aquí el JWT del estudiante ni un campo JSON de la API.
  let respuesta: Response
  try {
    respuesta = await fetch(urlDeSubidaFirmada(permiso.url, permiso.token), {
      method: 'PUT',
      headers: { 'Content-Type': 'image/jpeg' },
      body: foto
    })
  } catch {
    throw new Error('No se pudo conectar a Storage para subir la fotografía.')
  }

  if (!respuesta.ok) {
    throw new Error(`Storage rechazó la fotografía (HTTP ${respuesta.status}). Intenta de nuevo.`)
  }
  // Solo devolvemos la ruta tras un PUT exitoso. De lo contrario el worker
  // recibiría referencias a imágenes inexistentes y quedaría inconcluso.
  return permiso.path
}
