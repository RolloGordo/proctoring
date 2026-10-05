import { examContext } from './context'
import { buildSuspiciousProcessEvent } from './events'

export const POLL_INTERVAL_MS = 10_000

// Nombres en minuscula y sin ".exe". Coinciden con el nombre exacto del proceso.
const WATCHLIST: Record<string, string> = {
  zoom: 'screen_share',
  anydesk: 'remote_desktop',
  teamviewer: 'remote_desktop',
  obs: 'screen_recorder',
  obs32: 'screen_recorder',
  obs64: 'screen_recorder',
  discord: 'communication',
  vmware: 'virtual_machine',
  'vmware-vmx': 'virtual_machine',
  virtualbox: 'virtual_machine',
  virtualboxvm: 'virtual_machine'
}

export interface ProcessInfo {
  pid: number
  name: string
}

export interface ProcessMatch {
  processName: string
  category: string
  pid: number
}

function normalize(name: string): string {
  return name.toLowerCase().replace(/\.exe$/, '')
}

/** Devuelve un solo resultado por nombre de proceso, aunque haya varias instancias. */
export function findSuspicious(processes: ProcessInfo[]): ProcessMatch[] {
  const found = new Map<string, ProcessMatch>()
  for (const p of processes) {
    const key = normalize(p.name)
    const category = WATCHLIST[key]
    if (category && !found.has(key)) {
      found.set(key, { processName: key, category, pid: p.pid })
    }
  }
  return [...found.values()]
}

/**
 * Revisa los procesos cada 10 s. Emite un evento cuando un proceso de la
 * lista aparece; si se cierra y vuelve a abrir, emite otro.
 */
export interface ProcessMonitor {
  stop: () => void
  /**
   * Olvida lo ya visto y revisa de inmediato, como si fuera el inicio del examen.
   *
   * El monitor avisa de un proceso **una sola vez**, al verlo aparecer. Si
   * AnyDesk ya estaba abierto antes de que el estudiante llegara al examen, ese
   * aviso se emitio sin sesion y se descarto, y no volveria a emitirse nunca.
   * Al empezar el examen hay que volver a mirar.
   */
  rescan: () => void
}

export function startProcessMonitor(onEvent: (event: ProctoringEvent) => void): ProcessMonitor {
  const active = new Set<string>()
  let stopped = false
  let timer: NodeJS.Timeout | undefined
  let first = true
  let checking = false

  async function check(): Promise<void> {
    // Una revision a la vez: `rescan` puede llamar mientras hay una en curso.
    if (checking) return
    checking = true
    try {
      // import dinamico: ps-list es solo ESM y el main se compila a CommonJS
      const { default: psList } = await import('ps-list')
      const matches = findSuspicious(await psList())
      const current = new Set(matches.map((m) => m.processName))
      for (const m of matches) {
        if (!active.has(m.processName)) {
          onEvent(
            buildSuspiciousProcessEvent(examContext, m, first ? 'exam_start' : 'poll', Date.now())
          )
        }
      }
      active.clear()
      current.forEach((n) => active.add(n))
    } catch (error) {
      console.error('[processes] no se pudo leer la lista de procesos', error)
    } finally {
      checking = false
    }
    first = false
    if (!stopped) timer = setTimeout(check, POLL_INTERVAL_MS)
  }

  void check()
  return {
    stop: () => {
      stopped = true
      if (timer) clearTimeout(timer)
    },
    rescan: () => {
      active.clear()
      first = true
      if (timer) clearTimeout(timer)
      void check()
    }
  }
}
