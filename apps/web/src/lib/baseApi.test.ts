import { describe, expect, it } from 'vitest'

import { baseApi } from './baseApi'

const MAPA =
  'proctoring-upao.me=https://api.proctoring-upao.me, proctoring-upao.app=https://api.proctoring-upao.app/'

describe('baseApi', () => {
  it('desde el .me usa la API del .me', () => {
    expect(baseApi('https://api.proctoring-upao.app', MAPA, 'proctoring-upao.me')).toBe(
      'https://api.proctoring-upao.me'
    )
  })

  it('desde el .app usa la del .app, sin la barra final', () => {
    expect(baseApi('https://otra', MAPA, 'proctoring-upao.app')).toBe(
      'https://api.proctoring-upao.app'
    )
  })

  it('un dominio que no está en la lista usa la de por defecto', () => {
    expect(baseApi('https://api.proctoring-upao.app', MAPA, 'web.86-48-18-81.sslip.io')).toBe(
      'https://api.proctoring-upao.app'
    )
  })

  it('no confunde un dominio que solo se parece', () => {
    expect(baseApi('https://api.proctoring-upao.app', MAPA, 'proctoring-upao.me.evil.test')).toBe(
      'https://api.proctoring-upao.app'
    )
  })

  it('ignora una entrada sin HTTPS', () => {
    expect(
      baseApi(
        'https://api.proctoring-upao.app',
        'proctoring-upao.me=http://api.proctoring-upao.me',
        'proctoring-upao.me'
      )
    ).toBe('https://api.proctoring-upao.app')
  })

  it('sin lista ni dominio, como antes', () => {
    expect(baseApi('https://api.proctoring-upao.app/', undefined, undefined)).toBe(
      'https://api.proctoring-upao.app'
    )
    expect(baseApi(undefined, undefined, undefined)).toBe('http://localhost:8000')
  })
})
