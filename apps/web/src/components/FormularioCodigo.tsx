import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth-context'

/**
 * Teclear el código que dio el docente y llegar a la sala del examen.
 *
 * Vive aparte porque se usa en dos sitios: el panel del estudiante, donde es lo
 * primero que ve, y la pantalla "Entrar a un examen".
 *
 * El código se envía tal como se escribe; la API lo normaliza (mayúsculas, sin
 * espacios ni guiones), porque se lee de una pizarra o de un chat y hacerle
 * perder el examen a alguien por un espacio sería absurdo.
 */
export function FormularioCodigo({ compacto = false }: { compacto?: boolean }) {
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
    <form onSubmit={(e) => void enviar(e)} noValidate className={compacto ? 'codigo-linea' : ''}>
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
        {!compacto && (
          <p className="ayuda">Da igual si lo escribes en minúsculas o con espacios.</p>
        )}
      </label>

      <button type="submit" className="boton" disabled={buscando || !codigo.trim()}>
        {buscando ? 'Buscando…' : 'Buscar examen'}
      </button>
    </form>
  )
}
