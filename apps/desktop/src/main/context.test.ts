import { describe, expect, it } from 'vitest'
import { examContext, liveExamSessionId, setExamSession, setStudentFromToken } from './context'

const SESSION = '3f1a7c20-9b4e-4d2a-8f6c-1e2d3a4b5c60'
const STUDENT = '7b2e4d10-5c6f-4a8b-9d0e-2f3a4b5c6d71'
const WEB = 'http://localhost:5173'
const NIL = '00000000-0000-0000-0000-000000000000'

/** Un token con la forma de un JWT. La firma no importa: aqui no se verifica. */
function tokenOf(claims: object): string {
  const part = (value: object): string => Buffer.from(JSON.stringify(value)).toString('base64url')
  return `${part({ alg: 'ES256' })}.${part(claims)}.firma`
}

describe('liveExamSessionId', () => {
  it('reconoce el examen en curso', () => {
    expect(liveExamSessionId(`${WEB}/examen/${SESSION}/rendir`, WEB)).toBe(SESSION)
  })

  it('la sala NO cuenta: ahi todavia no hay consentimiento', () => {
    // Si la supervision empezara en /sala se observaria a quien aun no aceptó.
    expect(liveExamSessionId(`${WEB}/examen/${SESSION}/sala`, WEB)).toBeNull()
  })

  it('la pantalla del codigo y el login tampoco', () => {
    expect(liveExamSessionId(`${WEB}/examen`, WEB)).toBeNull()
    expect(liveExamSessionId(`${WEB}/login`, WEB)).toBeNull()
  })

  it('no distingue mayusculas del UUID ni la barra final', () => {
    expect(liveExamSessionId(`${WEB}/examen/${SESSION.toUpperCase()}/rendir/`, WEB)).toBe(
      SESSION.toUpperCase()
    )
  })

  it('un identificador que no es un UUID no sirve', () => {
    expect(liveExamSessionId(`${WEB}/examen/no-es-uuid/rendir`, WEB)).toBeNull()
  })

  it('otro origen no se toca: ni examen ni nada', () => {
    // Un sitio ajeno con la misma ruta no puede fingir un examen en curso.
    expect(liveExamSessionId(`https://otro.example/examen/${SESSION}/rendir`, WEB)).toBeUndefined()
    expect(liveExamSessionId('file:///C:/app/index.html', WEB)).toBeUndefined()
    expect(liveExamSessionId('esto no es una url', WEB)).toBeUndefined()
  })
})

describe('setStudentFromToken', () => {
  it('toma al estudiante del sub del token', () => {
    setStudentFromToken(tokenOf({ sub: STUDENT }))
    expect(examContext.student_id).toBe(STUDENT)
  })

  it('un token ilegible no inventa un estudiante', () => {
    setStudentFromToken(tokenOf({ sub: STUDENT }))
    setStudentFromToken('basura')
    expect(examContext.student_id).toBe(NIL)
  })

  it('un sub que no es un UUID se descarta', () => {
    setStudentFromToken(tokenOf({ sub: 'no-es-uuid' }))
    expect(examContext.student_id).toBe(NIL)
  })

  it('al cerrar sesion vuelve al respaldo del entorno', () => {
    setStudentFromToken(tokenOf({ sub: STUDENT }))
    setStudentFromToken(null)
    expect(examContext.student_id).toBe(NIL)
  })
})

describe('setExamSession', () => {
  it('avisa solo cuando cambia algo', () => {
    setExamSession(null)
    expect(setExamSession(SESSION)).toBe(true)
    // Entrar otra vez a la misma pantalla no debe reiniciar la supervision.
    expect(setExamSession(SESSION)).toBe(false)
    expect(setExamSession(null)).toBe(true)
    expect(examContext.session_id).toBe(NIL)
  })
})
