const SESSION_UUID = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
const EXAM_PATH = new RegExp(`^/(${SESSION_UUID})/?$`, 'i')

export function examSessionFromProtocolUrl(value: string): string | null {
  let url: URL
  try {
    url = new URL(value)
  } catch {
    return null
  }

  if (
    url.protocol !== 'proctoring:' ||
    url.hostname !== 'examen' ||
    url.username !== '' ||
    url.password !== '' ||
    url.port !== '' ||
    url.search !== '' ||
    url.hash !== ''
  ) {
    return null
  }

  return EXAM_PATH.exec(url.pathname)?.[1] ?? null
}

export function examSessionFromArguments(args: string[]): string | null {
  for (const argument of args) {
    const sessionId = examSessionFromProtocolUrl(argument)
    if (sessionId !== null) return sessionId
  }
  return null
}
