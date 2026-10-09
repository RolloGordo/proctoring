import { desktopCapturer, screen } from 'electron'

const NIL_UUID = '00000000-0000-0000-0000-000000000000'
const CAPTURE_EVENT_TYPES = new Set<ProctoringEvent['event_type']>([
  'suspicious_process',
  'extra_display',
  'screen_share'
])
const MAX_CAPTURES_PER_EXAM = 20
const MIN_CAPTURE_INTERVAL_MS = 5_000
const JPEG_QUALITY = 70

interface CaptureBudget {
  count: number
  lastCaptureAt: number
  inFlight: boolean
}

interface CaptureDependencies {
  getPrimaryDisplay: () => {
    id: number
    workAreaSize: { width: number; height: number }
  }
  getSources: (options: {
    types: Array<'screen'>
    thumbnailSize: { width: number; height: number }
  }) => Promise<
    Array<{
      display_id: string
      thumbnail: { isEmpty: () => boolean; toJPEG: (quality: number) => Buffer }
    }>
  >
  now: () => number
}

const budgets = new Map<string, CaptureBudget>()

const defaultDependencies: CaptureDependencies = {
  getPrimaryDisplay: () => screen.getPrimaryDisplay(),
  getSources: (options) => desktopCapturer.getSources(options),
  now: () => Date.now()
}

export async function captureEvidenceForEvent(
  event: ProctoringEvent,
  dependencies: CaptureDependencies = defaultDependencies
): Promise<Buffer | null> {
  if (
    !CAPTURE_EVENT_TYPES.has(event.event_type) ||
    event.session_id === NIL_UUID ||
    event.student_id === NIL_UUID
  ) {
    return null
  }

  const budget = budgets.get(event.session_id) ?? {
    count: 0,
    lastCaptureAt: Number.NEGATIVE_INFINITY,
    inFlight: false
  }
  budgets.set(event.session_id, budget)

  const now = dependencies.now()
  if (budget.count >= MAX_CAPTURES_PER_EXAM) {
    console.warn('[capturas] se alcanzo el limite de capturas para el examen')
    return null
  }
  if (budget.inFlight || now - budget.lastCaptureAt < MIN_CAPTURE_INTERVAL_MS) {
    return null
  }

  budget.lastCaptureAt = now
  budget.inFlight = true

  try {
    const display = dependencies.getPrimaryDisplay()
    const { width, height } = display.workAreaSize
    const sources = await dependencies.getSources({
      types: ['screen'],
      thumbnailSize: {
        width: Math.max(1, Math.round(width / 2)),
        height: Math.max(1, Math.round(height / 2))
      }
    })
    const source =
      sources.find((item) => item.display_id === String(display.id)) ??
      (sources.length === 1 ? sources[0] : undefined)

    if (!source || source.thumbnail.isEmpty()) {
      console.error('[capturas] no se encontro una captura de la pantalla principal')
      return null
    }

    const jpeg = source.thumbnail.toJPEG(JPEG_QUALITY)
    if (jpeg.byteLength === 0) {
      console.error('[capturas] la captura genero un archivo JPEG vacio')
      return null
    }
    budget.count += 1
    return jpeg
  } catch (error) {
    console.error('[capturas] no se pudo capturar la pantalla', error)
    return null
  } finally {
    budget.inFlight = false
  }
}
