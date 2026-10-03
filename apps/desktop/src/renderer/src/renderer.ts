import '../styles.css'

const LABELS: Partial<Record<EventType, string>> = {
  focus_lost: 'Salió de la ventana',
  extra_display: 'Monitor adicional',
  suspicious_process: 'Proceso sospechoso'
}

/**
 * Severidad mostrada al estudiante.
 *
 * Reproduce `default_severity` del dominio de la API
 * (`services/api/src/proctoring_api/domain/severity.py`). Si allí cambian los
 * umbrales, cambian aquí: que el panel diga una cosa y el docente vea otra sería
 * peor que no mostrar nada.
 */
const FOCUS_LOST_ALTA_MS = 30_000
const FOCUS_LOST_MEDIA_MS = 5_000

type Severidad = 'alta' | 'media' | 'info'

function severity(event: ProctoringEvent): Severidad {
  switch (event.event_type) {
    case 'extra_person':
    case 'suspicious_process':
    case 'screen_share':
      return 'alta'
    case 'extra_display':
      return 'media'
    case 'focus_lost':
      if (event.duration_ms >= FOCUS_LOST_ALTA_MS) return 'alta'
      return event.duration_ms >= FOCUS_LOST_MEDIA_MS ? 'media' : 'info'
    default:
      return 'info'
  }
}

const NOMBRE_SEVERIDAD: Record<Severidad, string> = {
  alta: 'Alta',
  media: 'Media',
  info: 'Leve'
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

  const nivel = severity(event)
  const row = document.createElement('tr')
  // Solo lo alto marca la fila. Si todo se marca, nada destaca.
  if (nivel === 'alta') row.className = 'alerta'

  const hora = document.createElement('td')
  hora.textContent = new Date(event.started_at).toLocaleTimeString('es-PE')

  const senal = document.createElement('td')
  const etiqueta = document.createElement('span')
  etiqueta.className = `severidad severidad-${nivel}`
  etiqueta.textContent = NOMBRE_SEVERIDAD[nivel]
  senal.append(etiqueta, ' ', LABELS[event.event_type] ?? event.event_type)

  const detalle = document.createElement('td')
  detalle.textContent = describe(event) // textContent evita inyectar HTML

  const duracion = document.createElement('td')
  duracion.textContent = event.duration_ms > 0 ? formatDuration(event.duration_ms) : '—'

  row.append(hora, senal, detalle, duracion)
  body.prepend(row) // lo mas reciente arriba
  document.getElementById('vacio')?.remove()

  if (event.event_type === 'focus_lost') {
    focusLosses += 1
    totalMsOutside += event.duration_ms
  }
  setText('n-salidas', String(focusLosses))
  setText('t-fuera', formatDuration(totalMsOutside))
}

/** El UUID nulo significa que no hay sesion ni estudiante de verdad. */
const NIL_UUID = '00000000-0000-0000-0000-000000000000'

async function start(): Promise<void> {
  // Primero lo ocurrido antes de que cargara la ventana, luego lo nuevo
  const previous = await window.api.listEvents()
  previous.forEach(addRow)
  window.api.onNewEvent(addRow)

  setText('n-monitores', String(await window.api.getDisplayCount()))
  window.api.onDisplayCountChange((count) => setText('n-monitores', String(count)))

  // Si no hay contexto, los eventos no salen de la app: conviene que se vea en
  // pantalla y no solo en la consola.
  const contexto = await window.api.getExamContext()
  if (contexto.session_id === NIL_UUID || contexto.student_id === NIL_UUID) {
    document.getElementById('aviso-contexto')?.removeAttribute('hidden')
  }
}

window.addEventListener('DOMContentLoaded', () => {
  void start()
})
