import { describe, expect, it } from 'vitest'
import type { Alert } from './api'
import { mergeAlerts } from './live-alerts'

const makeAlert = (id: string, createdAt: string): Alert => ({
  id,
  event_id: `event-${id}`,
  session_id: 'exam-1',
  student_id: 'student-1',
  severity: 'high',
  reason: `Alert ${id}`,
  created_at: createdAt
})

describe('mergeAlerts', () => {
  it('retains realtime alerts received while the initial request is pending', () => {
    const loaded = [makeAlert('first', '2026-10-17T10:00:00Z')]
    const realtime = [makeAlert('live', '2026-10-17T10:01:00Z')]

    expect(mergeAlerts(loaded, realtime).map((alert) => alert.id)).toEqual(['live', 'first'])
  })

  it('deduplicates alerts returned by both the API and realtime', () => {
    const loaded = makeAlert('same', '2026-10-17T10:00:00Z')
    const realtime = { ...loaded, reason: 'Updated reason' }

    expect(mergeAlerts([loaded], [realtime])).toEqual([realtime])
  })
})
