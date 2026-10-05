import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type Participant, type VerificationStatus } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { supabase } from '../lib/supabase'
import { soloHora } from '../lib/formato'

/** Cómo se lee cada estado y de qué color va. */
const ESTADOS: Record<VerificationStatus, { nombre: string; tono: 'low' | 'medium' | 'high' }> = {
  pending: { nombre: 'Esperando verificación', tono: 'medium' },
  verified: { nombre: 'Verificado', tono: 'low' },
  failed: { nombre: 'No reconocido', tono: 'high' },
  manually_approved: { nombre: 'Admitido por ti', tono: 'low' },
  rejected: { nombre: 'Rechazado por ti', tono: 'high' }
}

/**
 * Sala de espera del docente.
 *
 * Existe por una razón concreta: **un reconocimiento facial que falla con mala
 * luz no puede costarle el examen a nadie.** Aquí el docente ve quién llegó, en
 * qué estado está, y admite a mano a quien el sistema no reconoció. Queda
 * registrado quién lo admitió.
 *
 * Se actualiza por Supabase Realtime, igual que las alertas: la tabla
 * `session_participants` está publicada para eso.
 */
export function Participantes() {
  const { id = '' } = useParams()
  const { token } = useAuth()

  const [participantes, setParticipantes] = useState<Participant[]>()
  const [error, setError] = useState<string>()
  const [enVivo, setEnVivo] = useState(false)
  const [revisando, setRevisando] = useState<string>()

  const cargar = useCallback(() => {
    api
      .listParticipants(id, token)
      .then(setParticipantes)
      .catch((fallo: Error) => setError(fallo.message))
  }, [id, token])

  useEffect(cargar, [cargar])

  useEffect(() => {
    if (!supabase || !id) return

    const cliente = supabase
    const canal = cliente
      .channel(`participantes-${id}`)
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'session_participants',
          filter: `session_id=eq.${id}`
        },
        // Llega la fila cambiada, pero se recarga la lista entera: son pocas
        // filas y así no hay dos formas distintas de armar el mismo estado.
        () => cargar()
      )
      .subscribe((estado) => setEnVivo(estado === 'SUBSCRIBED'))

    return () => {
      void cliente.removeChannel(canal)
      setEnVivo(false)
    }
  }, [id, cargar])

  async function revisar(studentId: string, aprobar: boolean): Promise<void> {
    setError(undefined)
    setRevisando(studentId)
    try {
      const actualizado = await api.reviewIdentity(id, studentId, aprobar, token)
      setParticipantes((previos) =>
        (previos ?? []).map((p) => (p.student_id === studentId ? actualizado : p))
      )
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo registrar tu decisión')
    } finally {
      setRevisando(undefined)
    }
  }

  const esperando = (participantes ?? []).filter((p) => !p.can_take_exam && !p.submitted_at).length

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>Sala de espera</h1>
          <p className="subtitulo">
            {participantes
              ? `${participantes.length} ${participantes.length === 1 ? 'estudiante' : 'estudiantes'}` +
                (esperando > 0 ? ` · ${esperando} esperando que los admitas` : '')
              : 'Cargando…'}
          </p>
        </div>
        <div className="fila">
          {supabase && (
            <span className="en-vivo">
              <span className={enVivo ? 'punto punto-activo' : 'punto'} />
              {enVivo ? 'En vivo' : 'Sin conexión'}
            </span>
          )}
          <Link to={`/sesiones/${id}`} className="boton boton-secundario">
            Volver al examen
          </Link>
        </div>
      </div>

      {error && <p className="aviso">{error}</p>}

      <div className="tarjeta">
        {participantes?.length === 0 ? (
          <div className="vacio">
            <h3>Nadie ha entrado todavía</h3>
            <p className="subtitulo">
              Aparecerán aquí en cuanto acepten la supervisión con tu código de acceso.
            </p>
          </div>
        ) : (
          <table className="tabla">
            <thead>
              <tr>
                <th>Estudiante</th>
                <th>Identidad</th>
                <th>Entró</th>
                <th>Entregó</th>
                <th>Nota</th>
                <th aria-label="Acciones" />
              </tr>
            </thead>
            <tbody>
              {participantes?.map((participante) => (
                <tr key={participante.id}>
                  <td className="mono">{participante.student_id.slice(0, 8)}</td>
                  <td>
                    <span
                      className={`severidad severidad-${ESTADOS[participante.verification_status].tono}`}
                    >
                      {ESTADOS[participante.verification_status].nombre}
                    </span>
                  </td>
                  <td className="hora">
                    {participante.consent_at ? soloHora(participante.consent_at) : '—'}
                  </td>
                  <td className="hora">
                    {participante.submitted_at ? soloHora(participante.submitted_at) : '—'}
                  </td>
                  <td>
                    {participante.submitted_at && participante.score !== null
                      ? participante.score
                      : '—'}
                  </td>
                  <td>
                    {participante.submitted_at ? null : participante.can_take_exam ? (
                      <span className="tenue">Rindiendo</span>
                    ) : (
                      <div className="fila">
                        <button
                          type="button"
                          className="boton boton-secundario"
                          disabled={revisando === participante.student_id}
                          onClick={() => void revisar(participante.student_id, true)}
                        >
                          Admitir
                        </button>
                        <button
                          type="button"
                          className="boton boton-texto"
                          disabled={revisando === participante.student_id}
                          onClick={() => void revisar(participante.student_id, false)}
                        >
                          Rechazar
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <p className="ayuda" style={{ marginTop: 'var(--e4)' }}>
        Admitir a mano queda registrado con tu nombre. Es la salida prevista para cuando la cámara
        no reconoce a alguien por luz, lentes o calidad de imagen: el sistema avisa, tú decides.
      </p>
    </>
  )
}
