import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth-context'
import { authEnabled } from '../lib/supabase'

/** A donde va cada quien al entrar. */
function inicioSegunRol(rol?: 'teacher' | 'student'): string {
  return rol === 'student' ? '/examen' : '/sesiones'
}

export function Login() {
  const { entrar, token, cargando, rol } = useAuth()
  const navegar = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string>()
  const [enviando, setEnviando] = useState(false)

  // Sin Supabase configurado no hay a quién pedirle credenciales.
  if (!authEnabled || (!cargando && token))
    return <Navigate to={inicioSegunRol(rol)} replace />

  async function enviar(evento: FormEvent): Promise<void> {
    evento.preventDefault()
    setError(undefined)
    setEnviando(true)
    try {
      await entrar(email, password)
      // El rol llega con el perfil, justo despues del token; la redireccion
      // definitiva la hace el Navigate de arriba cuando ya se conoce.
      navegar('/', { replace: true })
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
      </div>
    </div>
  )
}
