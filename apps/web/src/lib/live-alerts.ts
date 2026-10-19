import type { Alert } from './api'

export function mergeAlerts(...groups: readonly (readonly Alert[])[]): Alert[] {
  const byId = new Map<string, Alert>()
  for (const group of groups) {
    for (const alert of group) byId.set(alert.id, alert)
  }
  return [...byId.values()].sort(
    (left, right) => Date.parse(right.created_at) - Date.parse(left.created_at)
  )
}
