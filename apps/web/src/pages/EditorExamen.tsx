import { useCallback, useEffect, useRef, useState, type FocusEvent } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { BancosDelExamen } from '../components/BancosDelExamen'
import { CodigoAcceso } from '../components/CodigoAcceso'
import { EditorPregunta } from '../components/EditorPregunta'
import { ImportarPreguntasExamen } from '../components/ImportarPreguntasExamen'
import { SeleccionPreguntasBancos } from '../components/SeleccionPreguntasBancos'
import { api, type ExamSession, type NewQuestion } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { estadoExamen, fechaLarga } from '../lib/formato'
import { Preguntas } from './Preguntas'
import { Resultados } from './Resultados'
import { SesionEnVivo } from './SesionEnVivo'
import { EditarSesion } from './EditarSesion'
import { Participantes } from './Participantes'

type VistaEditor = 'contenido' | 'participantes' | 'entregas' | 'actividad' | 'ajustes'
type ModalContenido = 'manual' | 'archivo' | 'bancos' | null

const VISTAS: Array<{ id: VistaEditor; etiqueta: string }> = [
  { id: 'contenido', etiqueta: 'Contenido' },
  { id: 'participantes', etiqueta: 'Participantes' },
  { id: 'entregas', etiqueta: 'Entregas' },
  { id: 'actividad', etiqueta: 'Actividad' },
  { id: 'ajustes', etiqueta: 'Ajustes' }
]

/** Lienzo único del examen: contenido al centro y configuración persistente al costado. */
export function EditorExamen() {
  const { id = '' } = useParams()
  const [parametros, setParametros] = useSearchParams()
  const { token } = useAuth()
  const [sesion, setSesion] = useState<ExamSession>()
  const [titulo, setTitulo] = useState('')
  const valorVista = parametros.get('vista')
  const vista: VistaEditor = VISTAS.some((opcion) => opcion.id === valorVista)
    ? (valorVista as VistaEditor)
    : 'contenido'
  const [error, setError] = useState<string>()
  const [aviso, setAviso] = useState<string>()
  const [guardandoTitulo, setGuardandoTitulo] = useState(false)
  const [modalContenido, setModalContenido] = useState<ModalContenido>(null)
  const [versionContenido, setVersionContenido] = useState(0)
  const [revisionBancos, setRevisionBancos] = useState(0)
  const ultimoConteoBancos = useRef<number | undefined>(undefined)
  const [bancosAsociados, setBancosAsociados] = useState(0)
  const [hayEntregas, setHayEntregas] = useState(false)
  const [cargandoEstadoContenido, setCargandoEstadoContenido] = useState(true)
  const [errorEstadoContenido, setErrorEstadoContenido] = useState<string>()
  const [errorContenido, setErrorContenido] = useState<string>()
  const [guardandoPregunta, setGuardandoPregunta] = useState(false)
  const [resumenContenido, setResumenContenido] = useState<{ cantidad: number; puntos: number }>()

  useEffect(() => {
    let cancelado = false
    api
      .getSession(id, token)
      .then((datos) => {
        if (cancelado) return
        setSesion(datos)
        setTitulo(datos.title)
      })
      .catch((fallo: Error) => !cancelado && setError(fallo.message))
    return () => {
      cancelado = true
    }
  }, [id, token])

  useEffect(() => {
    let cancelado = false
    setCargandoEstadoContenido(true)
    setErrorEstadoContenido(undefined)
    Promise.all([api.listSessionBanks(id, token), api.listParticipants(id, token)])
      .then(([bancos, participantes]) => {
        if (cancelado) return
        setBancosAsociados(bancos.length)
        setHayEntregas(participantes.some((participante) => participante.submitted_at !== null))
      })
      .catch((fallo: Error) => {
        if (cancelado) return
        setErrorEstadoContenido(fallo.message)
      })
      .finally(() => {
        if (!cancelado) setCargandoEstadoContenido(false)
      })
    return () => {
      cancelado = true
    }
  }, [id, token, versionContenido])

  useEffect(() => {
    let cancelado = false
    Promise.all([
      api.listQuestions(id, token),
      api.listSessionBanks(id, token),
      api.listSessionBankQuestions(id, token)
    ]).then(([propias, bancos, preguntasDeBanco]) => {
      if (cancelado) return
      const preguntas = bancos.length > 0
        ? preguntasDeBanco.filter((item) => item.included).map((item) => item.question)
        : propias
      setResumenContenido({
        cantidad: preguntas.length,
        puntos: preguntas.reduce((suma, pregunta) => suma + Number(pregunta.points), 0)
      })
    }).catch(() => {
      if (!cancelado) setResumenContenido(undefined)
    })
    return () => { cancelado = true }
  }, [id, token, versionContenido, revisionBancos])

  const actualizarCantidadBancos = useCallback((cantidad: number) => {
    setBancosAsociados(cantidad)
    if (ultimoConteoBancos.current !== cantidad) {
      ultimoConteoBancos.current = cantidad
      setRevisionBancos((version) => version + 1)
    }
  }, [])

  async function guardarTitulo(evento: FocusEvent<HTMLInputElement>): Promise<void> {
    const nuevoTitulo = evento.currentTarget.value.trim()
    if (!sesion || !nuevoTitulo || nuevoTitulo === sesion.title) {
      setTitulo(sesion?.title ?? '')
      return
    }
    setError(undefined)
    setAviso(undefined)
    setGuardandoTitulo(true)
    try {
      const actualizada = await api.updateSession(id, { title: nuevoTitulo }, token)
      setSesion(actualizada)
      setTitulo(actualizada.title)
      setAviso('Título guardado.')
    } catch (fallo) {
      setTitulo(sesion.title)
      setError(fallo instanceof Error ? fallo.message : 'No se pudo guardar el título.')
    } finally {
      setGuardandoTitulo(false)
    }
  }

  async function agregarPregunta(pregunta: NewQuestion): Promise<void> {
    setErrorContenido(undefined)
    setGuardandoPregunta(true)
    try {
      await api.addQuestions(id, [pregunta], token)
      setVersionContenido((version) => version + 1)
      setModalContenido(null)
      setAviso('Pregunta agregada al examen.')
    } catch (fallo) {
      setErrorContenido(fallo instanceof Error ? fallo.message : 'No se pudo agregar la pregunta.')
      throw fallo
    } finally {
      setGuardandoPregunta(false)
    }
  }

  if (error && !sesion) return <p className="aviso" role="alert">{error}</p>
  if (!sesion) return <p className="tenue">Cargando examen…</p>

  return (
    <div className="lienzo-examen">
      <header className="lienzo-examen-cabecera">
        <div className="lienzo-examen-titulo">
          <span className="lienzo-examen-etiqueta">Editor del examen</span>
          <label>
            <span className="sr-only">Título del examen</span>
            <input
              className="lienzo-examen-titulo-input"
              value={titulo}
              onChange={(evento) => setTitulo(evento.target.value)}
              onBlur={(evento) => void guardarTitulo(evento)}
              onKeyDown={(evento) => {
                if (evento.key === 'Enter') evento.currentTarget.blur()
                if (evento.key === 'Escape') setTitulo(sesion.title)
              }}
              maxLength={200}
              disabled={sesion.status === 'cancelled' || guardandoTitulo}
              aria-label="Título del examen. Edita y sal del campo para guardar."
            />
          </label>
          <p className="lienzo-examen-resumen">
            {fechaLarga(sesion.starts_at)} · {sesion.duration_minutes} min ·{' '}
            {estadoExamen(sesion.starts_at, sesion.duration_minutes, Date.now(), sesion.status === 'cancelled')}
            {guardandoTitulo && ' · Guardando título…'}
          </p>
        </div>
        <div className="lienzo-examen-codigo">
          <CodigoAcceso codigo={sesion.access_code} />
        </div>
      </header>

      {error && <p className="aviso" role="alert">{error}</p>}
      {aviso && <p className="aviso aviso-exito" role="status">{aviso}</p>}

      <nav className="lienzo-examen-pestanas" role="tablist" aria-label="Secciones del examen">
        {VISTAS.map((opcion) => (
          <button
            key={opcion.id}
            type="button"
            role="tab"
            id={`pestana-${opcion.id}`}
            aria-selected={vista === opcion.id}
            aria-controls="panel-editor-examen"
            className={vista === opcion.id ? 'activa' : ''}
            onClick={() => setParametros({ vista: opcion.id })}
          >
            {opcion.etiqueta}
          </button>
        ))}
      </nav>

      <div className="lienzo-examen-columnas">
        <section
          id="panel-editor-examen"
          className="lienzo-examen-contenido"
          role="tabpanel"
          aria-labelledby={`pestana-${vista}`}
          key={vista}
        >
          {vista === 'contenido' ? (
            <>
              <div className="lienzo-examen-acciones">
                <button
                  type="button"
                  className="boton"
                  disabled={cargandoEstadoContenido || Boolean(errorEstadoContenido) || sesion.status === 'cancelled' || hayEntregas || bancosAsociados > 0}
                  onClick={() => setModalContenido('manual')}
                >
                  + Pregunta manual
                </button>
                <button
                  type="button"
                  className="boton boton-secundario"
                  disabled={cargandoEstadoContenido || Boolean(errorEstadoContenido) || sesion.status === 'cancelled' || hayEntregas}
                  onClick={() => setModalContenido('archivo')}
                >
                  Importar preguntas
                </button>
                <button
                  type="button"
                  className="boton boton-secundario"
                  disabled={cargandoEstadoContenido || Boolean(errorEstadoContenido) || sesion.status === 'cancelled' || hayEntregas}
                  onClick={() => setModalContenido('bancos')}
                >
                  {bancosAsociados > 0 ? 'Administrar bancos' : 'Agregar desde un banco'}
                </button>
              </div>
              {resumenContenido && (
                <div className="editor-resumen-contenido" role="status">
                  <strong>{resumenContenido.cantidad} pregunta{resumenContenido.cantidad === 1 ? '' : 's'} en el examen</strong>
                  <span>{resumenContenido.puntos.toLocaleString('es-PE', { maximumFractionDigits: 2 })} puntos en total</span>
                </div>
              )}
              {cargandoEstadoContenido && <p className="ayuda" role="status">Comprobando bancos y entregas antes de habilitar cambios…</p>}
              {errorEstadoContenido && (
                <p className="aviso" role="alert">
                  No se pudo comprobar si este examen tiene bancos o entregas ({errorEstadoContenido}).
                  Por seguridad, crear o importar preguntas está deshabilitado. Recarga la página para volver a intentarlo.
                </p>
              )}
              {bancosAsociados > 0 && (
                <p className="aviso aviso-neutro">
                  Este examen usa preguntas de {bancosAsociados} banco{bancosAsociados === 1 ? '' : 's'}. Revisa las incluidas y sus puntajes en la lista.
                </p>
              )}
              {hayEntregas && (
                <p className="aviso aviso-neutro">
                  Este examen ya tiene entregas. El contenido queda bloqueado para conservar lo que rindió cada estudiante.
                </p>
              )}
              {bancosAsociados > 0 && (
                <SeleccionPreguntasBancos
                  sessionId={id}
                  revision={revisionBancos}
                  bloqueado={sesion.status === 'cancelled'}
                  onGuardado={() => setVersionContenido((version) => version + 1)}
                />
              )}
              {bancosAsociados === 0 && <Preguntas key={versionContenido} enLienzo />}
            </>
          ) : vista === 'participantes' ? (
            <Participantes />
          ) : vista === 'entregas' ? (
            <Resultados />
          ) : vista === 'actividad' ? (
            <SesionEnVivo enLienzo />
          ) : (
            <div className="lienzo-examen-ajustes">
              <h2>Configuración del examen</h2>
              <p className="ayuda">Ajusta horario, duración, supervisión y nota máxima.</p>
              <EditarSesion enPanel />
            </div>
          )}
        </section>


      </div>

      {modalContenido && (
        <div className="modal-examen-fondo" role="presentation" onMouseDown={(evento) => {
          if (evento.target === evento.currentTarget && !guardandoPregunta) setModalContenido(null)
        }}>
          <section className="modal-examen" role="dialog" aria-modal="true" aria-labelledby="modal-examen-titulo">
            <header className="modal-examen-cabecera">
              <div>
                <span className="lienzo-examen-etiqueta">Contenido del examen</span>
                <h2 id="modal-examen-titulo">
                  {modalContenido === 'manual'
                    ? 'Crear pregunta'
                    : modalContenido === 'archivo'
                      ? 'Importar preguntas'
                      : 'Bancos de preguntas'}
                </h2>
              </div>
              <button
                type="button"
                className="boton boton-secundario"
                disabled={guardandoPregunta}
                onClick={() => setModalContenido(null)}
              >
                Cerrar
              </button>
            </header>
            {errorContenido && <p className="aviso" role="alert">{errorContenido}</p>}
            {modalContenido === 'manual' ? (
              <EditorPregunta
                onGuardar={agregarPregunta}
                textoBoton={guardandoPregunta ? 'Guardando…' : 'Agregar al examen'}
              />
            ) : modalContenido === 'archivo' ? (
              <ImportarPreguntasExamen
                sessionId={id}
                courseId={sesion.course_id}
                hayBancosAsociados={bancosAsociados > 0}
                token={token}
                onClose={() => setModalContenido(null)}
                onImportadas={async (cantidad, guardadasEnBanco) => {
                  setVersionContenido((version) => version + 1)
                  if (guardadasEnBanco) {
                    const bancos = await api.listSessionBanks(id, token)
                    actualizarCantidadBancos(bancos.length)
                    setAviso(`${cantidad} preguntas guardadas en un banco y asociadas al examen.`)
                  } else {
                    setAviso(`${cantidad} preguntas agregadas al examen.`)
                  }
                }}
              />
            ) : (
              <BancosDelExamen sessionId={id} onCambioBancos={actualizarCantidadBancos} />
            )}
          </section>
        </div>
      )}
    </div>
  )
}
