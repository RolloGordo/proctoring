import { describe, expect, it, afterEach } from 'vitest'
import { examUrl, webBaseUrl } from './web'

// `examContext` se arma al importar el modulo a partir del entorno, asi que
// estas pruebas cubren lo que no depende de el: la URL base y el caso de
// "no hay sesion configurada", que es el que decide si se ve el examen o el
// panel de diagnostico.
const ORIGINAL = process.env['PROCTORING_WEB_URL']

afterEach(() => {
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
  it('sin sesion configurada no hay examen que cargar', () => {
    // El UUID nulo es lo que deja `context.ts` cuando no hay variables de
    // entorno: cargar /examen/00000000-.../sala solo daria un 404 confuso.
    expect(examUrl()).toBeNull()
  })
})
