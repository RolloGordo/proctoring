import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api } from './api'

afterEach(() => vi.unstubAllGlobals())

function respondeCon(status: number, cuerpo?: unknown): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      cuerpo === undefined
        ? new Response(null, { status })
        : new Response(JSON.stringify(cuerpo), {
            status,
            headers: { 'Content-Type': 'application/json' }
          })
    )
  )
}

describe('errores de la API', () => {
  it('conserva el codigo para distinguir 401 de 403', async () => {
    respondeCon(403, { detail: 'No tienes acceso a esta sesion de examen' })

    const fallo = await api.listSessions().catch((e: unknown) => e)

    expect(fallo).toBeInstanceOf(ApiError)
    expect((fallo as ApiError).status).toBe(403)
    expect((fallo as ApiError).message).toBe('No tienes acceso a esta sesion de examen')
  })

  it('traduce el 422 de Pydantic a algo legible', async () => {
    // Pydantic devuelve `detail` como lista, no como texto: sin esto el docente
    // veria "[object Object]".
    respondeCon(422, {
      detail: [
        { loc: ['body', 'title'], msg: 'String should have at least 1 character' },
        { loc: ['body', 'duration_minutes'], msg: 'Input should be greater than 0' }
      ]
    })

    const fallo = (await api.listSessions().catch((e: unknown) => e)) as ApiError

    expect(fallo.message).toContain('title')
    expect(fallo.message).toContain('duration_minutes')
  })

  it('no revienta si el cuerpo del error no es JSON', async () => {
    respondeCon(502)

    const fallo = (await api.listSessions().catch((e: unknown) => e)) as ApiError

    expect(fallo.status).toBe(502)
    expect(fallo.message).toContain('502')
  })

  it('traduce el fallo de conexión a la API a un mensaje accionable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      })
    )

    const fallo = await api.listSessions().catch((e: unknown) => e)

    expect(fallo).toBeInstanceOf(Error)
    expect((fallo as Error).message).toContain('No se pudo conectar con la API')
    expect((fallo as Error).message).not.toContain('Failed to fetch')
  })
})

describe('autenticacion', () => {
  it('manda el token cuando existe y lo omite cuando no', async () => {
    const espia = vi.fn(async () => new Response('[]', { status: 200 }))
    vi.stubGlobal('fetch', espia)

    await api.listSessions('token-de-prueba')
    await api.listSessions()

    const conToken = new Headers(
      (espia.mock.calls[0] as unknown as [string, RequestInit])[1].headers
    )
    const sinToken = new Headers(
      (espia.mock.calls[1] as unknown as [string, RequestInit])[1].headers
    )

    expect(conToken.get('Authorization')).toBe('Bearer token-de-prueba')
    expect(sinToken.get('Authorization')).toBeNull()
  })
})

describe('bancos de preguntas', () => {
  it('elimina un banco con una petición DELETE autenticada', async () => {
    const espia = vi.fn(async () => new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', espia)

    await api.deleteBank('bank-123', 'token-de-prueba')

    expect(espia).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/question-banks/bank-123'),
      expect.objectContaining({ method: 'DELETE' })
    )
  })
})
