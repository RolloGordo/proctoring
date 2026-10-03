/** Sesión del docente: token, perfil y acceso. */

import { useEffect, useState, type ReactNode } from 'react'
import { ContextoAuth } from './auth-context'
import { authEnabled, supabase } from './supabase'

export function ProveedorAuth({ children }: { children: ReactNode }) {
  const [cargando, setCargando] = useState(authEnabled)
  const [token, setToken] = useState<string>()
  const [email, setEmail] = useState<string>()
  const [rol, setRol] = useState<'teacher' | 'student'>()

  useEffect(() => {
    if (!supabase) return

    async function leerPerfil(userId: string): Promise<void> {
      const { data } = await supabase!
        .from('profiles')
        .select('role')
        .eq('id', userId)
        .maybeSingle()
      setRol((data?.role as 'teacher' | 'student') ?? undefined)
    }

    supabase.auth.getSession().then(({ data }) => {
      setToken(data.session?.access_token)
      setEmail(data.session?.user.email ?? undefined)
      if (data.session) void leerPerfil(data.session.user.id)
      setCargando(false)
    })

    // Mantiene el token al día: Supabase lo renueva solo antes de que venza.
    const { data: sub } = supabase.auth.onAuthStateChange((_evento, sesion) => {
      setToken(sesion?.access_token)
      setEmail(sesion?.user.email ?? undefined)
      if (sesion) void leerPerfil(sesion.user.id)
      else setRol(undefined)
    })

    return () => sub.subscription.unsubscribe()
  }, [])

  async function entrar(correo: string, password: string): Promise<void> {
    if (!supabase) return
    const { error } = await supabase.auth.signInWithPassword({ email: correo, password })
    if (error) throw new Error(traducir(error.message))
  }

  async function salir(): Promise<void> {
    await supabase?.auth.signOut()
  }

  return (
    <ContextoAuth.Provider value={{ cargando, token, email, rol, entrar, salir }}>
      {children}
    </ContextoAuth.Provider>
  )
}

/** Los mensajes de Supabase vienen en inglés; la interfaz está en español. */
function traducir(mensaje: string): string {
  if (mensaje.includes('Invalid login credentials')) return 'Correo o contraseña incorrectos'
  if (mensaje.includes('Email not confirmed')) return 'Falta confirmar el correo'
  return mensaje
}
