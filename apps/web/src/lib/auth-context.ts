/** Contexto de sesión. Vive aparte del proveedor para que el módulo de
 * componentes exporte solo componentes (lo exige react-refresh). */

import { createContext, useContext } from 'react'

export interface AuthState {
  /** `true` mientras se recupera la sesión guardada, para no parpadear al login. */
  cargando: boolean
  /** Token de acceso para la API. `undefined` cuando no hay autenticación. */
  token?: string
  email?: string
  /** El rol vive en `public.profiles`, no en el token. */
  rol?: 'teacher' | 'student'
  /**
   * `true` cuando ya se consultó el perfil, **haya o no uno**.
   *
   * Sin esto no se distingue "el rol está por llegar" de "esta cuenta no tiene
   * perfil": en el segundo caso esperar para siempre dejaría a la persona
   * mirando una pantalla de carga sin saber qué pasó.
   */
  perfilListo: boolean
  entrar: (email: string, password: string) => Promise<void>
  salir: () => Promise<void>
}

export const ContextoAuth = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const estado = useContext(ContextoAuth)
  if (!estado) throw new Error('useAuth se usa dentro de ProveedorAuth')
  return estado
}
