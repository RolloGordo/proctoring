import type { Participant } from './api'

export function filterParticipants(participants: Participant[], query: string): Participant[] {
  const normalizedQuery = normalize(query.trim())
  if (!normalizedQuery) return participants

  return participants.filter((participant) =>
    [participant.student_name, participant.student_email]
      .filter((value): value is string => Boolean(value))
      .some((value) => normalize(value).includes(normalizedQuery))
  )
}

function normalize(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase()
}
