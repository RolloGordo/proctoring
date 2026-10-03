import type { BrowserWindow } from 'electron'

const COPY_PASTE_KEYS = new Set(['c', 'v', 'x'])

/**
 * Protege la ventana del examen:
 * - la oculta de capturas y de pantalla compartida (Zoom, Meet, OBS)
 * - bloquea copiar, pegar, cortar y el menu contextual
 * Para grabar una evidencia donde la ventana si deba verse, arrancar con
 * PROCTORING_DISABLE_CONTENT_PROTECTION=1.
 */
export function applyWindowProtection(win: BrowserWindow): void {
  if (process.env['PROCTORING_DISABLE_CONTENT_PROTECTION'] !== '1') {
    win.setContentProtection(true)
  }

  win.webContents.on('before-input-event', (event, input) => {
    if (input.type !== 'keyDown') return
    const key = input.key.toLowerCase()
    const withCtrl = input.control || input.meta
    const isCopyPaste =
      (withCtrl && COPY_PASTE_KEYS.has(key)) ||
      (withCtrl && key === 'insert') || // Ctrl+Insert
      (input.shift && key === 'insert') // Shift+Insert
    if (isCopyPaste) event.preventDefault()
  })

  win.webContents.on('context-menu', (event) => event.preventDefault())
}
