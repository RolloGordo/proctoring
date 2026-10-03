import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth-context'

/**
 * Entrada del estudiante: teclea el código que le dio su docente.
 *
 * El código se envía tal como lo escribe; la API lo normaliza (mayúsculas, sin
 * espacios ni guiones), porque lo lee de una pizarra o de un chat y hacerle
 * perder el examen por un espacio sería absurdo.
 */
export function AccesoExamen() {
  const { token } = useAuth()
  const navegar = useNavigate()
  const [codigo, setCodigo] = useState('')
  const [error, setError] = useState<string>()
  const [buscando, setBuscando] = useState(false)

  async function enviar(evento: FormEvent): Promise<void> {
    evento.preventDefault()
    setError(undefined)
    setBuscando(true)
    try {
      const examen = await api.joinExam(codigo, token)
      navegar(`/examen/${examen.session_id}/sala`, { state: examen })
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo buscar el examen')
    } finally {
      setBuscando(false)
    }
  }

  return (
    <div className="centrado-estrecho">
      <h1>Entrar a un examen</h1>
      <p className="subtitulo">Escribe el código que te dio tu docente</p>

      <div className="tarjeta" style={{ marginTop: 'var(--e6)' }}>
        <div className="tarjeta-cuerpo">
          <form onSubmit={(e) => void enviar(e)} noValidate>
            {error && <p className="aviso">{error}</p>}

            <label className="campo">
              <span>Código de acceso</span>
              <input
                value={codigo}
                onChange={(e) => setCodigo(e.target.value)}
                className="entrada-codigo"
                placeholder="KK8M5E"
                maxLength={16}
                autoComplete="off"
                autoCapitalize="characters"
                required
              />
              <p className="ayuda">Da igual si lo escribes en minúsculas o con espacios.</p>
            </label>

            <button type="submit" className="boton" disabled={buscando || !codigo.trim()}>
              {buscando ? 'Buscando…' : 'Buscar examen'}
            </button>
          </form>
        </div>
      </div>

      <p className="ayuda" style={{ marginTop: 'var(--e5)' }}>
        Para rendir el examen necesitas la aplicación de escritorio. Esta pantalla sirve para
        comprobar que tu código es correcto y ver cuándo empieza.
      </p>
    </div>
  )
}
