import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  api,
  type Decision,
  type ExamSession,
  type Participant,
  type Question,
  type RiskLevel,
  type StudentRisk
} from '../lib/api'
import { FiltroCorreo, SinCoincidencias, VerMas } from '../components/ControlesLista'
import { useAuth } from '../lib/auth-context'
import { fechaLarga, formatearNota, nombreDecision, nombreEvento, soloHora } from '../lib/formato'
import { useListaAcotada } from '../lib/lista-acotada'
import { latestDecisionByStudent, summarizeResults } from '../lib/resultados'

export function Resultados() {
  const { id = '' } = useParams()
  const { token } = useAuth()
  const [participantes, setParticipantes] = useState<Participant[]>()
  const [decisiones, setDecisiones] = useState<Decision[]>()
  const [sesion, setSesion] = useState<ExamSession>()
  const [preguntas, setPreguntas] = useState<Question[]>()
  const [riesgos, setRiesgos] = useState<StudentRisk[]>()
  const [nivel, setNivel] = useState<RiskLevel | 'todos'>('todos')
  const [error, setError] = useState<string>()

  useEffect(() => {
    let cancelado = false
    Promise.all([
      api.listParticipants(id, token),
      api.listDecisions(id, token),
      api.getSession(id, token),
      api.listQuestions(id, token),
      api.listSessionRisk(id, token)
    ])
      .then(([datosParticipantes, datosDecisiones, datosSesion, datosPreguntas, datosRiesgo]) => {
        if (cancelado) return
        setParticipantes(datosParticipantes)
        setDecisiones(datosDecisiones)
        setSesion(datosSesion)
        setPreguntas(datosPreguntas)
        setRiesgos(datosRiesgo)
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
  const riesgoPorAlumno = useMemo(
    () => new Map((riesgos ?? []).map((riesgo) => [riesgo.student_id, riesgo])),
    [riesgos]
  )
  // De más a menos sospechoso: el docente empieza por los rojos y descarta los verdes.
  const ordenados = useMemo(
    () =>
      [...(participantes ?? [])]
        .filter((p) => nivel === 'todos' || nivelDe(riesgoPorAlumno.get(p.student_id)) === nivel)
        .sort(
          (a, b) =>
            (riesgoPorAlumno.get(b.student_id)?.score ?? 0) -
            (riesgoPorAlumno.get(a.student_id)?.score ?? 0)
        ),
    [participantes, riesgoPorAlumno, nivel]
  )
  const lista = useListaAcotada(
    ordenados,
    (p) => `${p.student_email ?? ''} ${p.student_name ?? ''}`
  )
  const conteo = useMemo(() => {
    const cuenta: Record<RiskLevel, number> = { high: 0, medium: 0, low: 0 }
    for (const p of participantes ?? []) cuenta[nivelDe(riesgoPorAlumno.get(p.student_id))] += 1
    return cuenta
  }, [participantes, riesgoPorAlumno])

  if (error) return <p className="aviso">{error}</p>
  if (!participantes || !decisiones || !sesion || !preguntas || !riesgos || !resumen) {
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
            Participantes
          </Link>
        </div>
      </div>

      <div className="panel-resumen">
        <Dato valor={resumen.submittedCount} etiqueta="Entregaron" />
        <Dato valor={notaMedia} etiqueta="Nota media" />
        <Dato valor={resumen.pendingReviewCount} etiqueta="Casos por revisar" tono="medium" />
        <Dato valor={conteo.high} etiqueta="En rojo" tono="high" />
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
          <div className="controles-lista">
            <FiltroCorreo valor={lista.filtro} onCambio={lista.setFiltro} />
            <div className="filtro-nivel" role="group" aria-label="Filtrar por nivel de riesgo">
              {(['todos', 'high', 'medium', 'low'] as const).map((opcion) => (
                <button
                  key={opcion}
                  type="button"
                  aria-pressed={nivel === opcion}
                  className={opcion === 'todos' ? 'semaforo' : `semaforo semaforo-${opcion}`}
                  onClick={() => setNivel(opcion)}
                >
                  {opcion === 'todos'
                    ? `Todos (${participantes.length})`
                    : `${NOMBRE_SEMAFORO[opcion]} (${conteo[opcion]})`}
                </button>
              ))}
            </div>
          </div>
          {lista.visibles.length === 0 && <SinCoincidencias filtro={lista.filtro} />}
          <table className="tabla">
            <thead>
              <tr>
                <th>Riesgo</th>
                <th>Estudiante</th>
                <th className="numero">Nota</th>
                <th>Entregado</th>
                <th>Revisión</th>
                <th aria-label="Acciones" />
              </tr>
            </thead>
            <tbody>
              {lista.visibles.map((participante) => {
                const decision = decisionesVigentes.get(participante.student_id)
                return (
                  <tr key={participante.id}>
                    <td>
                      <Semaforo riesgo={riesgoPorAlumno.get(participante.student_id)} />
                    </td>
                    <td>
                      {participante.student_name ? (
                        <>
                          {/* El nombre lleva a su revisión, donde la nota va en grande. */}
                          <Link
                            to={`/sesiones/${id}/estudiantes/${participante.student_id}`}
                            className="resultados-nombre"
                          >
                            {participante.student_name}
                          </Link>
                          {participante.student_email && (
                            <p className="ayuda">{participante.student_email}</p>
                          )}
                        </>
                      ) : (
                        <span className="mono">{participante.student_id.slice(0, 8)}</span>
                      )}
                    </td>
                    <td className="numero">
                      <Nota
                        participant={participante}
                        maxScore={maxScore}
                        hasManualQuestions={hayDesarrollos}
                      />
                    </td>
                    <td className="hora">
                      {participante.submitted_at ? soloHora(participante.submitted_at) : '—'}
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
          <VerMas restantes={lista.restantes} onClick={lista.verMas} />
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

const NOMBRE_SEMAFORO: Record<RiskLevel, string> = {
  high: 'Rojo',
  medium: 'Amarillo',
  low: 'Verde'
}

function nivelDe(riesgo: StudentRisk | undefined): RiskLevel {
  return riesgo?.level ?? 'low'
}

/** Verde, amarillo o rojo según el riesgo calculado. Orienta, no sentencia. */
function Semaforo({ riesgo }: { riesgo: StudentRisk | undefined }) {
  const nivel = nivelDe(riesgo)
  const detalle = riesgo?.top_signal
    ? `${riesgo.signal_count} señales · sobre todo ${nombreEvento(riesgo.top_signal).toLowerCase()}`
    : 'Sin señales'
  return (
    <span className={`semaforo semaforo-${nivel}`} title={detalle}>
      {NOMBRE_SEMAFORO[nivel]} · {riesgo?.score ?? 0}
    </span>
  )
}

function Dato({
  valor,
  etiqueta,
  tono
}: {
  valor: string | number
  etiqueta: string
  tono?: 'medium' | 'high'
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
    <span className="resultados-nota">
      <strong>{formatearNota(participant.score)}</strong>
      <span className="tenue"> / {formatearNota(maxScore)}</span>
      {hasManualQuestions && (
        <span className="chip chip-programado nota-aviso">Parcial · faltan desarrollos</span>
      )}
    </span>
  )
}
