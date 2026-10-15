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
import { formatRemainingTime, unansweredCount } from '../lib/exam-progress'
import { soloHora } from '../lib/formato'
import { detectoresDe, necesitaAudio } from '../supervision/detectores'
import type { AjustesMonitoreo } from '../supervision/monitoreo'
import { useSupervision } from '../supervision/useSupervision'
import { AvisoSupervision } from '../components/AvisoSupervision'
import type { AvisoSupervision as DatosAviso } from '../supervision/avisos'

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
  const { token, userId } = useAuth()

  const [preguntas, setPreguntas] = useState<ExamQuestion[]>()
  const [matricula, setMatricula] = useState<Participant>()
  const [finExamen, setFinExamen] = useState<string>()
  const [modulosActivos, setModulosActivos] = useState<Record<string, Record<string, unknown>>>({})
  const [respuestas, setRespuestas] = useState<Record<string, NewAnswer>>({})
  const [error, setError] = useState<string>()
  const [guardado, setGuardado] = useState<EstadoGuardado>('limpio')
  const [entregando, setEntregando] = useState(false)
  const [observado, setObservado] = useState(false)
  const [conectado, setConectado] = useState(() => navigator.onLine)
  const [ahora, setAhora] = useState(() => Date.now())
  const [aviso, setAviso] = useState<DatosAviso | null>(null)
  const [reintentoCamara, setReintentoCamara] = useState(0)
  const vistaPrevia = useRef<HTMLVideoElement>(null)
  const streamActual = useRef<MediaStream | null>(null)
  // Se reutiliza el stream de supervisión; NO se abre una segunda cámara.
  const mostrarCamara = useCallback((stream: MediaStream | null) => {
    streamActual.current = stream
    if (vistaPrevia.current) {
      vistaPrevia.current.srcObject = stream
      if (stream) void vistaPrevia.current.play().catch(() => undefined)
    }
  }, [])
  const asociarVistaPrevia = useCallback((video: HTMLVideoElement | null) => {
    vistaPrevia.current = video
    if (video) {
      video.srcObject = streamActual.current
      if (streamActual.current) void video.play().catch(() => undefined)
    }
  }, [])
  // En que pregunta esta. El examen va de una en una: es la unica forma de que
  // "no volver atras" signifique algo, y ademas es lo que deja saber **cual**
  // es la pregunta en curso cuando se registra un evento.
  const [enCurso, setEnCurso] = useState(0)
  const [volverAtras, setVolverAtras] = useState(true)

  useEffect(() => {
    let cancelado = false

    Promise.all([
      api.examQuestions(id, token),
      api.myAnswers(id, token),
      api.myEnrollment(id, token),
      api.myExams(token)
    ])
      .then(([delExamen, yaRespondidas, mia, misExamenes]) => {
        if (cancelado) return
        const previas = indexar(yaRespondidas)
        setPreguntas(delExamen)
        setRespuestas(previas)
        setMatricula(mia)
        const mio = misExamenes.find((e) => e.session_id === id)
        setFinExamen(mio?.ends_at)
        setModulosActivos(mio?.modules ?? {})
        setVolverAtras(mio?.allow_back_navigation ?? true)
        // Al retomar, se sigue en la primera sin responder y no en la uno.
        const sinResponder = delExamen.findIndex((p) => !(p.id in previas))
        setEnCurso(sinResponder === -1 ? Math.max(delExamen.length - 1, 0) : sinResponder)
      })
      .catch((fallo: Error) => !cancelado && setError(fallo.message))

    return () => {
      cancelado = true
    }
  }, [id, token])

  const { guardar, reintentarGuardado } = useGuardadoDiferido(id, token, setGuardado, setError)

  useEffect(() => {
    const alConectar = (): void => {
      setConectado(true)
      if (guardado === 'error') reintentarGuardado()
    }
    const alDesconectar = (): void => setConectado(false)
    window.addEventListener('online', alConectar)
    window.addEventListener('offline', alDesconectar)
    return () => {
      window.removeEventListener('online', alConectar)
      window.removeEventListener('offline', alDesconectar)
    }
  }, [guardado, reintentarGuardado])

  useEffect(() => {
    const temporizador = setInterval(() => setAhora(Date.now()), 1000)
    return () => clearInterval(temporizador)
  }, [])

  // La supervisión se enciende aquí y no antes: el consentimiento se da en la
  // sala, y observar a alguien que todavía no aceptó sería justo lo que el
  // proyecto promete no hacer.
  const detectores = useMemo(
    () => detectoresDe(matricula ? modulosActivos : {}),
    [matricula, modulosActivos]
  )
  // El módulo de monitoreo en vivo no es un detector: no emite eventos, solo
  // deja que el docente mire. Va aparte por eso.
  const monitoreo = useMemo<AjustesMonitoreo | null>(
    () => (matricula ? ((modulosActivos.live_monitoring as AjustesMonitoreo) ?? null) : null),
    [matricula, modulosActivos]
  )
  const supervision = useSupervision({
    sessionId: id,
    studentId: userId,
    // La pregunta que tiene delante. Importa de verdad: es contra este
    // enunciado contra el que el servicio de IA compara lo que el estudiante
    // dice en voz alta, y con la pregunta equivocada esa comparación no vale.
    questionId: preguntas?.[enCurso]?.id ?? null,
    token,
    detectores,
    conAudio: necesitaAudio(detectores),
    monitoreo,
    onObservado: setObservado,
    onAviso: setAviso,
    onCamara: mostrarCamara,
    reintento: reintentoCamara,
    activa: matricula?.submitted_at == null
  })

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
    const faltantes = unansweredCount(total, respondidas)
    const confirmacion =
      faltantes === 0
        ? '¿Quieres entregar el examen? Ya respondiste todas las preguntas.'
        : `Te quedan ${faltantes} pregunta${faltantes === 1 ? '' : 's'} sin responder. ¿Quieres entregar el examen de todas formas?`
    if (!window.confirm(confirmacion)) return
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
  const faltantes = unansweredCount(total, respondidas)
  const actual = preguntas?.[enCurso]
  const restante = finExamen ? Math.max(0, new Date(finExamen).getTime() - ahora) : undefined
  // Sin volver atras, una respuesta enviada ya no se cambia: la API la rechaza,
  // asi que el campo se deshabilita en vez de dejar que lo descubra chocandose.
  const bloqueada = !volverAtras && actual !== undefined && actual.id in respuestas

  if (matricula?.submitted_at) return <Entregado cuando={matricula.submitted_at} />
  if (error && !preguntas) return <NoSePuede mensaje={error} />
  if (!preguntas) return <p className="tenue">Cargando examen…</p>

  return (
    <div className="pantalla-examen">
      <AvisoSupervision aviso={aviso} onCerrar={() => setAviso(null)} />
      <div className="barra-examen">
        <div>
          <strong>
            Pregunta {total > 0 ? enCurso + 1 : 0} de {total}
          </strong>
          <p className="ayuda">
            {respondidas} respondidas · {faltantes} sin responder
          </p>
          <p className="ayuda">{textoGuardado(guardado)}</p>
          {restante !== undefined && (
            <p className="ayuda">
              {restante === 0 ? (
                <strong>El tiempo del examen terminó</strong>
              ) : (
                <>
                  Tiempo restante: <strong>{formatRemainingTime(restante)}</strong>
                </>
              )}
            </p>
          )}
        </div>
        <button
          type="button"
          className="boton"
          onClick={() => void entregar()}
          disabled={entregando || guardado === 'guardando' || guardado === 'error' || !conectado}
        >
          {entregando ? 'Entregando…' : 'Entregar examen'}
        </button>
      </div>

      {!conectado && (
        <p className="aviso">
          Sin conexión. Las respuestas guardadas anteriormente permanecen en el servidor, pero los
          cambios recientes no se guardarán hasta recuperar la conexión.
        </p>
      )}
      {guardado === 'error' && (
        <p className="aviso">
          No se guardó la última respuesta. Comprueba la conexión y vuelve a intentarlo.
          <button
            type="button"
            className="boton boton-secundario"
            onClick={reintentarGuardado}
            disabled={!conectado}
            style={{ marginLeft: 'var(--e3)' }}
          >
            Reintentar guardado
          </button>
        </p>
      )}

      {supervision.tipo === 'activa' && (
        <div className="indicador-camara-examen" aria-label="Cámara activa durante el examen">
          <video ref={asociarVistaPrevia} muted playsInline autoPlay aria-label="Mi cámara activa" />
          <span>● Cámara activa</span>
        </div>
      )}

      {observado && (
        <p className="aviso aviso-neutro">
          Tu docente está viendo tu cámara en este momento. No se está grabando: la imagen se
          muestra y se descarta.
        </p>
      )}

      {supervision.tipo === 'fallo' && (
        <p className="aviso aviso-neutro">
          {supervision.mensaje} Puedes seguir rindiendo: quedará registrado que la supervisión no se
          pudo activar, y tu docente lo verá al revisar.
          <button type="button" className="boton boton-secundario" onClick={() => setReintentoCamara((n) => n + 1)}>
            Reintentar cámara
          </button>
        </p>
      )}

      {error && <p className="aviso">{error}</p>}

      {total === 0 ? (
        <div className="tarjeta">
          <div className="vacio">
            <h3>Este examen todavía no tiene preguntas</h3>
            <p className="subtitulo">Avísale a tu docente antes de entregar.</p>
          </div>
        </div>
      ) : (
        <>
          <div className="tarjeta">
            <div className="tarjeta-cuerpo">
              <div className="fila" style={{ justifyContent: 'space-between' }}>
                <h4>
                  Pregunta {enCurso + 1} de {total}
                </h4>
                <span className="tenue">{actual?.points} pts</span>
              </div>
              {actual && (
                <>
                  <p className="enunciado">{actual.statement}</p>
                  <CampoRespuesta
                    pregunta={actual}
                    respuesta={respuestas[actual.id]}
                    onResponder={responder}
                    bloqueada={bloqueada}
                  />
                </>
              )}
              {bloqueada && (
                <p className="ayuda">Ya respondiste esta pregunta y este examen no deja volver.</p>
              )}
            </div>
          </div>

          <div className="navegacion-examen">
            {volverAtras ? (
              <button
                type="button"
                className="boton boton-secundario"
                onClick={() => setEnCurso((n) => Math.max(n - 1, 0))}
                disabled={enCurso === 0}
              >
                Anterior
              </button>
            ) : (
              // Solo mientras todavia se pueda responder: una vez bloqueada, lo
              // dice la propia pregunta y repetirlo aqui sobra.
              <p className="ayuda" style={{ margin: 0 }}>
                {bloqueada ? '' : 'Este examen no permite volver a una pregunta ya respondida.'}
              </p>
            )}

            {enCurso < total - 1 ? (
              <button
                type="button"
                className="boton"
                onClick={() => setEnCurso((n) => Math.min(n + 1, total - 1))}
              >
                Siguiente
              </button>
            ) : (
              <button
                type="button"
                className="boton"
                onClick={() => void entregar()}
                disabled={entregando || guardado === 'guardando'}
              >
                {entregando ? 'Entregando…' : 'Entregar examen'}
              </button>
            )}
          </div>
        </>
      )}
    </div>
  )
}

function CampoRespuesta({
  pregunta,
  respuesta,
  onResponder,
  bloqueada = false
}: {
  pregunta: ExamQuestion
  respuesta: NewAnswer | undefined
  onResponder: (respuesta: NewAnswer) => void
  /** Ya respondida en un examen que no deja volver: se ve, no se cambia. */
  bloqueada?: boolean
}) {
  if (pregunta.question_type === 'multiple_choice' || pregunta.question_type === 'true_false') {
    return (
      <ul className="opciones-examen">
        {pregunta.options.map((opcion) => (
          <li key={opcion.id}>
            <label>
              <input
                type="radio"
                disabled={bloqueada}
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
          disabled={bloqueada}
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
          disabled={bloqueada}
          maxLength={10000}
          defaultValue={respuesta?.text_answer ?? ''}
          onBlur={(e) => {
            const valor = e.target.value.trim()
            if (valor) onResponder({ question_id: pregunta.id, text_answer: valor })
          }}
        />
      ) : (
        <input
          disabled={bloqueada}
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
): { guardar: (respuesta: NewAnswer) => void; reintentarGuardado: () => void } {
  const pendientes = useRef(new Map<string, NewAnswer>())
  const temporizador = useRef<ReturnType<typeof setTimeout>>(undefined)
  const guardando = useRef(false)

  const enviar = useCallback(async () => {
    if (guardando.current) return
    const lote = [...pendientes.current.values()]
    pendientes.current.clear()
    if (lote.length === 0) return

    guardando.current = true
    setGuardado('guardando')
    setError(undefined)
    try {
      await api.saveAnswers(sessionId, lote, token)
      setGuardado(pendientes.current.size > 0 ? 'guardando' : 'guardado')
      setError(undefined)
    } catch (fallo: unknown) {
      for (const respuesta of lote) {
        if (!pendientes.current.has(respuesta.question_id)) {
          pendientes.current.set(respuesta.question_id, respuesta)
        }
      }
      setGuardado('error')
      // Un 403 aquí no es un fallo de red: el examen cerró o ya se entregó, y
      // el estudiante necesita saberlo con esas palabras.
      setError(
        fallo instanceof ApiError
          ? fallo.message
          : 'Se perdió la conexión. Tu última respuesta no se guardó.'
      )
    } finally {
      guardando.current = false
    }
  }, [sessionId, token, setGuardado, setError])

  // Al desmontar se manda lo que quede: cerrar la pestaña no debería perder la
  // respuesta que estaba en el aire.
  useEffect(
    () => () => {
      void enviar()
    },
    [enviar]
  )

  const guardar = useCallback(
    (respuesta: NewAnswer) => {
      pendientes.current.set(respuesta.question_id, respuesta)
      clearTimeout(temporizador.current)
      temporizador.current = setTimeout(enviar, 500)
    },
    [enviar]
  )

  const reintentarGuardado = useCallback(() => {
    clearTimeout(temporizador.current)
    void enviar()
  }, [enviar])

  return { guardar, reintentarGuardado }
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
