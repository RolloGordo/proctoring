import { describe, expect, it } from 'vitest'
import type { ProctoringEvent } from './api'
import { mergeEvents } from './live-events'

const makeEvent = (id: string, startedAt: string): ProctoringEvent => ({
  id,
  session_id: 'exam-1',
  student_id: 'student-1',
  question_id: null,
  event_type: 'focus_lost',
  started_at: startedAt,
  duration_ms: 0,
  metadata: {},
  evidence_path: null,
  severity: 'medium'
})

describe('mergeEvents', () => {
  it('retains events received while the initial list is loading', () => {
    expect(
      mergeEvents(
        [makeEvent('loaded', '2026-10-17T10:00:00Z')],
        [makeEvent('live', '2026-10-17T10:01:00Z')]
      ).map((event) => event.id)
    ).toEqual(['live', 'loaded'])
  })

  it('deduplicates events delivered by realtime and the list endpoint', () => {
    const loaded = makeEvent('same', '2026-10-17T10:00:00Z')
    const refreshed = { ...loaded, duration_ms: 5000 }

    expect(mergeEvents([loaded], [refreshed])).toEqual([refreshed])
  })
})
