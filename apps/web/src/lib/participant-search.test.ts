import { describe, expect, it } from 'vitest'
import type { Participant } from './api'
import { filterParticipants } from './participant-search'

const participants = Array.from({ length: 12 }, (_, index) => ({
  id: `participant-${index}`,
  session_id: 'exam-1',
  student_id: `student-${index}`,
  attempt: 1,
  verification_status: 'verified',
  consent_at: null,
  verified_at: null,
  started_at: null,
  submitted_at: null,
  can_take_exam: true,
  score: null,
  student_name: index === 10 ? 'José Ramírez' : `Estudiante ${index + 1}`,
  student_email: `student${index + 1}@example.test`
})) satisfies Participant[]

describe('filterParticipants', () => {
  it('returns everyone when the search is empty', () => {
    expect(filterParticipants(participants, '')).toHaveLength(12)
  })

  it('searches by name without requiring accents or matching case', () => {
    expect(filterParticipants(participants, 'jose ramirez').map((item) => item.student_id)).toEqual(
      ['student-10']
    )
  })

  it('searches by email and supports a list larger than ten students', () => {
    expect(
      filterParticipants(participants, 'STUDENT12@EXAMPLE.TEST').map((item) => item.student_id)
    ).toEqual(['student-11'])
  })
})
