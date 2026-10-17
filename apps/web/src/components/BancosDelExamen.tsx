import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type QuestionBank } from '../lib/api'
import { useAuth } from '../lib/auth-context'

/**
 * De qué bancos extrae un examen, con lo justo para atar y desatar.
 *
 * Desatar no borra nada del banco: el examen deja de usarlo y las preguntas
 * siguen ahí para el ciclo siguiente. El texto lo dice porque es exactamente la
 * clase de botón que da miedo pulsar.
 */
export function BancosDelExamen({ sessionId }: { sessionId: string }) {
  const { token } = useAuth()
  const [atados, setAtados] = useState<QuestionBank[]>()
  const [mios, setMios] = useState<QuestionBank[]>([])
  const [eligiendo, setEligiendo] = useState('')
  const [error, setError] = useState<string>()
  const [trabajando, setTrabajando] = useState(false)

  useEffect(() => {
    let cancelado = false
    api
      .listSessionBanks(sessionId, token)
      .then((datos) => !cancelado && setAtados(datos))
      .catch((fallo: Error) => !cancelado && setError(fallo.message))
    api
      .listBanks(token)
      .then((datos) => !cancelado && setMios(datos))
      .catch(() => undefined)
    return () => {
      cancelado = true
    }
  }, [sessionId, token])

  async function atar(): Promise<void> {
    if (!eligiendo) return
    setError(undefined)
    setTrabajando(true)
    try {
      await api.attachBank(sessionId, eligiendo, token)
      const banco = mios.find((b) => b.id === eligiendo)
      if (banco) setAtados((previos) => [...(previos ?? []), banco])
      setEligiendo('')
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo atar el banco')
    } finally {
      setTrabajando(false)
    }
  }

  async function desatar(bankId: string): Promise<void> {
    setError(undefined)
    setTrabajando(true)
    try {
      await api.detachBank(sessionId, bankId, token)
      setAtados((previos) => (previos ?? []).filter((b) => b.id !== bankId))
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo quitar el banco')
    } finally {
      setTrabajando(false)
    }
  }

  const yaAtados = new Set((atados ?? []).map((b) => b.id))
  const porAtar = mios.filter((b) => !yaAtados.has(b.id))
  const disponibles = (atados ?? []).reduce((suma, b) => suma + b.question_count, 0)

  return (
    <div className="tarjeta" style={{ marginBottom: 'var(--e5)' }}>
      <div className="tarjeta-cuerpo">
        <div className="fila" style={{ justifyContent: 'space-between' }}>
          <h3>Bancos de preguntas</h3>
          {atados && atados.length > 0 && (
            <span className="tenue">
              {disponibles} pregunta{disponibles === 1 ? '' : 's'} disponibles
            </span>
          )}
        </div>

        {error && <p className="aviso">{error}</p>}

        {atados?.length === 0 ? (
          <p className="ayuda">
            Este examen usa sus propias preguntas. Si atas un banco, las preguntas saldrán de ahí
            y cada estudiante recibirá su propio sorteo.
          </p>
        ) : (
          <ul className="lista-modulos">
            {atados?.map((banco) => (
              <li key={banco.id} className="fila" style={{ justifyContent: 'space-between' }}>
                <span>
                  <Link to={`/bancos/${banco.id}`}>{banco.name}</Link>{' '}
                  <span className="tenue">
                    · {banco.question_count} pregunta{banco.question_count === 1 ? '' : 's'}
                  </span>
                </span>
                <button
                  type="button"
                  className="boton boton-texto"
                  disabled={trabajando}
                  onClick={() => void desatar(banco.id)}
                >
                  Quitar
                </button>
              </li>
            ))}
          </ul>
        )}

        {porAtar.length > 0 && (
          <div className="fila" style={{ marginTop: 'var(--e3)' }}>
            <select
              value={eligiendo}
              onChange={(e) => setEligiendo(e.target.value)}
              aria-label="Banco que se quiere atar al examen"
            >
              <option value="">Elige un banco…</option>
              {porAtar.map((banco) => (
                <option key={banco.id} value={banco.id}>
                  {banco.name} ({banco.question_count})
                </option>
              ))}
            </select>
            <button
              type="button"
              className="boton boton-secundario"
              disabled={!eligiendo || trabajando}
              onClick={() => void atar()}
            >
              Atar al examen
            </button>
          </div>
        )}

        {mios.length === 0 && (
          <p className="ayuda" style={{ marginTop: 'var(--e3)' }}>
            Todavía no tienes bancos. <Link to="/bancos">Crea uno</Link> para escribir las
            preguntas una sola vez y reutilizarlas.
          </p>
        )}
      </div>
    </div>
  )
}
