import { describe, expect, it } from 'vitest'
import { examSessionFromArguments, examSessionFromProtocolUrl } from './protocol'

const SESSION = '3f1a7c20-9b4e-4d2a-8f6c-1e2d3a4b5c60'

describe('examSessionFromProtocolUrl', () => {
  it('accepts a proctoring link for an exam UUID', () => {
    expect(examSessionFromProtocolUrl(`proctoring://examen/${SESSION}`)).toBe(SESSION)
  })

  it('accepts UUIDs case-insensitively', () => {
    const upperCaseSession = SESSION.toUpperCase()
    expect(examSessionFromProtocolUrl(`proctoring://examen/${upperCaseSession}`)).toBe(
      upperCaseSession
    )
  })

  it.each([
    'not a URL',
    `https://examen/${SESSION}`,
    `proctoring://other/${SESSION}`,
    'proctoring://examen/not-a-uuid',
    `proctoring://examen/${SESSION}/extra`,
    `proctoring://user@examen/${SESSION}`,
    `proctoring://examen:${'8000'}/${SESSION}`,
    `proctoring://examen/${SESSION}?redirect=https://example.com`,
    `proctoring://examen/${SESSION}#section`
  ])('rejects an invalid or unexpected link: %s', (value) => {
    expect(examSessionFromProtocolUrl(value)).toBeNull()
  })
})

describe('examSessionFromArguments', () => {
  it('finds the protocol URL among process arguments', () => {
    expect(
      examSessionFromArguments([
        'C:\\Program Files\\Proctoring\\proctoring.exe',
        '--some-flag',
        `proctoring://examen/${SESSION}`
      ])
    ).toBe(SESSION)
  })

  it('returns null if there is no valid protocol URL', () => {
    expect(
      examSessionFromArguments(['electron.exe', 'index.js', 'proctoring://examen/invalid'])
    ).toBe(null)
  })
})
