import { describe, expect, it } from 'vitest'
import { revisarAcceso } from './acceso'

describe('revisarAcceso', () => {
  it('pide los dos campos cuando están vacíos', () => {
    expect(revisarAcceso('', '')).toEqual({
      correo: 'Escribe tu correo institucional.',
      clave: 'Escribe tu contraseña.'
    })
  })

  it('trata un correo de solo espacios como vacío', () => {
    expect(revisarAcceso('   ', 'secreta').correo).toBe('Escribe tu correo institucional.')
  })

  it('avisa de un correo sin dominio', () => {
    expect(revisarAcceso('hsilvav2@upao', 'secreta').correo).toMatch(/no está completo/)
    expect(revisarAcceso('hsilvav2', 'secreta').correo).toMatch(/no está completo/)
  })

  it('acepta un correo con espacios alrededor', () => {
    expect(revisarAcceso('  hsilvav2@upao.edu.pe ', 'secreta')).toEqual({})
  })

  it('no recorta la contraseña: un espacio cuenta como contraseña', () => {
    expect(revisarAcceso('hsilvav2@upao.edu.pe', ' ')).toEqual({})
  })
})
