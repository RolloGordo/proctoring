import type { BrowserWindow } from 'electron'

const COPY_PASTE_KEYS = new Set(['c', 'v', 'x'])

/**
 * Protege la ventana del examen:
 * - la oculta de capturas y de pantalla compartida (Zoom, Meet, OBS)
 * - bloquea copiar, pegar, cortar y el menu contextual
 * Para grabar una evidencia donde la ventana si deba verse, arrancar con
 * PROCTORING_DISABLE_CONTENT_PROTECTION=1.
 */
export function applyWindowProtection(
  win: BrowserWindow,
  onCopyAttempt?: (shortcut: string) => void
): void {
  if (process.env['PROCTORING_DISABLE_CONTENT_PROTECTION'] !== '1') {
    win.setContentProtection(true)
  }

  win.webContents.on('before-input-event', (event, input) => {
    if (input.type !== 'keyDown' || input.isAutoRepeat) return
    const key = input.key.toLowerCase()
    const withCtrl = input.control || input.meta
    let copyShortcut: string | undefined
    if (key === 'c' && withCtrl) copyShortcut = input.meta ? 'Cmd+C' : 'Ctrl+C'
    else if (key === 'c' && input.alt) copyShortcut = 'Alt+C'
    else if (key === 'insert' && input.control) copyShortcut = 'Ctrl+Insert'
    const isCopyPaste =
      (withCtrl && COPY_PASTE_KEYS.has(key)) ||
      (withCtrl && key === 'insert') || // Ctrl+Insert
      (input.shift && key === 'insert') // Shift+Insert
    if (isCopyPaste || copyShortcut === 'Alt+C') event.preventDefault()
    if (copyShortcut) onCopyAttempt?.(copyShortcut)
  })

  win.webContents.on('context-menu', (event) => event.preventDefault())
}
