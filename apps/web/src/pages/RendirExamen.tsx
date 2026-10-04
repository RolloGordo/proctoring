import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ApiError,
  api,
  type Answer,
  type ExamQuestion,
  type NewAnswer,
  type Participant
} from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { soloHora } from '../lib/formato'

/**
 * Pantalla del examen del estudiante.
 *
 * Dos decisiones importantes:
 *
 * 1. **Se guarda al responder, no al entregar.** Un examen supervisado corre en
 *    un equipo que se puede reiniciar, quedarse sin batería o cerrar la cámara.
 *    Cada cambio viaja a la API, y al volver se recupera lo respondido.
 * 2. **El estado de guardado se muestra.** Si algo no se guardó, el estudiante
 *    tiene que verlo mientras puede hacer algo al respecto, no al entregar.
 */
export function RendirExamen() {
  const { id = '' } = useParams()
  const { token } = useAuth()

  const [preguntas, setPreguntas] = useState<ExamQuestion[]>()
  const [matricula, setMatricula] = useState<Participant>()
  const [respuestas, setRespuestas] = useState<Record<string, NewAnswer>>({})
  const [error, setError] = useState<string>()
  const [guardado, setGuardado] = useState<EstadoGuardado>('limpio')
  const [entregando, setEntregando] = useState(false)

  useEffect(() => {
    let cancelado = false

    Promise.all([
      api.examQuestions(id, token),
      api.myAnswers(id, token),
      api.myEnrollment(id, token)
    ])
      .then(([delExamen, yaRespondidas, mia]) => {
        if (cancelado) return
        setPreguntas(delExamen)
        setRespuestas(indexar(yaRespondidas))
        setMatricula(mia)
      })
      .catch((fallo: Error) => !cancelado && setError(fallo.message))

    return () => {
      cancelado = true
    }
  }, [id, token])

  const guardar = useGuardadoDiferido(id, token, setGuardado, setError)

  const responder = useCallback(
    (respuesta: NewAnswer) => {
      setRespuestas((previas) => ({ ...previas, [respuesta.question_id]: respuesta }))
      setGuardado('guardando')
      guardar(respuesta)
    },
    [guardar]
  )

  async function entregar(): Promise<void> {
    setError(undefined)
    setEntregando(true)
    try {
      setMatricula(await api.submitExam(id, token))
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo entregar')
    } finally {
      setEntregando(false)
    }
  }

  const respondidas = Object.keys(respuestas).length
  const total = preguntas?.length ?? 0

  if (matricula?.submitted_at) return <Entregado cuando={matricula.submitted_at} />
  if (error && !preguntas) return <NoSePuede mensaje={error} />
  if (!preguntas) return <p className="tenue">Cargando examen…</p>

  return (
    <div className="pantalla-examen">
      <div className="barra-examen">
        <div>
          <strong>
            {respondidas} de {total} respondidas
          </strong>
          <p className="ayuda">{textoGuardado(guardado)}</p>
        </div>
        <button
          type="button"
          className="boton"
          onClick={() => void entregar()}
          disabled={entregando || guardado === 'guardando'}
        >
          {entregando ? 'Entregando…' : 'Entregar examen'}
        </button>
      </div>

      {error && <p className="aviso">{error}</p>}

      {total === 0 ? (
        <div className="tarjeta">
          <div className="vacio">
            <h3>Este examen todavía no tiene preguntas</h3>
            <p className="subtitulo">Avísale a tu docente antes de entregar.</p>
          </div>
        </div>
      ) : (
        <ol className="lista-preguntas">
          {preguntas.map((pregunta) => (
            <li key={pregunta.id} className="tarjeta">
              <div className="tarjeta-cuerpo">
                <div className="fila" style={{ justifyContent: 'space-between' }}>
                  <h4>Pregunta {pregunta.position}</h4>
                  <span className="tenue">{pregunta.points} pts</span>
                </div>
                <p className="enunciado">{pregunta.statement}</p>
                <CampoRespuesta
                  pregunta={pregunta}
                  respuesta={respuestas[pregunta.id]}
                  onResponder={responder}
                />
              </div>
            </li>
          ))}
        </ol>
      )}

      <div className="fila" style={{ justifyContent: 'flex-end', marginTop: 'var(--e6)' }}>
        <button
          type="button"
          className="boton"
          onClick={() => void entregar()}
          disabled={entregando || guardado === 'guardando'}
        >
          {entregando ? 'Entregando…' : 'Entregar examen'}
        </button>
      </div>
    </div>
  )
}

function CampoRespuesta({
  pregunta,
  respuesta,
  onResponder
}: {
  pregunta: ExamQuestion
  respuesta: NewAnswer | undefined
  onResponder: (respuesta: NewAnswer) => void
}) {
  if (pregunta.question_type === 'multiple_choice' || pregunta.question_type === 'true_false') {
    return (
      <ul className="opciones-examen">
        {pregunta.options.map((opcion) => (
          <li key={opcion.id}>
            <label>
              <input
                type="radio"
                name={pregunta.id}
                value={opcion.id}
                checked={respuesta?.selected_option_id === opcion.id}
                onChange={() =>
                  onResponder({ question_id: pregunta.id, selected_option_id: opcion.id })
                }
              />
              <span>{opcion.option_text}</span>
            </label>
          </li>
        ))}
      </ul>
    )
  }

  if (pregunta.question_type === 'numeric') {
    return (
      <label className="campo" style={{ maxWidth: '220px', marginBottom: 0 }}>
        <span>Tu respuesta</span>
        <input
          type="number"
          step="any"
          defaultValue={respuesta?.numeric_answer ?? ''}
          // onBlur y no onChange: guardar en cada tecla mandaría "4" cuando el
          // estudiante va escribiendo "42".
          onBlur={(e) => {
            const valor = e.target.value.trim()
            if (valor) onResponder({ question_id: pregunta.id, numeric_answer: valor })
          }}
        />
      </label>
    )
  }

  const largo = pregunta.question_type === 'essay'
  return (
    <label className="campo" style={{ marginBottom: 0 }}>
      <span>Tu respuesta</span>
      {largo ? (
        <textarea
          rows={6}
          maxLength={10000}
          defaultValue={respuesta?.text_answer ?? ''}
          onBlur={(e) => {
            const valor = e.target.value.trim()
            if (valor) onResponder({ question_id: pregunta.id, text_answer: valor })
          }}
        />
      ) : (
        <input
          maxLength={1000}
          defaultValue={respuesta?.text_answer ?? ''}
          onBlur={(e) => {
            const valor = e.target.value.trim()
            if (valor) onResponder({ question_id: pregunta.id, text_answer: valor })
          }}
        />
      )}
    </label>
  )
}

function Entregado({ cuando }: { cuando: string }) {
  return (
    <div className="centrado-estrecho">
      <div className="tarjeta">
        <div className="vacio">
          <h3>Examen entregado</h3>
          <p className="subtitulo">
            {/* "p. m." ya termina en punto: encadenar otro daria "p. m..". */}
            Se registró tu entrega a las {soloHora(cuando)} — ya puedes cerrar la aplicación.
          </p>
          <p className="ayuda" style={{ marginTop: 'var(--e4)' }}>
            Si durante el examen aparecieron avisos de supervisión, los revisa tu docente. El
            sistema no decide nada por su cuenta.
          </p>
        </div>
      </div>
    </div>
  )
}

function NoSePuede({ mensaje }: { mensaje: string }) {
  return (
    <div className="centrado-estrecho">
      <div className="tarjeta">
        <div className="vacio">
          <h3>No puedes entrar al examen</h3>
          <p className="subtitulo">{mensaje}</p>
          <p style={{ marginTop: 'var(--e5)' }}>
            <Link to="/examen" className="boton boton-secundario">
              Volver al inicio
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

type EstadoGuardado = 'limpio' | 'guardando' | 'guardado' | 'error'

function textoGuardado(estado: EstadoGuardado): string {
  switch (estado) {
    case 'guardando':
      return 'Guardando…'
    case 'guardado':
      return 'Guardado'
    case 'error':
      return 'No se pudo guardar tu última respuesta'
    default:
      return 'Tus respuestas se guardan solas'
  }
}

/**
 * Guarda con un pequeño retraso y agrupando.
 *
 * Sin esto, escribir un desarrollo largo dispararía una petición por campo que
 * pierde el foco, y el orden de llegada no está garantizado. Con un lote cada
 * medio segundo la última respuesta siempre es la que queda.
 */
function useGuardadoDiferido(
  sessionId: string,
  token: string | undefined,
  setGuardado: (estado: EstadoGuardado) => void,
  setError: (mensaje: string | undefined) => void
): (respuesta: NewAnswer) => void {
  const pendientes = useRef(new Map<string, NewAnswer>())
  const temporizador = useRef<ReturnType<typeof setTimeout>>(undefined)

  const enviar = useCallback(() => {
    const lote = [...pendientes.current.values()]
    pendientes.current.clear()
    if (lote.length === 0) return

    api
      .saveAnswers(sessionId, lote, token)
      .then(() => {
        setGuardado('guardado')
        setError(undefined)
      })
      .catch((fallo: unknown) => {
        setGuardado('error')
        // Un 403 aquí no es un fallo de red: el examen cerró o ya se entregó, y
        // el estudiante necesita saberlo con esas palabras.
        setError(
          fallo instanceof ApiError
            ? fallo.message
            : 'Se perdió la conexión. Tu última respuesta no se guardó.'
        )
      })
  }, [sessionId, token, setGuardado, setError])

  // Al desmontar se manda lo que quede: cerrar la pestaña no debería perder la
  // respuesta que estaba en el aire.
  useEffect(() => () => enviar(), [enviar])

  return useMemo(() => {
    return (respuesta: NewAnswer) => {
      pendientes.current.set(respuesta.question_id, respuesta)
      clearTimeout(temporizador.current)
      temporizador.current = setTimeout(enviar, 500)
    }
  }, [enviar])
}

function indexar(respuestas: Answer[]): Record<string, NewAnswer> {
  return Object.fromEntries(
    respuestas.map((r) => [
      r.question_id,
      {
        question_id: r.question_id,
        selected_option_id: r.selected_option_id,
        text_answer: r.text_answer,
        numeric_answer: r.numeric_answer
      }
    ])
  )
}
