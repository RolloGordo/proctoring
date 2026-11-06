/**
 * La portada de un curso: prepararla en el navegador y subirla directo a Storage.
 *
 * Una foto del celular pesa 4 MB o más y mide 4000 px; en la tarjeta se ve a
 * 300. Por eso se reduce aquí a 1600 px y se pasa a WebP antes de subirla: queda
 * en unos cientos de KB, cabe en el límite de 2 MB del bucket y no gasta la
 * cuota del plan gratuito. La imagen no pasa por la API, igual que la evidencia.
 */
import { api, type Course, type CoverContentType } from './api'
import { urlDeSubidaFirmada } from './identidad'

/** Lo que se acepta elegir. El GIF y el SVG no: uno anima y el otro puede traer script. */
export const FORMATOS_PORTADA = ['image/jpeg', 'image/png', 'image/webp'] as const
/** Una foto tal cual sale del celular cabe de sobra; un archivo mayor es un error. */
export const MAX_ORIGINAL_BYTES = 15 * 1024 * 1024
/** El límite del bucket `course-covers`. */
export const MAX_SUBIDA_BYTES = 2 * 1024 * 1024
/** Por debajo de esto la portada se vería borrosa en una tarjeta ancha. */
export const ANCHO_MINIMO = 480
const ANCHO_MAXIMO = 1600

/** Comprueba lo que se puede saber sin abrir la imagen: el formato y el tamaño. */
export function validarArchivoPortada(archivo: File): void {
  if (!(FORMATOS_PORTADA as readonly string[]).includes(archivo.type)) {
    throw new Error('Elige una imagen JPG, PNG o WebP.')
  }
  if (archivo.size > MAX_ORIGINAL_BYTES) {
    throw new Error('La imagen pesa más de 15 MB. Elige una más liviana.')
  }
}

/** Reduce la imagen y la codifica en WebP (o JPEG si el navegador no sabe WebP). */
export async function prepararPortada(archivo: File): Promise<Blob> {
  validarArchivoPortada(archivo)

  let mapa: ImageBitmap
  try {
    // Respeta la orientación EXIF: una foto vertical del celular no sale girada.
    mapa = await createImageBitmap(archivo, { imageOrientation: 'from-image' })
  } catch {
    throw new Error('No se pudo abrir la imagen. Prueba con otra.')
  }

  try {
    if (mapa.width < ANCHO_MINIMO) {
      throw new Error(
        `La imagen mide ${mapa.width} px de ancho; se vería borrosa. Usa una de al menos ${ANCHO_MINIMO} px.`
      )
    }
    const escala = Math.min(1, ANCHO_MAXIMO / mapa.width)
    const lienzo = document.createElement('canvas')
    lienzo.width = Math.round(mapa.width * escala)
    lienzo.height = Math.round(mapa.height * escala)
    const contexto = lienzo.getContext('2d')
    if (!contexto) throw new Error('El navegador no pudo preparar la imagen.')
    contexto.drawImage(mapa, 0, 0, lienzo.width, lienzo.height)

    for (const [tipo, calidad] of [
      ['image/webp', 0.82],
      ['image/jpeg', 0.85]
    ] as const) {
      const blob = await new Promise<Blob | null>((listo) => lienzo.toBlob(listo, tipo, calidad))
      // Un navegador sin WebP devuelve PNG en silencio: se comprueba el tipo real.
      if (blob && blob.type === tipo && blob.size <= MAX_SUBIDA_BYTES) return blob
    }
    throw new Error('No se pudo dejar la imagen por debajo de 2 MB. Prueba con otra.')
  } finally {
    mapa.close()
  }
}

/** Sube la imagen ya preparada y la fija como portada. Devuelve el curso actualizado. */
export async function subirPortada(
  courseId: string,
  imagen: Blob,
  token?: string
): Promise<Course> {
  const tipo = imagen.type as CoverContentType
  if (!(FORMATOS_PORTADA as readonly string[]).includes(tipo) || imagen.size === 0) {
    throw new Error('La imagen preparada no es válida. Inténtalo de nuevo.')
  }

  const permiso = await api.courseCoverUpload(courseId, tipo, token)
  let respuesta: Response
  try {
    // Storage pide PUT y la URL firmada es la autorización: no se manda el JWT.
    respuesta = await fetch(urlDeSubidaFirmada(permiso.url, permiso.token), {
      method: 'PUT',
      headers: { 'Content-Type': tipo },
      body: imagen
    })
  } catch {
    throw new Error('No se pudo conectar con el almacenamiento para subir la imagen.')
  }
  if (!respuesta.ok) {
    throw new Error(`El almacenamiento rechazó la imagen (HTTP ${respuesta.status}).`)
  }
  // Solo tras una subida correcta: si no, el curso apuntaría a un archivo que no existe.
  return api.setCourseCover(courseId, permiso.path, token)
}
