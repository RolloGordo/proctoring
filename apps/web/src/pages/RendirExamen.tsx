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
import { ColaDeGuardado } from '../lib/cola-de-guardado'
import { soloHora } from '../lib/formato'
import { detectoresDe, necesitaAudio } from '../supervision/detectores'
import { loadCalibration } from '../supervision/calibration'
import type { AjustesMonitoreo } from '../supervision/monitoreo'
import { useSupervision } from '../supervision/useSupervision'
import { AvisoSupervision } from '../components/AvisoSupervision'
import { GestorDeAvisos, type AvisoVisible } from '../supervision/avisos'
import { recordNetworkDiagnostic } from '../supervision/diagnostics'
import { supabase } from '../lib/supabase'

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
  /** Módulos de supervisión que no arrancaron. Se le dice al estudiante. */
  const [entregando, setEntregando] = useState(false)
  const [observado, setObservado] = useState(false)
  const [conectado, setConectado] = useState(() => navigator.onLine)
  const desconexionInicio = useRef<number | null>(null)
  const [ahora, setAhora] = useState(() => Date.now())
  // El gestor decide cuando se ve un aviso: silencia la repeticion, junta lo
  // simultaneo y lo retira solo. Vive en un ref para que no se reinicie en
  // cada renderizado y pierda lo que ya habia silenciado.
  const [aviso, setAviso] = useState<AvisoVisible | null>(null)
  const gestorAvisos = useRef<GestorDeAvisos>(undefined)
  gestorAvisos.current ??= new GestorDeAvisos()
  useEffect(() => {
    const gestor = gestorAvisos.current
    const quitar = gestor?.suscribir(setAviso)
    return () => {
      quitar?.()
      gestor?.destruir()
    }
  }, [])
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

  // Electron captura estos atajos en el proceso principal. En navegador web
  // normal no existe ese proceso, asi que los registramos aqui y los asociamos
  // directamente con el alumno autenticado y la pregunta visible.
  useEffect(() => {
    if (
      window.api ||
      !modulosActivos.copy_paste_block ||
      !userId ||
      matricula?.submitted_at != null
    ) return
    const estudianteId = userId

    function capturarAtajo(evento: KeyboardEvent): void {
      if (evento.repeat) return
      const tecla = evento.key.toLowerCase()
      const conModificador = evento.ctrlKey || evento.metaKey
      const copiar = (tecla === 'c' && (conModificador || evento.altKey)) ||
        (tecla === 'insert' && evento.ctrlKey)
      const portapapeles = (conModificador && ['c', 'v', 'x'].includes(tecla)) ||
        (evento.ctrlKey && tecla === 'insert') ||
        (evento.shiftKey && tecla === 'insert')

      if (portapapeles) evento.preventDefault()
      if (!copiar) return

      const atajo = tecla === 'insert'
        ? 'Ctrl+Insert'
        : evento.metaKey
          ? 'Cmd+C'
          : evento.altKey && !evento.ctrlKey
            ? 'Alt+C'
            : 'Ctrl+C'

      void api.registerEvent(
        {
          session_id: id,
          student_id: estudianteId,
          question_id: preguntas?.[enCurso]?.id ?? null,
          event_type: 'copy_attempt',
          started_at: new Date().toISOString(),
          duration_ms: 0,
          metadata: { source: 'browser_input', shortcut: atajo },
          evidence_path: null
        },
        token
      ).catch((fallo: unknown) => {
        console.error('[supervision] no se pudo registrar el atajo de copia', fallo)
      })
    }

    window.addEventListener('keydown', capturarAtajo, true)
    return () => window.removeEventListener('keydown', capturarAtajo, true)
  }, [id, userId, token, modulosActivos, matricula?.submitted_at, preguntas, enCurso])

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
        const previas = {
          ...indexar(yaRespondidas),
          ...Object.fromEntries(
            respuestasLocales(id, userId ?? null).map((answer) => [answer.question_id, answer])
          )
        }
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

  const { guardar, reintentarGuardado, vaciarPendientes, limpiarPendientes } = useGuardadoDiferido(
    id,
    token,
    userId ?? null,
    setGuardado,
    setError
  )

  useEffect(() => {
    let cancelado = false
    let comprobando = false
    const registrar = (code: 'network_disconnected' | 'network_reconnected', durationMs?: number) => {
      if (!userId) return
      void recordNetworkDiagnostic(supabase, {
        session_id: id,
        student_id: userId,
        code,
        occurred_at: new Date().toISOString(),
        module: 'network',
        details: {
          occurred_at: new Date().toISOString(),
          ...(durationMs === undefined ? {} : { duration_ms: durationMs })
        }
      })
    }
    const perderConexion = () => {
      if (desconexionInicio.current !== null) return
      desconexionInicio.current = Date.now()
      setConectado(false)
      registrar('network_disconnected')
    }
    const comprobar = async () => {
      if (comprobando || !navigator.onLine) {
        if (!navigator.onLine) perderConexion()
        return
      }
      comprobando = true
      const apiDisponible = await api.probe()
      let supabaseDisponible = true
      if (apiDisponible && supabase && userId) {
        const { error: falloSupabase } = await supabase
          .from('profiles')
          .select('id')
          .eq('id', userId)
          .limit(1)
          .abortSignal(AbortSignal.timeout(1500))
        supabaseDisponible = !falloSupabase
      }
      comprobando = false
      if (cancelado) return
      if (!apiDisponible || !supabaseDisponible) {
        perderConexion()
        return
      }
      if (desconexionInicio.current !== null) {
        const duracion = Date.now() - desconexionInicio.current
        desconexionInicio.current = null
        registrar('network_reconnected', duracion)
        reintentarGuardado()
      }
      setConectado(true)
      reintentarGuardado()
    }
    const alDesconectar = () => perderConexion()
    window.addEventListener('online', comprobar)
    window.addEventListener('offline', alDesconectar)
    void comprobar()
    const temporizador = window.setInterval(() => void comprobar(), 2000)
    return () => {
      cancelado = true
      window.clearInterval(temporizador)
      window.removeEventListener('online', comprobar)
      window.removeEventListener('offline', alDesconectar)
    }
  }, [id, userId, reintentarGuardado])

  useEffect(() => {
    const temporizador = setInterval(() => setAhora(Date.now()), 1000)
    return () => clearInterval(temporizador)
  }, [])

  useEffect(() => {
    if (conectado) return
    document.getSelection()?.removeAllRanges()
    const bloquearAtajo = (event: KeyboardEvent): void => {
      const tecla = event.key.toLowerCase()
      if ((event.ctrlKey || event.metaKey) && ['a', 'c', 'x', 'v'].includes(tecla)) {
        event.preventDefault()
        event.stopImmediatePropagation()
      }
    }
    const bloquearPortapapeles = (event: Event): void => {
      event.preventDefault()
      event.stopImmediatePropagation()
    }
    window.addEventListener('keydown', bloquearAtajo, true)
    window.addEventListener('copy', bloquearPortapapeles, true)
    window.addEventListener('cut', bloquearPortapapeles, true)
    window.addEventListener('paste', bloquearPortapapeles, true)
    window.addEventListener('contextmenu', bloquearPortapapeles, true)
    return () => {
      window.removeEventListener('keydown', bloquearAtajo, true)
      window.removeEventListener('copy', bloquearPortapapeles, true)
      window.removeEventListener('cut', bloquearPortapapeles, true)
      window.removeEventListener('paste', bloquearPortapapeles, true)
      window.removeEventListener('contextmenu', bloquearPortapapeles, true)
    }
  }, [conectado])

  // La supervisión se enciende aquí y no antes: el consentimiento se da en la
  // sala, y observar a alguien que todavía no aceptó sería justo lo que el
  // proyecto promete no hacer.
  const detectores = useMemo(() => {
    if (!matricula) return detectoresDe({})
    const config = { ...modulosActivos }
    // El umbral calibrado de este estudiante manda sobre el del examen, pero
    // solo hacia arriba: calibrar puede hacer la supervisión más tolerante con
    // su pantalla, nunca más estricta de lo que el docente configuró.
    if (config.gaze && userId) {
      const calibracion = loadCalibration(id, userId)
      config.gaze = {
        ...config.gaze,
        yaw_degrees: calibracion
          ? Math.max(Number(config.gaze.yaw_degrees) || 25, calibracion.thresholdDeg)
          : config.gaze.yaw_degrees,
        yaw_baseline_deg: calibracion?.baselineYawDeg ?? 0,
        // Línea base y umbral de los ojos medidos en la calibración (Jesús).
        // Sin calibrar quedan los del detector.
        ...(calibracion?.eyeDownThreshold !== undefined && {
          eye_down_threshold: Math.max(
            Number(config.gaze.eye_down_threshold) || 0,
            calibracion.eyeDownThreshold
          ),
          eye_down_baseline: calibracion.baselineEyeDown,
          eye_blink_baseline: calibracion.baselineEyeBlink
        }),
        // Queda registrado si se calibró o no: una señal de mirada sin calibrar
        // vale menos, y el docente tiene que poder saberlo al revisar.
        calibration_status: calibracion ? 'calibrated' : 'default'
      }
    }
    return detectoresDe(config)
  }, [matricula, modulosActivos, id, userId])
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
    onAviso: (a) => gestorAvisos.current?.registrar(a),
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
    if (!conectado || !navigator.onLine) return
    setError(undefined)
    setEntregando(true)

    // Antes de entregar se intenta salvar lo que quede en el aire. Si no se
    // consigue, **se entrega igual**: perder un examen porque un guardado
    // falló hace un minuto es mucho peor que entregarlo con una respuesta
    // menos, y el estudiante decide sabiendo lo que pasa.
    let todoGuardado = true
    try {
      todoGuardado = await vaciarPendientes()
    } catch {
      todoGuardado = false
    } finally {
      setEntregando(false)
    }

    // La conexión pudo caer mientras esperábamos el último guardado.
    if (!navigator.onLine || !(await api.probe())) {
      setConectado(false)
      return
    }

    const faltantes = unansweredCount(total, respondidas)
    const sobreFaltantes =
      faltantes === 0
        ? '¿Quieres entregar el examen? Ya respondiste todas las preguntas.'
        : `Te quedan ${faltantes} pregunta${faltantes === 1 ? '' : 's'} sin responder. ¿Quieres entregar el examen de todas formas?`
    const confirmacion = todoGuardado
      ? sobreFaltantes
      : 'No se pudo guardar tu última respuesta y puede perderse. ' +
        '¿Quieres entregar el examen de todas formas?'
    if (!window.confirm(confirmacion)) return
    setEntregando(true)
    try {
      const entregada = await api.submitExam(id, token)
      limpiarPendientes()
      setMatricula(entregada)
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

  if (matricula?.submitted_at)
    return <Entregado cuando={matricula.submitted_at} sessionId={id} />
  if (!conectado) return <PantallaReconectando />
  if (error && !preguntas) return <NoSePuede mensaje={error} />
  if (!preguntas) return <p className="tenue">Cargando examen…</p>

  return (
    <div className="pantalla-examen">
      <AvisoSupervision aviso={aviso} onCerrar={() => gestorAvisos.current?.descartar()} />
      <div className="barra-examen">
        <div>
          <strong>
            Pregunta {total > 0 ? enCurso + 1 : 0} de {total}
          </strong>
          <p className="ayuda">
            {respondidas} {respondidas === 1 ? 'respondida' : 'respondidas'} · {faltantes} sin responder
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
          // Secundario: siempre a mano, pero sin competir con «Siguiente». En
          // la última pregunta el botón principal de abajo ya es entregar.
          className="boton boton-secundario"
          onClick={() => void entregar()}
          // Solo mientras se entrega. Bloquearlo por un guardado fallido o por
          // `navigator.onLine` dejaba al estudiante sin poder entregar por un
          // corte de red de hace un minuto, que es la peor forma de fallar que
          // tiene esta pantalla.
          disabled={entregando}
        >
          {entregando ? 'Entregando…' : 'Entregar examen'}
        </button>
      </div>

      {supervision.tipo === 'degradada' && (
        <div className="aviso aviso-neutro" role="status">
          <p>
            <strong>
              {supervision.fallidos.length === 1
                ? 'Un módulo de supervisión no está activo'
                : 'Hay módulos de supervisión que no están activos'}
              : {supervision.fallidos.join(', ')}.
            </strong>
          </p>
          <p className="ayuda">
            Puedes seguir rindiendo. No es una infracción y no se te atribuye a ti, pero tu
            docente verá que ese módulo no estuvo activo durante el examen.
          </p>
        </div>
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

      {/*
        Se ensena mientras la supervision este encendida, aunque algo vaya mal.
        Estaba condicionado a `=== 'activa'`, asi que en cuanto el monitor de
        salud decidia que la imagen era pobre, al estudiante le desaparecia la
        vista de su propia camara: justo la unica forma que tiene de comprobar
        que sigue encuadrado y de arreglar la luz.
      */}
      {supervision.tipo !== 'apagada' && supervision.tipo !== 'iniciando' && (
        <div className="indicador-camara-examen" aria-label="Mi cámara durante el examen">
          <video ref={asociarVistaPrevia} muted playsInline autoPlay aria-label="Mi cámara" />
          {/* La etiqueta dice lo que pasa, no siempre «activa»: afirmar que la
              camara esta activa cuando se ha desconectado es la clase de
              mentira pequena que hace desconfiar de todo lo demas. */}
          <span>
            {supervision.tipo === 'fallo' ? '○ Cámara sin señal' : '● Cámara activa'}
          </span>
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
                disabled={entregando}
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

function PantallaReconectando() {
  return (
    <main className="pantalla-reconectando" role="alert" aria-live="assertive">
      <div>
        <span className="indicador-reconectando" aria-hidden="true" />
        <h1>Reconectando…</h1>
        <p>El examen está temporalmente bloqueado mientras se recupera la conexión.</p>
      </div>
    </main>
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

  if (pregunta.question_type === 'multiple_select') {
    const marcadas = respuesta?.selected_option_ids ?? []
    return (
      <>
        <p className="ayuda">Marca todas las que correspondan.</p>
        <ul className="opciones-examen">
          {pregunta.options.map((opcion) => (
            <li key={opcion.id}>
              <label>
                <input
                  type="checkbox"
                  disabled={bloqueada}
                  value={opcion.id}
                  checked={marcadas.includes(opcion.id)}
                  onChange={() =>
                    onResponder({
                      question_id: pregunta.id,
                      // Se manda el conjunto entero, no el cambio: así el
                      // guardado es idempotente y reintentarlo no deja una
                      // respuesta a medias.
                      selected_option_ids: marcadas.includes(opcion.id)
                        ? marcadas.filter((id) => id !== opcion.id)
                        : pregunta.options
                            .filter((o) => o.id === opcion.id || marcadas.includes(o.id))
                            .map((o) => o.id)
                    })
                  }
                />
                <span>{opcion.option_text}</span>
              </label>
            </li>
          ))}
        </ul>
      </>
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

/**
 * Lo que ve el estudiante al terminar.
 *
 * Lleva salidas a propósito. Antes decía «ya puedes cerrar la aplicación» y
 * nada más: un callejón sin salida justo después del momento de más tensión
 * del examen, y la única pantalla de la aplicación sin forma de volver. Quien
 * acaba de entregar quiere comprobar que su entrega consta y ver su examen, no
 * quedarse mirando un mensaje ni tener que matar la ventana.
 */
function Entregado({ cuando, sessionId }: { cuando: string; sessionId?: string }) {
  return (
    <div className="centrado-estrecho">
      <div className="tarjeta">
        <div className="vacio">
          <h3>Examen entregado</h3>
          <p className="subtitulo">
            {/* "p. m." ya termina en punto: encadenar otro daria "p. m..". */}
            Se registró tu entrega a las {soloHora(cuando)}.
          </p>
          <p className="ayuda" style={{ marginTop: 'var(--e4)' }}>
            Si durante el examen aparecieron avisos de supervisión, los revisa tu docente. El
            sistema no decide nada por su cuenta.
          </p>
          <p style={{ marginTop: 'var(--e5)' }}>
            {sessionId && (
              <Link to={`/estudiante/examenes/${sessionId}`} className="boton">
                Ver mi examen
              </Link>
            )}
            <Link
              to="/estudiante"
              className={sessionId ? 'boton boton-secundario' : 'boton'}
              style={sessionId ? { marginLeft: 'var(--e3)' } : undefined}
            >
              Volver a mis exámenes
            </Link>
          </p>
          <p className="ayuda" style={{ marginTop: 'var(--e4)' }}>
            Ya puedes cerrar la aplicación cuando quieras.
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

function almacenamientoLocal(): Storage | undefined {
  try {
    return window.localStorage
  } catch {
    return undefined
  }
}

function respuestasLocales(sessionId: string, studentId: string | null): NewAnswer[] {
  const storage = almacenamientoLocal()
  if (!storage) return []
  try {
    const value: unknown = JSON.parse(
      storage.getItem(`proctoring.pending-answers:${sessionId}:${studentId ?? 'guest'}`) ?? '[]'
    )
    return Array.isArray(value)
      ? value.filter(
          (answer): answer is NewAnswer =>
            typeof answer === 'object' &&
            answer !== null &&
            'question_id' in answer &&
            typeof answer.question_id === 'string'
        )
      : []
  } catch {
    return []
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
  studentId: string | null,
  setGuardado: (estado: EstadoGuardado) => void,
  setError: (mensaje: string | undefined) => void
): {
  guardar: (respuesta: NewAnswer) => void
  reintentarGuardado: () => void
  /** Manda lo pendiente y dice si quedó algo sin guardar. */
  vaciarPendientes: () => Promise<boolean>
  limpiarPendientes: () => void
} {
  // La lógica vive en `ColaDeGuardado`, fuera de React. Es el camino por el que
  // se pierden o no se pierden las respuestas de alguien en un examen, y dentro
  // del componente no se podía probar sin montar una pantalla: por eso un fallo
  // aquí llegó a producción.
  const cola = useRef<ColaDeGuardado>(undefined)
  const ajustes = useRef({ sessionId, token, setGuardado, setError })
  useEffect(() => {
    ajustes.current = { sessionId, token, setGuardado, setError }
  }, [sessionId, token, setGuardado, setError])

  cola.current ??= new ColaDeGuardado(
    async (lote) => {
      // Se descarta lo que devuelve: la cola solo necesita saber si llegó.
      await api.saveAnswers(ajustes.current.sessionId, lote, ajustes.current.token)
    },
    (estado) => {
      ajustes.current.setGuardado(estado)
      if (estado !== 'error') ajustes.current.setError(undefined)
    },
    (fallo) => {
      // Un 403 aquí no es un fallo de red: el examen cerró o ya se entregó, y
      // el estudiante necesita saberlo con esas palabras.
      ajustes.current.setError(
        fallo instanceof ApiError
          ? fallo.message
          : 'Se perdió la conexión. Tu última respuesta no se guardó.'
      )
    },
    500,
    almacenamientoLocal(),
    `proctoring.pending-answers:${sessionId}:${studentId ?? 'guest'}`
  )

  // Al desmontar se manda lo que quede: cerrar la pestaña no debería perder la
  // respuesta que estaba en el aire.
  useEffect(() => {
    const actual = cola.current
    return () => {
      void actual?.enviar()
      actual?.destruir()
    }
  }, [])

  const guardar = useCallback((respuesta: NewAnswer) => cola.current?.encolar(respuesta), [])
  const reintentarGuardado = useCallback(() => void cola.current?.enviar(), [])
  const vaciarPendientes = useCallback(async () => (await cola.current?.vaciar()) ?? true, [])
  const limpiarPendientes = useCallback(() => cola.current?.limpiar(), [])
  return { guardar, reintentarGuardado, vaciarPendientes, limpiarPendientes }
}

function indexar(respuestas: Answer[]): Record<string, NewAnswer> {
  return Object.fromEntries(
    respuestas.map((r) => [
      r.question_id,
      {
        question_id: r.question_id,
        selected_option_id: r.selected_option_id,
        selected_option_ids: r.selected_option_ids,
        text_answer: r.text_answer,
        numeric_answer: r.numeric_answer
      }
    ])
  )
}
