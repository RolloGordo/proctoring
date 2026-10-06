/**
 * Permisos de la ventana del examen.
 *
 * La detección de mirada, rostro y habla corre en el navegador —es decir, en la
 * web que esta ventana carga—, así que necesita cámara y micrófono. Pero
 * conceder permisos a lo que pida la página sería dejar que cualquier sitio al
 * que llegara la ventana encendiera la cámara del estudiante.
 *
 * Aquí se conceden **solo** cámara y micrófono, y **solo** al origen del examen.
 * Todo lo demás se deniega, incluida la geolocalización y las notificaciones:
 * un examen no las necesita, y lo que no se necesita no se concede.
 *
 * Es la contraparte de `restrictNavigation` en `web.ts`: una ata a dónde puede
 * ir la ventana, esta ata qué puede hacer cuando llega.
 */

import type { Session } from 'electron'

/** Lo único que el examen necesita del sistema. */
const PERMITIDOS = new Set(['media', 'audioCapture', 'videoCapture'])

function mismoOrigen(url: string, permitido: string): boolean {
  try {
    return new URL(url).origin === permitido
  } catch {
    return false
  }
}

/**
 * Deja que solo el examen use cámara y micrófono.
 *
 * @param session sesión de Electron sobre la que aplicar las reglas.
 * @param webOrigin origen de la web del examen, por ejemplo `http://localhost:5173`.
 */
export function applyPermissionPolicy(session: Session, webOrigin: string): void {
  const permitido = new URL(webOrigin).origin

  session.setPermissionRequestHandler((contents, permission, callback) => {
    const url = contents?.getURL() ?? ''
    const concedido = PERMITIDOS.has(permission) && mismoOrigen(url, permitido)
    if (!concedido) {
      console.warn('[permisos] denegado', permission, 'a', url || '(sin url)')
    }
    callback(concedido)
  })

  // Algunas comprobaciones de permiso son sincronas y no pasan por el handler de
  // arriba; sin esta, el navegador podria responder "concedido" por su cuenta.
  session.setPermissionCheckHandler((_contents, permission, requestingOrigin) => {
    return PERMITIDOS.has(permission) && requestingOrigin === permitido
  })

  // Elegir qué cámara o micrófono se usa es del estudiante, no de la página: sin
  // esto, una página podría enumerar sus dispositivos.
  session.setDevicePermissionHandler(() => false)
}
