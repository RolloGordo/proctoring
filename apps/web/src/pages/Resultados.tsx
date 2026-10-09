import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type Decision, type ExamSession, type Participant, type Question } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { fechaLarga, nombreDecision, soloHora } from '../lib/formato'
import { latestDecisionByStudent, summarizeResults } from '../lib/resultados'

export function Resultados() {
  const { id = '' } = useParams()
  const { token } = useAuth()
  const [participantes, setParticipantes] = useState<Participant[]>()
  const [decisiones, setDecisiones] = useState<Decision[]>()
  const [sesion, setSesion] = useState<ExamSession>()
  const [preguntas, setPreguntas] = useState<Question[]>()
  const [error, setError] = useState<string>()

  useEffect(() => {
    let cancelado = false
    Promise.all([
      api.listParticipants(id, token),
      api.listDecisions(id, token),
      api.getSession(id, token),
      api.listQuestions(id, token)
    ])
      .then(([datosParticipantes, datosDecisiones, datosSesion, datosPreguntas]) => {
        if (cancelado) return
        setParticipantes(datosParticipantes)
        setDecisiones(datosDecisiones)
        setSesion(datosSesion)
        setPreguntas(datosPreguntas)
      })
      .catch((fallo: Error) => !cancelado && setError(fallo.message))

    return () => {
      cancelado = true
    }
  }, [id, token])

  const resumen = useMemo(
    () => (participantes && decisiones ? summarizeResults(participantes, decisiones) : undefined),
    [participantes, decisiones]
  )
  const decisionesVigentes = useMemo(() => latestDecisionByStudent(decisiones ?? []), [decisiones])
  const hayDesarrollos = preguntas?.some((pregunta) => pregunta.question_type === 'essay') ?? false

  if (error) return <p className="aviso">{error}</p>
  if (!participantes || !decisiones || !sesion || !preguntas || !resumen) {
    return <p className="tenue">Cargando resultados…</p>
  }

  const maxScore = Number(sesion.max_score)
  const notaMedia =
    resumen.averageScore === null
      ? '—'
      : `${formatearNota(resumen.averageScore)} / ${formatearNota(maxScore)}`

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>Resultados</h1>
          <p className="subtitulo">
            {sesion.title} · {fechaLarga(sesion.starts_at)}
          </p>
        </div>
        <div className="fila">
          <Link to={`/sesiones/${id}`} className="boton boton-secundario">
            Volver al examen
          </Link>
          <Link to={`/sesiones/${id}/participantes`} className="boton boton-secundario">
            Sala de espera
          </Link>
        </div>
      </div>

      <div className="panel-resumen">
        <Dato valor={resumen.submittedCount} etiqueta="Entregaron" />
        <Dato valor={notaMedia} etiqueta="Nota media" />
        <Dato valor={resumen.pendingReviewCount} etiqueta="Casos por revisar" tono="medium" />
      </div>

      {participantes.length === 0 ? (
        <div className="tarjeta">
          <div className="vacio">
            <h3>Aún no hay participantes</h3>
            <p className="subtitulo">Los resultados aparecerán cuando los estudiantes ingresen.</p>
          </div>
        </div>
      ) : (
        <div className="tarjeta">
          <table className="tabla">
            <thead>
              <tr>
                <th>Estudiante</th>
                <th>Entregado</th>
                <th>Nota</th>
                <th>Revisión</th>
                <th aria-label="Acciones" />
              </tr>
            </thead>
            <tbody>
              {participantes.map((participante) => {
                const decision = decisionesVigentes.get(participante.student_id)
                return (
                  <tr key={participante.id}>
                    <td>
                      {participante.student_name ? (
                        <>
                          <strong>{participante.student_name}</strong>
                          {participante.student_email && (
                            <p className="ayuda">{participante.student_email}</p>
                          )}
                        </>
                      ) : (
                        <span className="mono">{participante.student_id.slice(0, 8)}</span>
                      )}
                    </td>
                    <td className="hora">
                      {participante.submitted_at ? soloHora(participante.submitted_at) : '—'}
                    </td>
                    <td>
                      <Nota
                        participant={participante}
                        maxScore={maxScore}
                        hasManualQuestions={hayDesarrollos}
                      />
                    </td>
                    <td>
                      <span className="chip chip-programado">
                        {decision ? nombreDecision(decision.decision) : 'Pendiente'}
                      </span>
                    </td>
                    <td>
                      <Link
                        to={`/sesiones/${id}/estudiantes/${participante.student_id}`}
                        className="boton boton-texto"
                      >
                        Revisar
                      </Link>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      {hayDesarrollos && (
        <p className="ayuda" style={{ marginTop: 'var(--e4)' }}>
          Las notas de exámenes con preguntas de desarrollo son parciales hasta que el docente las
          califique.
        </p>
      )}
    </>
  )
}

function Dato({
  valor,
  etiqueta,
  tono
}: {
  valor: string | number
  etiqueta: string
  tono?: 'medium'
}) {
  return (
    <div className="tarjeta dato">
      <p className={`cifra${tono ? ` cifra-${tono}` : ''}`}>{valor}</p>
      <p className="etiqueta">{etiqueta}</p>
    </div>
  )
}

function Nota({
  participant,
  maxScore,
  hasManualQuestions
}: {
  participant: Participant
  maxScore: number
  hasManualQuestions: boolean
}) {
  if (!participant.submitted_at) return <span className="tenue">Sin entregar</span>
  if (participant.score === null) {
    return <span className="chip chip-programado">Pendiente de calificación</span>
  }

  return (
    <>
      <strong>
        {formatearNota(participant.score)} de {formatearNota(maxScore)}
      </strong>
      {hasManualQuestions && (
        <span className="chip chip-programado nota-aviso">Parcial · faltan desarrollos</span>
      )}
    </>
  )
}

function formatearNota(score: number): string {
  return new Intl.NumberFormat('es-PE', { maximumFractionDigits: 2 }).format(score)
}
