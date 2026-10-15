import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  api,
  type Answer,
  type ExamQuestion,
  type MyExam,
  type ProctoringEvent
} from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { detalleEvento, duracion, fechaLarga, nombreEvento } from '../lib/formato'

interface Detalle {
  exam: MyExam
  questions: ExamQuestion[]
  answers: Answer[]
  events: ProctoringEvent[]
}

export function DetalleExamenEstudiante() {
  const { id = '' } = useParams()
  const { token } = useAuth()
  const [detalle, setDetalle] = useState<Detalle>()
  const [error, setError] = useState<string>()

  useEffect(() => {
    let cancelado = false

    Promise.all([
      api.myExams(token),
      api.examQuestions(id, token),
      api.myAnswers(id, token),
      api.listEvents(id, token)
    ])
      .then(([exams, questions, answers, events]) => {
        if (cancelado) return
        const exam = exams.find((item) => item.session_id === id)
        if (!exam) {
          setError('No se encontró este examen en tu cuenta.')
          return
        }
        if (!exam.submitted_at) {
          setError('El detalle estará disponible cuando entregues el examen.')
          return
        }
        setDetalle({ exam, questions, answers, events })
      })
      .catch((fallo: Error) => !cancelado && setError(fallo.message))

    return () => {
      cancelado = true
    }
  }, [id, token])

  if (error && !detalle) {
    return (
      <>
        <p className="aviso">{error}</p>
        <Link to="/estudiante" className="boton boton-secundario">
          Volver a mis exámenes
        </Link>
      </>
    )
  }
  if (!detalle) return <p className="tenue">Cargando el detalle…</p>

  const answers = new Map(detalle.answers.map((answer) => [answer.question_id, answer]))

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>{detalle.exam.title}</h1>
          <p className="subtitulo">
            Entregado {detalle.exam.submitted_at ? fechaLarga(detalle.exam.submitted_at) : ''}
          </p>
        </div>
        <Link to="/estudiante" className="boton boton-secundario">
          Volver a mis exámenes
        </Link>
      </div>

      <section className="bloque">
        <h2>Resultado</h2>
        <div className="tarjeta">
          <div className="tarjeta-cuerpo">
            {detalle.exam.score === null ? (
              <p>Pendiente de calificación.</p>
            ) : (
              <p>
                Nota: <strong>{detalle.exam.score}</strong>
                {detalle.exam.max_score !== null && <> de {detalle.exam.max_score}</>}
              </p>
            )}
            {detalle.exam.pending_manual_review && (
              <p className="ayuda">
                La nota es parcial: todavía hay respuestas de desarrollo pendientes de revisión.
              </p>
            )}
          </div>
        </div>
      </section>

      <section className="bloque">
        <h2>Tus respuestas</h2>
        {detalle.questions.length === 0 ? (
          <p className="tenue">No hay preguntas disponibles para mostrar.</p>
        ) : (
          <ol className="lista-preguntas numerada">
            {detalle.questions.map((question) => (
              <li key={question.id} className="tarjeta">
                <div className="tarjeta-cuerpo">
                  <h3>{question.statement}</h3>
                  <p>
                    {respuestaTexto(question, answers.get(question.id)) || 'Sin respuesta'}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
        <p className="ayuda">
          Este resumen muestra tus respuestas, no revela la clave de respuestas correctas.
        </p>
      </section>

      <section className="bloque">
        <h2>Señales registradas durante el examen</h2>
        {detalle.events.length === 0 ? (
          <div className="tarjeta">
            <p className="tarjeta-cuerpo">No hay señales registradas para este examen.</p>
          </div>
        ) : (
          <ul className="lista-alertas">
            {detalle.events.map((event) => (
              <li key={event.id}>
                <span className={`severidad severidad-${event.severity}`}>{event.severity}</span>
                <div>
                  <p className="motivo">{nombreEvento(event.event_type)}</p>
                  <p className="ayuda">
                    {fechaLarga(event.started_at)}
                    {event.duration_ms > 0 ? ` · ${duracion(event.duration_ms)}` : ''}
                    {detalleEvento(event.metadata) ? ` · ${detalleEvento(event.metadata)}` : ''}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
        <p className="ayuda">
          Una señal no es una decisión de sanción. El docente revisa la evidencia y decide.
        </p>
      </section>
    </>
  )
}

function respuestaTexto(question: ExamQuestion, answer: Answer | undefined): string {
  if (!answer) return ''
  if (answer.selected_option_id) {
    return (
      question.options.find((option) => option.id === answer.selected_option_id)?.option_text ??
      'Opción seleccionada'
    )
  }
  return answer.numeric_answer ?? answer.text_answer ?? ''
}
