const LABELS: Partial<Record<EventType, string>> = {
  focus_lost: 'Salió de la ventana',
  extra_display: 'Monitor adicional',
  suspicious_process: 'Proceso sospechoso'
}

let focusLosses = 0
let totalMsOutside = 0

function formatDuration(ms: number): string {
  return ms < 60_000
    ? `${(ms / 1000).toFixed(1)} s`
    : `${Math.floor(ms / 60_000)} min ${Math.round((ms % 60_000) / 1000)} s`
}

function setText(id: string, value: string): void {
  const el = document.getElementById(id)
  if (el) el.textContent = value
}

function describe(event: ProctoringEvent): string {
  const meta = event.metadata
  if (event.event_type === 'focus_lost') {
    return meta['returned'] === false ? 'Cerró la app fuera de la ventana' : 'Volvió a la ventana'
  }
  if (event.event_type === 'extra_display') {
    const count = typeof meta['display_count'] === 'number' ? meta['display_count'] : '?'
    return `${count} monitores conectados`
  }
  if (event.event_type === 'suspicious_process') {
    const name = typeof meta['process_name'] === 'string' ? meta['process_name'] : '?'
    return `${name} está abierto`
  }
  return ''
}

function addRow(event: ProctoringEvent): void {
  const body = document.getElementById('cuerpo')
  if (!body) return

  const row = document.createElement('tr')
  row.className = 'alerta'

  const cells = [
    new Date(event.started_at).toLocaleTimeString('es-PE'),
    LABELS[event.event_type] ?? event.event_type,
    describe(event),
    event.duration_ms > 0 ? formatDuration(event.duration_ms) : ''
  ]
  for (const value of cells) {
    const td = document.createElement('td')
    td.textContent = value // textContent evita inyectar HTML
    row.appendChild(td)
  }
  body.prepend(row) // lo mas reciente arriba
  document.getElementById('vacio')?.remove()

  if (event.event_type === 'focus_lost') {
    focusLosses += 1
    totalMsOutside += event.duration_ms
  }
  setText('n-salidas', String(focusLosses))
  setText('t-fuera', formatDuration(totalMsOutside))
}

async function start(): Promise<void> {
  // Primero lo ocurrido antes de que cargara la ventana, luego lo nuevo
  const previous = await window.api.listEvents()
  previous.forEach(addRow)
  window.api.onNewEvent(addRow)

  setText('n-monitores', String(await window.api.getDisplayCount()))
  window.api.onDisplayCountChange((count) => setText('n-monitores', String(count)))
}

window.addEventListener('DOMContentLoaded', () => {
  void start()
})
