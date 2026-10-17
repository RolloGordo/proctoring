import { expect, it, vi } from 'vitest'
import { recordDiagnostic } from './diagnostics'
import type { SupabaseClient } from '@supabase/supabase-js'
const entry = {
  session_id: 'session', student_id: 'student',
  code: 'vision_module_failed' as const, module: 'mirada'
}
it('persists only diagnostic metadata under the student and session', async () => {
  const insert = vi.fn().mockResolvedValue({ error: null })
  const client = { from: vi.fn().mockReturnValue({ insert }) } as unknown as SupabaseClient
  expect(await recordDiagnostic(client, entry)).toBe(true)
  expect(client.from).toHaveBeenCalledWith('supervision_diagnostics')
  expect(insert).toHaveBeenCalledWith({
    session_id: 'session', student_id: 'student', code: 'vision_module_failed', module: 'mirada', details: {}
  })
})
it('does not break the exam if the database is unreachable or migration is missing', async () => {
  const client = { from: () => ({ insert: async () => ({ error: { message: 'not found' } }) }) } as unknown as SupabaseClient
  const err = vi.spyOn(console, 'error').mockImplementation(() => undefined)
  expect(await recordDiagnostic(client, entry)).toBe(false)
  expect(await recordDiagnostic(null, entry)).toBe(false)
  err.mockRestore()
})
