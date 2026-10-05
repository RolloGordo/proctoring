import { describe, expect, it, afterEach } from 'vitest'
import { examUrl, webBaseUrl } from './web'
import { setExamSession } from './context'

// `examContext` se arma al importar el modulo a partir del entorno, asi que
// estas pruebas cubren lo que no depende de el.
const ORIGINAL = process.env['PROCTORING_WEB_URL']

afterEach(() => {
  setExamSession(null)
  if (ORIGINAL === undefined) delete process.env['PROCTORING_WEB_URL']
  else process.env['PROCTORING_WEB_URL'] = ORIGINAL
})

describe('webBaseUrl', () => {
  it('usa el servidor de desarrollo por defecto', () => {
    delete process.env['PROCTORING_WEB_URL']
    expect(webBaseUrl()).toBe('http://localhost:5173')
  })

  it('quita la barra final para no construir rutas con doble barra', () => {
    process.env['PROCTORING_WEB_URL'] = 'https://proctoring.vercel.app/'
    expect(webBaseUrl()).toBe('https://proctoring.vercel.app')
  })
})

describe('examUrl', () => {
  it('sin examen configurado abre la pantalla del codigo de acceso', () => {
    // Con login, la web pide primero iniciar sesion y despues el codigo: no hay
    // que configurar nada a mano.
    delete process.env['PROCTORING_WEB_URL']
    setExamSession(null)
    expect(examUrl()).toBe('http://localhost:5173/examen')
  })

  it('con un examen configurado abre su sala, no el examen en curso', () => {
    // La sala es donde se da el consentimiento. Saltarsela seria saltarse la
    // aceptacion.
    delete process.env['PROCTORING_WEB_URL']
    setExamSession('3f1a7c20-9b4e-4d2a-8f6c-1e2d3a4b5c60')
    expect(examUrl()).toBe('http://localhost:5173/examen/3f1a7c20-9b4e-4d2a-8f6c-1e2d3a4b5c60/sala')
  })
})
