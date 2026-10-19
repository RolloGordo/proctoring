import type { ProctoringEvent } from './api'

export function mergeEvents(...groups: readonly (readonly ProctoringEvent[])[]): ProctoringEvent[] {
  const byId = new Map<string, ProctoringEvent>()
  for (const group of groups) {
    for (const event of group) byId.set(event.id, event)
  }
  return [...byId.values()].sort(
    (left, right) => Date.parse(right.started_at) - Date.parse(left.started_at)
  )
}
