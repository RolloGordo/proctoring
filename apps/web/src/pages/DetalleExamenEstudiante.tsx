import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  api,
  type Answer,
  type Decision,
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
  decision: Decision | null
}

/** Cómo se le cuenta al estudiante lo que su docente decidió. */
const TEXTO_DECISION: Record<Decision['decision'], { titulo: string; detalle: string }> = {
  dismissed: {
    titulo: 'Tu docente revisó las señales y no encontró infracción',
    detalle: 'El examen queda como está.'
  },
  confirmed: {
    titulo: 'Tu docente revisó las señales y confirmó una infracción',
    detalle: 'Si no estás de acuerdo, habla con tu docente: esta es su justificación.'
  },
  retake: {
    titulo: 'Tu docente decidió que repitas el examen',
    detalle: 'No es una sanción: se te da otra oportunidad.'
  }
}

export function DetalleExamenEstudiante() {
  const { id = '' } = useParams()
  const { token } = useAuth()
  const [detalle, setDetalle] = useState<Detalle>()
  const [error, setError] = useState<string>()

  useEffect(() => {
    let cancelado = false

    // `submittedExamQuestions`, no `examQuestions`: el segundo se cierra cuando
    // pasa la hora del examen, así que entrar aquí a un examen terminado —que es
    // justo cuando se quiere repasar— respondía «El examen no está abierto en
    // este momento» y tumbaba la pantalla entera.
    Promise.all([
      api.myExams(token),
      api.submittedExamQuestions(id, token),
      api.myAnswers(id, token),
      api.listEvents(id, token),
      api.myDecision(id, token)
    ])
      .then(([exams, questions, answers, events, decision]) => {
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
        setDetalle({ exam, questions, answers, events, decision })
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

      {detalle.decision && (
        <section className="bloque">
          <h2>Lo que decidió tu docente</h2>
          <div className="tarjeta">
            <div className="tarjeta-cuerpo">
              <h3>{TEXTO_DECISION[detalle.decision.decision].titulo}</h3>
              <p>{TEXTO_DECISION[detalle.decision.decision].detalle}</p>
              <blockquote className="justificacion">
                {detalle.decision.justification}
              </blockquote>
              <p className="ayuda">
                Decidido el {fechaLarga(detalle.decision.decided_at)}. El sistema no decide por
                su cuenta: reúne evidencia y la revisa una persona, que tiene que justificar por
                escrito lo que resuelve.
              </p>
            </div>
          </div>
        </section>
      )}

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
  if (answer.selected_option_ids?.length) {
    // En el orden de la pregunta, no en el que se marcaron: el estudiante la
    // vuelve a leer como la vio.
    return question.options
      .filter((option) => answer.selected_option_ids.includes(option.id))
      .map((option) => option.option_text)
      .join(' · ')
  }
  if (answer.selected_option_id) {
    return (
      question.options.find((option) => option.id === answer.selected_option_id)?.option_text ??
      'Opción seleccionada'
    )
  }
  return answer.numeric_answer ?? answer.text_answer ?? ''
}
