import { app, shell, BrowserWindow, ipcMain, screen, session } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'
import { examContext, liveExamSessionId, setExamSession, setStudentFromToken } from './context'
import { buildExtraDisplayEvent, buildFocusLostEvent } from './events'
import { applyPermissionPolicy } from './permisos'
import { applyWindowProtection } from './protection'
import { startProcessMonitor, type ProcessMonitor } from './processes'
import { sendEvent, setAuthSession } from './sender'
import { loadExam, recoverFromLoadFailure, restrictNavigation, webBaseUrl } from './web'

// Se conservan para mostrarlos en el panel local.
const events: ProctoringEvent[] = []
let mainWindow: BrowserWindow | null = null
let blurStartedAt: number | null = null
let processMonitor: ProcessMonitor | null = null

function recordEvent(event: ProctoringEvent): void {
  events.push(event)
  sendEvent(event)
  console.log('[event]', event.event_type, event.duration_ms)
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('events:new', event)
  }
}

function notifyDisplayCount(): void {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('displays:changed', screen.getAllDisplays().length)
  }
}

// Evento extra_display solo cuando hay mas de un monitor
function checkDisplays(detectedOn: string): void {
  const displays = screen.getAllDisplays()
  notifyDisplayCount()
  if (displays.length > 1) {
    recordEvent(buildExtraDisplayEvent(examContext, displays, detectedOn, Date.now()))
  }
}

function closeFocusLost(returned: boolean): void {
  if (blurStartedAt === null) return
  const startedAt = blurStartedAt
  blurStartedAt = null
  recordEvent(buildFocusLostEvent(examContext, startedAt, Date.now(), returned))
}

/**
 * Empieza la supervision cuando el estudiante llega al examen en curso.
 *
 * Los avisos de "AnyDesk esta abierto" y "hay un segundo monitor" se emiten al
 * verlos aparecer, y antes de este momento no habia examen al que atribuirlos:
 * se habrian descartado y no volverian a emitirse. Por eso se vuelve a mirar
 * todo aqui, como si fuera el inicio.
 */
function startSupervision(): void {
  console.log('[examen] supervision iniciada para la sesion', examContext.session_id)
  checkDisplays('exam_start')
  processMonitor?.rescan()
}

/** Sigue a la ventana por la web: el examen en curso sale de la URL. */
function trackNavigation(url: string): void {
  const sessionId = liveExamSessionId(url, new URL(webBaseUrl()).origin)
  // undefined: no es la web del examen (el panel local); no se toca nada.
  if (sessionId === undefined) return
  if (setExamSession(sessionId) && sessionId !== null) startSupervision()
}

function isAuthSession(value: unknown): value is AuthSession {
  return (
    typeof value === 'object' &&
    value !== null &&
    'accessToken' in value &&
    typeof value.accessToken === 'string' &&
    'refreshToken' in value &&
    typeof value.refreshToken === 'string'
  )
}

function createWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 900,
    height: 670,
    show: false,
    autoHideMenuBar: true,
    // Modo kiosco solo fuera de desarrollo; para probarlo: PROCTORING_KIOSK=1
    kiosk: !is.dev || process.env['PROCTORING_KIOSK'] === '1',
    ...(process.platform === 'linux' ? { icon } : {}),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false
    }
  })

  applyWindowProtection(win)
  restrictNavigation(win)
  recoverFromLoadFailure(win)

  // La web es una SPA: ir de /sala a /rendir cambia la URL sin recargar, y eso
  // llega como `did-navigate-in-page`, no como `did-navigate`.
  win.webContents.on('did-navigate', (_event, url) => trackNavigation(url))
  win.webContents.on('did-navigate-in-page', (_event, url) => trackNavigation(url))

  win.on('ready-to-show', () => {
    win.show()
    // En el panel local no hay navegacion de examen: se revisa al abrir. En el
    // examen real se revisa al llegar a /rendir (ver startSupervision).
    if (process.env['PROCTORING_PANEL'] === '1') checkDisplays('exam_start')
  })

  // blur solo marca el inicio; el evento se emite al volver (un solo evento con duracion)
  win.on('blur', () => {
    if (blurStartedAt !== null) return
    blurStartedAt = Date.now()
  })
  win.on('focus', () => closeFocusLost(true))
  // Si cierra la app estando fuera de la ventana, no se pierde el evento
  win.on('close', () => closeFocusLost(false))

  win.webContents.setWindowOpenHandler((details) => {
    if (details.url.startsWith('https://')) shell.openExternal(details.url)
    return { action: 'deny' }
  })

  // La ventana carga la MISMA web del examen, no una copia en Electron. Sin
  // sesion configurada carga el panel local de eventos, que es la herramienta
  // de diagnostico del proceso principal.
  const cargado = loadExam(win)
  if (cargado === 'panel') {
    console.log(
      '[ventana] sin PROCTORING_SESSION_ID se abre el panel local de eventos, no el examen'
    )
  }

  win.on('closed', () => {
    if (mainWindow === win) mainWindow = null
  })

  return win
}

app.whenReady().then(() => {
  electronApp.setAppUserModelId('com.proctoring.desktop')

  // Camara y microfono solo para el examen, y solo desde su propio origen: la
  // deteccion de mirada y de habla corre en la web que carga esta ventana.
  applyPermissionPolicy(session.defaultSession, webBaseUrl())

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  ipcMain.handle('events:list', () => events)
  ipcMain.handle('displays:count', () => screen.getAllDisplays().length)
  // El panel avisa en pantalla si no hay contexto: sin el, los eventos no
  // salen de la app y conviene que se vea sin abrir la consola.
  ipcMain.handle('context:get', () => examContext)
  ipcMain.handle('auth:set-session', (_event, session: unknown) => {
    if (session !== null && !isAuthSession(session)) {
      throw new TypeError('La sesion de autenticacion de Supabase no es valida')
    }
    setAuthSession(session)
    // Quien rinde es quien dice el token. Con null (cerro sesion) vuelve al
    // respaldo del entorno.
    setStudentFromToken(session?.accessToken ?? null)
  })

  screen.on('display-added', () => checkDisplays('display_added'))
  // El contrato no tiene evento para "monitor retirado": solo se actualiza el contador
  screen.on('display-removed', () => notifyDisplayCount())

  mainWindow = createWindow()
  processMonitor = startProcessMonitor(recordEvent)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) mainWindow = createWindow()
  })
})

app.on('before-quit', () => processMonitor?.stop())

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
