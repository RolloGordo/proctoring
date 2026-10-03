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
  entrar: (email: string, password: string) => Promise<void>
  salir: () => Promise<void>
}

export const ContextoAuth = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const estado = useContext(ContextoAuth)
  if (!estado) throw new Error('useAuth se usa dentro de ProveedorAuth')
  return estado
}
