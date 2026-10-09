import { describe, expect, it } from 'vitest'
import type { Decision, Participant } from './api'
import { latestDecisionByStudent, summarizeResults } from './resultados'

function participant(studentId: string, score: number | null, submitted: boolean): Participant {
  return {
    id: `participant-${studentId}`,
    session_id: 'session-id',
    student_id: studentId,
    attempt: 1,
    verification_status: 'verified',
    consent_at: null,
    verified_at: null,
    started_at: null,
    submitted_at: submitted ? '2026-10-08T12:00:00Z' : null,
    can_take_exam: false,
    score
  }
}

function decision(studentId: string, decidedAt: string): Decision {
  return {
    id: `decision-${studentId}-${decidedAt}`,
    session_id: 'session-id',
    student_id: studentId,
    teacher_id: 'teacher-id',
    decision: 'dismissed',
    justification: 'Revisado',
    decided_at: decidedAt
  }
}

describe('summarizeResults', () => {
  it('counts submitted exams, averages available grades, and counts cases without a decision', () => {
    expect(
      summarizeResults(
        [
          participant('student-1', 16, true),
          participant('student-2', null, true),
          participant('student-3', 10, false)
        ],
        [decision('student-1', '2026-10-08T13:00:00Z')]
      )
    ).toEqual({
      submittedCount: 2,
      averageScore: 16,
      pendingReviewCount: 1
    })
  })

  it('uses the most recent decision for each student', () => {
    const latest = latestDecisionByStudent([
      decision('student-1', '2026-10-08T12:00:00Z'),
      {
        ...decision('student-1', '2026-10-08T13:00:00Z'),
        decision: 'confirmed'
      }
    ])

    expect(latest.get('student-1')?.decision).toBe('confirmed')
  })
})
