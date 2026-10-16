import { describe, expect, it, vi } from 'vitest'
import { origenDeSupabase } from './supabase'

describe('la URL de Supabase', () => {
  it('deja intacto el origen correcto', () => {
    expect(origenDeSupabase('https://abc.supabase.co')).toBe('https://abc.supabase.co')
  })

  it('quita la ruta /rest/v1 que enseña el panel en sus ejemplos', () => {
    // El caso real: con la ruta puesta, el cliente construye
    // /rest/v1/auth/v1/token y el login falla con un PGRST125 que no dice nada.
    const avisos = vi.spyOn(console, 'warn').mockImplementation(() => {})

    expect(origenDeSupabase('https://abc.supabase.co/rest/v1/')).toBe('https://abc.supabase.co')
    expect(avisos).toHaveBeenCalled()

    avisos.mockRestore()
  })

  it('quita la barra final', () => {
    expect(origenDeSupabase('https://abc.supabase.co/')).toBe('https://abc.supabase.co')
  })

  it('sin valor no hay cliente', () => {
    expect(origenDeSupabase(undefined)).toBeUndefined()
    expect(origenDeSupabase('   ')).toBeUndefined()
  })

  it('una direccion invalida no revienta la aplicacion', () => {
    const errores = vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(origenDeSupabase('esto-no-es-una-url')).toBeUndefined()
    expect(errores).toHaveBeenCalled()

    errores.mockRestore()
  })
})
