import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { buildExtraDisplayEvent, buildFocusLostEvent } from './events'
import { findSuspicious } from './processes'

const context = {
  session_id: '3f1a7c20-9b4e-4d2a-8f6c-1e2d3a4b5c60',
  student_id: '7b2e4d10-5c6f-4a8b-9d0e-2f3a4b5c6d71'
}

describe('findSuspicious', () => {
  it('normalizes process names and returns only one match per process name', () => {
    expect(
      findSuspicious([
        { name: 'Zoom.exe', pid: 101 },
        { name: 'zoom', pid: 202 },
        { name: 'AnyDesk.EXE', pid: 303 },
        { name: 'notepad.exe', pid: 404 }
      ])
    ).toEqual([
      { processName: 'zoom', category: 'screen_share', pid: 101 },
      { processName: 'anydesk', category: 'remote_desktop', pid: 303 }
    ])
  })
})

describe('buildFocusLostEvent', () => {
  it('never creates a negative duration', () => {
    const event = buildFocusLostEvent(context, 1_000, 900, true)

    expect(event.duration_ms).toBe(0)
  })
})

describe('buildExtraDisplayEvent', () => {
  it('matches the shared extra_display contract example', () => {
    const example = JSON.parse(
      readFileSync(
        new URL('../../../../packages/contracts/examples/extra_display.json', import.meta.url),
        'utf8'
      )
    ) as ProctoringEvent
    const detectedAt = Date.parse(example.started_at)
    const displays = example.metadata['displays'] as Array<{
      id: number
      bounds: { width: number; height: number }
      scale_factor: number
    }>

    const event = buildExtraDisplayEvent(
      context,
      displays.map((display) => ({
        id: display.id,
        bounds: display.bounds,
        scaleFactor: display.scale_factor
      })),
      'exam_start',
      detectedAt
    )

    expect(event).toEqual(example)
  })
})
