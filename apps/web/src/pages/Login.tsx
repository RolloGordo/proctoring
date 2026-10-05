import { useState, type FormEvent } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../lib/auth-context'
import { inicioSegunRol } from '../lib/rutas'
import { authEnabled } from '../lib/supabase'

export function Login() {
  const { entrar, salir, token, cargando, rol, perfilListo } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string>()
  const [enviando, setEnviando] = useState(false)

  // Sin Supabase configurado no hay a quien pedirle credenciales.
  if (!authEnabled) return <Navigate to="/" replace />

  if (!cargando && token) {
    if (rol) return <Navigate to={inicioSegunRol(rol)} replace />

    // Hay sesion pero el perfil todavia no ha llegado. Si ya se consulto y no
    // hay rol, la cuenta existe en Supabase pero no tiene perfil: esperar para
    // siempre dejaria a la persona mirando "Entrando..." sin saber que pasa.
    return (
      <div className="pantalla-acceso">
        <div className="acceso-caja">
          <p className="acceso-marca">
            Proc<span>toring</span>
          </p>
          {perfilListo ? (
            <>
              <h1>Cuenta sin perfil</h1>
              <p className="aviso">
                Tu cuenta existe, pero no tiene un perfil en el sistema. Avisa a tu docente.
              </p>
              <button type="button" className="boton acceso-boton" onClick={() => void salir()}>
                Cerrar sesión
              </button>
            </>
          ) : (
            <p className="subtitulo">Entrando…</p>
          )}
        </div>
      </div>
    )
  }

  async function enviar(evento: FormEvent): Promise<void> {
    evento.preventDefault()
    setError(undefined)
    setEnviando(true)
    try {
      // No se navega aqui: cuando llegan el token y el perfil este mismo
      // componente se vuelve a pintar y redirige al panel que corresponde.
      await entrar(email, password)
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo iniciar sesión')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="pantalla-acceso">
      <div className="acceso-caja">
        <p className="acceso-marca">
          Proc<span>toring</span>
        </p>
        <h1>Iniciar sesión</h1>
        <p className="subtitulo">Supervisión de exámenes remotos</p>

        <form onSubmit={(e) => void enviar(e)} noValidate>
          {error && <p className="aviso">{error}</p>}

          <label className="campo">
            <span>Correo institucional</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              required
            />
          </label>

          <label className="campo">
            <span>Contraseña</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>

          <button type="submit" className="boton acceso-boton" disabled={enviando}>
            {enviando ? 'Entrando…' : 'Entrar'}
          </button>
        </form>

        <p className="acceso-volver">
          <Link to="/">← Volver al inicio</Link>
        </p>
      </div>
    </div>
  )
}
