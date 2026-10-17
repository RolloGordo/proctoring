import type { Decision, Participant } from './api'

export interface ResultsSummary {
  submittedCount: number
  averageScore: number | null
  pendingReviewCount: number
}

export function summarizeResults(
  participants: Participant[],
  decisions: Decision[]
): ResultsSummary {
  const submitted = participants.filter((participant) => participant.submitted_at !== null)
  const scores = submitted.flatMap((participant) =>
    participant.score === null ? [] : [participant.score]
  )
  const reviewedStudentIds = new Set(decisions.map((decision) => decision.student_id))

  return {
    submittedCount: submitted.length,
    averageScore:
      scores.length > 0 ? scores.reduce((total, score) => total + score, 0) / scores.length : null,
    pendingReviewCount: submitted.filter(
      (participant) => !reviewedStudentIds.has(participant.student_id)
    ).length
  }
}

export function latestDecisionByStudent(decisions: Decision[]): Map<string, Decision> {
  const latest = new Map<string, Decision>()
  for (const decision of decisions) {
    const current = latest.get(decision.student_id)
    if (!current || Date.parse(decision.decided_at) > Date.parse(current.decided_at)) {
      latest.set(decision.student_id, decision)
    }
  }
  return latest
}
