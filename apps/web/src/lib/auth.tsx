/** Sesión del docente: token, perfil y acceso. */

import { useEffect, useState, type ReactNode } from 'react'
import type { Session } from '@supabase/supabase-js'
import { ContextoAuth } from './auth-context'
import { authEnabled, supabase } from './supabase'

/**
 * Dentro de la app de escritorio, le pasa la sesion al proceso principal.
 *
 * Es lo que conecta las dos mitades: el proceso principal es quien detecta
 * cambios de foco, monitores y procesos, y necesita el token para mandar esos
 * eventos a la API y saber a nombre de quien. En un navegador normal
 * `window.api` no existe y esto no hace nada.
 *
 * Se llama en **cada** cambio de sesion, renovaciones incluidas: Supabase rota
 * el token de refresco, y si el proceso principal se quedara con uno viejo, sus
 * eventos empezarian a fallar con 401 a mitad del examen.
 */
function entregarAlEscritorio(sesion: Session | null): void {
  void window.api?.setAuthSession?.(
    sesion ? { accessToken: sesion.access_token, refreshToken: sesion.refresh_token } : null
  )
}

export function ProveedorAuth({ children }: { children: ReactNode }) {
  const [cargando, setCargando] = useState(authEnabled)
  const [token, setToken] = useState<string>()
  const [email, setEmail] = useState<string>()
  const [userId, setUserId] = useState<string>()
  const [rol, setRol] = useState<'teacher' | 'student'>()
  const [perfilListo, setPerfilListo] = useState(false)

  useEffect(() => {
    if (!supabase) return

    async function leerPerfil(userId: string): Promise<void> {
      const { data } = await supabase!
        .from('profiles')
        .select('role')
        .eq('id', userId)
        .maybeSingle()
      setRol((data?.role as 'teacher' | 'student') ?? undefined)
      setPerfilListo(true)
    }

    supabase.auth.getSession().then(({ data }) => {
      setToken(data.session?.access_token)
      setEmail(data.session?.user.email ?? undefined)
      setUserId(data.session?.user.id)
      if (data.session) void leerPerfil(data.session.user.id)
      entregarAlEscritorio(data.session)
      setCargando(false)
    })

    // Mantiene el token al día: Supabase lo renueva solo antes de que venza.
    const { data: sub } = supabase.auth.onAuthStateChange((_evento, sesion) => {
      setToken(sesion?.access_token)
      setEmail(sesion?.user.email ?? undefined)
      setUserId(sesion?.user.id)
      if (sesion) void leerPerfil(sesion.user.id)
      else {
        setRol(undefined)
        setPerfilListo(false)
      }
      entregarAlEscritorio(sesion)
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
    <ContextoAuth.Provider
      value={{ cargando, token, email, userId, rol, perfilListo, entrar, salir }}
    >
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
