import { describe, expect, it, vi } from 'vitest'
import { captureEvidenceForEvent } from './capturas'

type CaptureDependencies = NonNullable<Parameters<typeof captureEvidenceForEvent>[1]>

function makeEvent(
  sessionId: string,
  eventType: ProctoringEvent['event_type'] = 'suspicious_process'
): ProctoringEvent {
  return {
    session_id: sessionId,
    student_id: '7b2e4d10-5c6f-4a8b-9d0e-2f3a4b5c6d71',
    question_id: null,
    event_type: eventType,
    started_at: '2026-10-03T14:21:05.120Z',
    duration_ms: 0,
    metadata: {},
    evidence_path: null
  }
}

describe('captureEvidenceForEvent', () => {
  it('captures only relevant events and applies the cooldown and per-exam cap', async () => {
    let now = 0
    const source = {
      display_id: '12',
      thumbnail: {
        isEmpty: () => false,
        toJPEG: vi.fn(() => Buffer.from('jpeg-data'))
      }
    }
    const getSources = vi.fn(async (options: Parameters<CaptureDependencies['getSources']>[0]) =>
      options.types.includes('screen') ? [source] : []
    )
    const captureDependencies: CaptureDependencies = {
      getPrimaryDisplay: () => ({ id: 12, workAreaSize: { width: 1920, height: 1080 } }),
      getSources,
      now: () => now
    }
    const sessionId = '3f1a7c20-9b4e-4d2a-8f6c-1e2d3a4b5c60'

    expect(
      await captureEvidenceForEvent(makeEvent(sessionId, 'focus_lost'), captureDependencies)
    ).toBeNull()
    const first = await captureEvidenceForEvent(makeEvent(sessionId), captureDependencies)
    expect(first).toEqual(Buffer.from('jpeg-data'))
    expect(getSources).toHaveBeenCalledWith({
      types: ['screen'],
      thumbnailSize: { width: 960, height: 540 }
    })

    now += 4_999
    expect(await captureEvidenceForEvent(makeEvent(sessionId), captureDependencies)).toBeNull()

    for (let captureIndex = 1; captureIndex < 20; captureIndex += 1) {
      now += 5_000
      expect(
        await captureEvidenceForEvent(makeEvent(sessionId), captureDependencies)
      ).not.toBeNull()
    }

    now += 5_000
    expect(await captureEvidenceForEvent(makeEvent(sessionId), captureDependencies)).toBeNull()
    expect(getSources).toHaveBeenCalledTimes(20)
  })
})
