import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CamaraEnVivo } from '../components/CamaraEnVivo'
import { api, type Decision, type Participant, type VerificationStatus } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { supabase } from '../lib/supabase'
import { nombreDecision, soloHora } from '../lib/formato'

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
  const { token, userId } = useAuth()

  const [participantes, setParticipantes] = useState<Participant[]>()
  const [error, setError] = useState<string>()
  const [enVivo, setEnVivo] = useState(false)
  const [revisando, setRevisando] = useState<string>()
  const [decisiones, setDecisiones] = useState<Decision[]>([])
  const [monitoreoActivo, setMonitoreoActivo] = useState(false)
  // El estudiante cuya cámara se está mirando. Uno a la vez: abrir el canal es
  // lo que hace que ese estudiante empiece a enviar, así que no se abren los de
  // todos «por si acaso». La cuadrícula completa es HU-015.
  const [mirando, setMirando] = useState<string>()

  const cargar = useCallback(() => {
    api
      .listParticipants(id, token)
      .then(setParticipantes)
      .catch((fallo: Error) => setError(fallo.message))
  }, [id, token])

  useEffect(cargar, [cargar])

  // Si el docente activó el monitoreo en vivo para este examen. Si no está
  // activo no se ofrece mirar: el estudiante no aceptó eso.
  useEffect(() => {
    api
      .getSession(id, token)
      .then((sesion) => setMonitoreoActivo('live_monitoring' in sesion.modules))
      .catch(() => undefined)
  }, [id, token])

  // Las decisiones son un complemento de la sala: si fallan, la sala sigue sirviendo.
  useEffect(() => {
    api
      .listDecisions(id, token)
      .then(setDecisiones)
      .catch(() => undefined)
  }, [id, token])

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

      {mirando && userId && (
        <div className="tarjeta">
          <div className="tarjeta-cuerpo">
            <div className="encabezado-seccion">
              <h2>Cámara en vivo</h2>
              <button type="button" className="boton boton-texto" onClick={() => setMirando(undefined)}>
                Dejar de mirar
              </button>
            </div>
            <CamaraEnVivo
              sessionId={id}
              studentId={mirando}
              teacherId={userId}
              nombre={nombreDe(participantes, mirando)}
            />
            <p className="ayuda">
              No se está grabando. La imagen viaja y se pierde: solo se guardan las capturas de los
              eventos que generaron alerta. Mientras no mires, el equipo del estudiante no envía
              nada, y él ve en su pantalla que lo estás mirando.
            </p>
          </div>
        </div>
      )}

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
                <th>Caso</th>
                <th aria-label="Acciones" />
              </tr>
            </thead>
            <tbody>
              {participantes?.map((participante) => (
                <tr key={participante.id}>
                  <td>
                    {participante.student_name ? (
                      <>
                        <strong>{participante.student_name}</strong>
                        <p className="ayuda">{participante.student_email}</p>
                      </>
                    ) : (
                      // Sin perfil: se muestra igual, con su identificador.
                      <span className="mono">{participante.student_id.slice(0, 8)}</span>
                    )}
                  </td>
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
                    <Link
                      to={`/sesiones/${id}/estudiantes/${participante.student_id}`}
                      className="boton boton-texto"
                    >
                      Revisar
                    </Link>
                    {vigente(decisiones, participante.student_id) && (
                      <span className="chip chip-programado">
                        {nombreDecision(vigente(decisiones, participante.student_id)!.decision)}
                      </span>
                    )}
                  </td>
                  <td>
                    {participante.submitted_at ? null : participante.can_take_exam ? (
                      monitoreoActivo && userId ? (
                        <button
                          type="button"
                          className="boton boton-texto"
                          disabled={mirando === participante.student_id}
                          onClick={() => setMirando(participante.student_id)}
                        >
                          {mirando === participante.student_id ? 'Mirando' : 'Ver cámara'}
                        </button>
                      ) : (
                        <span className="tenue">Rindiendo</span>
                      )
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

/** El nombre con el que se rotula la cámara. */
function nombreDe(participantes: Participant[] | undefined, studentId: string): string | undefined {
  return (participantes ?? []).find((p) => p.student_id === studentId)?.student_name ?? undefined
}

/** La decisión vigente de un estudiante: la más reciente. */
function vigente(decisiones: Decision[], studentId: string): Decision | undefined {
  return decisiones.find((d) => d.student_id === studentId)
}
