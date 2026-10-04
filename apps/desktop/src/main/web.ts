/**
 * De dónde sale el examen que ve el estudiante.
 *
 * La app de escritorio **no reimplementa el examen**: carga la misma web que
 * usa el docente, en la ruta del examen, dentro de una ventana en modo kiosco
 * con la protección de contenido puesta. Tener dos exámenes distintos —uno en
 * React y otro en Electron— sería tener dos sitios donde arreglar cada cosa.
 *
 * Si no hay sesión configurada se carga el panel local de eventos, que es la
 * herramienta de diagnóstico: sirve para ver qué está detectando el proceso
 * principal sin montar un examen entero.
 */

import { join } from 'path'
import type { BrowserWindow } from 'electron'
import { examContext } from './context'

const NIL_UUID = '00000000-0000-0000-0000-000000000000'

/** Dónde vive la web del examen. En producción, la URL del despliegue. */
export function webBaseUrl(): string {
  return (process.env['PROCTORING_WEB_URL'] ?? 'http://localhost:5173').replace(/\/$/, '')
}

/** La ruta del examen de esta sesión, o `null` si no hay sesión configurada. */
export function examUrl(): string | null {
  if (examContext.session_id === NIL_UUID) return null
  return `${webBaseUrl()}/examen/${examContext.session_id}/sala`
}

/**
 * Carga el examen en la ventana, o el panel local si no hay sesión.
 *
 * Devuelve qué se cargó, para que quien llame pueda decirlo en el registro:
 * arrancar sin sesión y ver el panel de eventos es fácil de confundir con un
 * error si nadie lo explica.
 */
export function loadExam(win: BrowserWindow): 'examen' | 'panel' {
  const url = examUrl()
  if (url !== null) {
    void win.loadURL(url)
    return 'examen'
  }

  // electron-vite define ELECTRON_RENDERER_URL solo al correr en desarrollo.
  // Se mira la variable en vez de `is.dev` de @electron-toolkit/utils porque
  // ese paquete importa electron al cargarse y este modulo tiene pruebas.
  const enDesarrollo = process.env['ELECTRON_RENDERER_URL']
  if (enDesarrollo) {
    void win.loadURL(enDesarrollo)
  } else {
    void win.loadFile(join(__dirname, '../renderer/index.html'))
  }
  return 'panel'
}

/**
 * Ata la ventana a su propio origen.
 *
 * La ventana del examen tiene un preload que expone `window.api`. Si el
 * estudiante consiguiera que navegara a otro sitio —un enlace en el enunciado,
 * una redirección— ese sitio heredaría esa API. Aquí solo se deja navegar
 * dentro del origen de la web del examen; cualquier otra cosa se cancela y se
 * registra.
 *
 * Es defensa en profundidad: el examen no debería tener enlaces hacia fuera.
 * Precisamente por eso, si alguna vez navega fuera, conviene que falle.
 */
export function restrictNavigation(win: BrowserWindow): void {
  const permitido = new URL(webBaseUrl()).origin

  win.webContents.on('will-navigate', (event, url) => {
    // file:// es el panel local de diagnostico, que se carga desde el disco.
    if (url.startsWith('file://')) return
    if (new URL(url).origin === permitido) return
    event.preventDefault()
    console.warn('[ventana] navegacion bloqueada hacia', new URL(url).origin)
  })
}
