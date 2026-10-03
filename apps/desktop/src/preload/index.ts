import { contextBridge, ipcRenderer } from 'electron'

// Con sandbox: true el preload solo puede usar 'electron' y APIs basicas.
// Solo se expone esta API minima; el renderer nunca recibe ipcRenderer.
const api = {
  listEvents: (): Promise<ProctoringEvent[]> => ipcRenderer.invoke('events:list'),
  onNewEvent: (callback: (event: ProctoringEvent) => void): (() => void) => {
    const listener = (_: unknown, event: ProctoringEvent): void => callback(event)
    ipcRenderer.on('events:new', listener)
    return () => ipcRenderer.removeListener('events:new', listener)
  },
  setAuthSession: (session: AuthSession | null): Promise<void> =>
    ipcRenderer.invoke('auth:set-session', session),
  getDisplayCount: (): Promise<number> => ipcRenderer.invoke('displays:count'),
  onDisplayCountChange: (callback: (count: number) => void): (() => void) => {
    const listener = (_: unknown, count: number): void => callback(count)
    ipcRenderer.on('displays:changed', listener)
    return () => ipcRenderer.removeListener('displays:changed', listener)
  }
}

contextBridge.exposeInMainWorld('api', api)
