import { app, shell, BrowserWindow, ipcMain, screen } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'
import { examContext } from './context'
import { buildExtraDisplayEvent, buildFocusLostEvent } from './events'
import { applyWindowProtection } from './protection'
import { startProcessMonitor } from './processes'
import { sendEvent, setAuthSession } from './sender'

// Se conservan para mostrarlos en el panel local.
const events: ProctoringEvent[] = []
let mainWindow: BrowserWindow | null = null
let blurStartedAt: number | null = null
let stopProcessMonitor: (() => void) | null = null

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

  win.on('ready-to-show', () => {
    win.show()
    checkDisplays('exam_start')
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

  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    win.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    win.loadFile(join(__dirname, '../renderer/index.html'))
  }

  win.on('closed', () => {
    if (mainWindow === win) mainWindow = null
  })

  return win
}

app.whenReady().then(() => {
  electronApp.setAppUserModelId('com.proctoring.desktop')

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
  })

  screen.on('display-added', () => checkDisplays('display_added'))
  // El contrato no tiene evento para "monitor retirado": solo se actualiza el contador
  screen.on('display-removed', () => notifyDisplayCount())

  mainWindow = createWindow()
  stopProcessMonitor = startProcessMonitor(recordEvent)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) mainWindow = createWindow()
  })
})

app.on('before-quit', () => stopProcessMonitor?.())

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
