// Identificadores de la sesion de examen y del estudiante.
//
// Quien rinde y en que examen ya no hace falta configurarlo a mano: el
// estudiante inicia sesion en la web que carga esta ventana, y de ahi salen los
// dos datos.
//
// - student_id: el `sub` del token de Supabase que la web entrega al proceso
//   principal (`auth:set-session`).
// - session_id: el examen que la ventana tiene abierto, leido de la URL.
//
// Las variables de entorno quedan como respaldo para desarrollar sin login y
// para el panel local de diagnostico. El UUID nulo solo sirve para ese panel: la
// API lo rechazaria porque no existe en la base de datos.
const NIL_UUID = '00000000-0000-0000-0000-000000000000'

const UUID = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
const UUID_PATTERN = new RegExp(`^${UUID}$`, 'i')
const LIVE_EXAM_PATH = new RegExp(`^/examen/(${UUID})/rendir/?$`, 'i')

const ENV_STUDENT_ID = process.env['PROCTORING_STUDENT_ID'] ?? NIL_UUID

export const examContext = {
  session_id: process.env['PROCTORING_SESSION_ID'] ?? NIL_UUID,
  student_id: ENV_STUDENT_ID
}

export type ExamContext = typeof examContext

/**
 * El estudiante que dice el token, o `null` si no se puede leer.
 *
 * **No verifica la firma, y no hace falta:** aqui el `sub` solo etiqueta los
 * eventos. Quien decide si el token es de verdad es la API, que lo verifica
 * contra el JWKS de Supabase y rechaza con 403 cualquier evento cuyo
 * `student_id` no coincida con el del token. Un token manipulado no consigue
 * nada: sus eventos serian rechazados.
 */
export function studentIdFromToken(accessToken: string): string | null {
  const payload = accessToken.split('.')[1]
  if (!payload) return null
  try {
    const claims = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8')) as {
      sub?: unknown
    }
    return typeof claims.sub === 'string' && UUID_PATTERN.test(claims.sub) ? claims.sub : null
  } catch {
    return null
  }
}

/**
 * Que examen esta rindiendo la ventana, segun su URL.
 *
 * - `undefined`: la pagina no es de la web del examen (el panel local, por
 *   ejemplo). No se toca nada.
 * - `null`: es la web, pero no el examen en curso.
 * - un UUID: esta en `/examen/<id>/rendir`.
 *
 * **Solo `/rendir` cuenta, no `/sala`.** El consentimiento se da en la sala; si
 * la supervision empezara al abrir la app, se observaria a alguien que todavia
 * no aceptado ser observado.
 */
export function liveExamSessionId(url: string, webOrigin: string): string | null | undefined {
  let parsed: URL
  try {
    parsed = new URL(url)
  } catch {
    return undefined
  }
  if (parsed.origin !== webOrigin) return undefined
  const match = LIVE_EXAM_PATH.exec(parsed.pathname)
  return match?.[1] ?? null
}

/** Fija el examen en curso. Devuelve `true` si cambio algo. */
export function setExamSession(sessionId: string | null): boolean {
  const next = sessionId ?? NIL_UUID
  if (next === examContext.session_id) return false
  examContext.session_id = next
  return true
}

/**
 * Fija el estudiante a partir del token que entrega la web. Con `null` (cerro
 * sesion) vuelve al respaldo del entorno.
 */
export function setStudentFromToken(accessToken: string | null): void {
  examContext.student_id =
    (accessToken !== null ? studentIdFromToken(accessToken) : null) ?? ENV_STUDENT_ID
}
