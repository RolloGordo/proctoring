/**
 * De dónde sale el examen que ve el estudiante.
 *
 * La app de escritorio **no reimplementa el examen**: carga la misma web que
 * usa el docente, en la ruta del examen, dentro de una ventana en modo kiosco
 * con la protección de contenido puesta. Tener dos exámenes distintos —uno en
 * React y otro en Electron— sería tener dos sitios donde arreglar cada cosa.
 *
 * El panel local de eventos sigue existiendo como herramienta de diagnóstico
 * (`PROCTORING_PANEL=1`): sirve para ver qué está detectando el proceso principal
 * sin montar un examen entero.
 */

import { join } from 'path'
import type { BrowserWindow } from 'electron'
import { examContext, setExamSession } from './context'

const NIL_UUID = '00000000-0000-0000-0000-000000000000'

/**
 * Dónde vive la web del examen.
 *
 * Tres sitios, en este orden, y el orden importa:
 *
 * 1. `PROCTORING_WEB_URL` del entorno, que permite apuntar una compilación a
 *    otro sitio sin reconstruirla. Es lo que usamos para probar.
 * 2. La **horneada al construir** (`__PROCTORING_WEB_URL__`). Es la que lleva
 *    un instalador publicado, porque en el equipo de un estudiante no hay
 *    ninguna variable de entorno que leer y el `.env` no viaja en el paquete.
 * 3. El servidor de desarrollo, solo cuando no hay ninguna de las dos.
 *
 * De esta única dirección cuelgan cuatro cosas —qué carga la ventana, a dónde
 * puede navegar, a qué origen se le conceden cámara y micrófono, y qué origen
 * acepta el enlace `proctoring://`—, así que apuntarla bien es lo único que
 * hace falta para mover la aplicación a producción.
 */
export function webBaseUrl(): string {
  const delEntorno = process.env['PROCTORING_WEB_URL']?.trim()
  const horneada = typeof __PROCTORING_WEB_URL__ === 'string' ? __PROCTORING_WEB_URL__.trim() : ''
  return (delEntorno || horneada || 'http://localhost:5173').replace(/\/$/, '')
}

/**
 * A dónde abre la ventana.
 *
 * - Con `PROCTORING_SESSION_ID`: directo a la sala de ese examen.
 * - Sin ella: a la pantalla del código de acceso. Si hay login, la web pide
 *   primero iniciar sesión; el estudiante entra, escribe su código y el examen
 *   sale de ahí. No hay que configurar nada a mano.
 */
export function examUrl(sessionId?: string): string {
  const base = webBaseUrl()
  const targetSessionId = sessionId ?? examContext.session_id
  return targetSessionId === NIL_UUID ? `${base}/examen` : `${base}/examen/${targetSessionId}/sala`
}

/**
 * Carga la web del examen en la ventana, o el panel local si se pide.
 *
 * El panel de eventos es la herramienta de diagnóstico del proceso principal:
 * se abre con `PROCTORING_PANEL=1`. Ya no es lo que se abre por defecto, porque
 * el estudiante tiene que ver el examen.
 *
 * Devuelve qué se cargó, para que quien llame pueda decirlo en el registro.
 */
export function loadExam(win: BrowserWindow, sessionId?: string): 'examen' | 'panel' {
  if (process.env['PROCTORING_PANEL'] !== '1' || sessionId !== undefined) {
    const url = examUrl(sessionId)
    // La supervision no empieza al abrir la app sino al llegar a /rendir, tras
    // el consentimiento. Aunque el entorno traiga un examen para abrir la sala,
    // no se registra nada hasta entonces.
    setExamSession(null)
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

const RETRY_MS = 3_000

/** Códigos de Chromium que no son un fallo: -3 es "cancelada" (otra navegación la reemplazó). */
const ABORTED = -3

/**
 * Si la web no carga, muestra un aviso claro y reintenta solo.
 *
 * Sin esto la ventana se queda con la pantalla de error de Chromium, que a un
 * estudiante en pleno examen no le dice nada util. Y reintentar solo importa:
 * si se cae la red un momento, el examen tiene que volver sin que nadie toque la
 * app, en kiosco no hay barra de direcciones ni boton de recargar.
 */
export function recoverFromLoadFailure(win: BrowserWindow): void {
  let timer: NodeJS.Timeout | undefined

  win.webContents.on('did-fail-load', (_event, code, _description, failedUrl, isMainFrame) => {
    if (!isMainFrame || code === ABORTED || failedUrl.startsWith('data:')) return
    console.warn('[ventana] no se pudo cargar', failedUrl, 'codigo', code)

    void win.loadURL(
      'data:text/html;charset=utf-8,' +
        encodeURIComponent(
          '<!doctype html><meta charset="utf-8"><title>Proctoring</title>' +
            '<body style="font-family:sans-serif;max-width:32rem;margin:20vh auto;padding:0 1rem;color:#212529">' +
            '<h1 style="font-size:1.25rem">No se pudo abrir el examen</h1>' +
            '<p>Revisa tu conexión. Se vuelve a intentar solo cada pocos segundos; no cierres la aplicación.</p>'
        )
    )

    clearTimeout(timer)
    timer = setTimeout(() => {
      if (!win.isDestroyed()) void win.loadURL(failedUrl)
    }, RETRY_MS)
  })

  win.on('closed', () => clearTimeout(timer))
}
