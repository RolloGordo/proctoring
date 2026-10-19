import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { BancosDelExamen } from '../components/BancosDelExamen'
import { CamaraEnVivo } from '../components/CamaraEnVivo'
import {
  api,
  type Alert,
  type ExamSession,
  type Participant,
  type ProctoringEvent
} from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { supabase } from '../lib/supabase'
import { duracion, fechaLarga, nombreEvento, nombrePreset, soloHora } from '../lib/formato'
import { CodigoAcceso } from '../components/CodigoAcceso'
import { mergeAlerts } from '../lib/live-alerts'
import { mergeEvents } from '../lib/live-events'

const CAMARAS_POR_PAGINA = 6

/**
 * Pantalla en vivo del docente.
 *
 * Las alertas llegan por **Supabase Realtime**: la API inserta una fila en
 * `alerts` y esta pantalla la recibe sin preguntar nada. Es lo que sostiene la
 * meta de avisar en menos de 5 s.
 *
 * Realtime solo trae lo que ocurre a partir de la suscripción, así que primero
 * se carga lo ya ocurrido por la API y después se escucha.
 */
export function SesionEnVivo() {
  const { id = '' } = useParams()
  const { token, userId } = useAuth()
  const location = useLocation()

  const [sesion, setSesion] = useState<ExamSession>()
  const [alertasSesion, setAlertasSesion] = useState<{
    sessionId: string
    datos: Alert[]
  }>()
  const [eventosSesion, setEventosSesion] = useState<{
    sessionId: string
    datos: ProctoringEvent[]
  }>()
  const [estadoParticipantes, setEstadoParticipantes] = useState<{
    sessionId: string
    datos: Participant[]
  }>()
  const [falloParticipantes, setFalloParticipantes] = useState<{
    sessionId: string
    mensaje: string
  }>()
  const [paginaCamaras, setPaginaCamaras] = useState({ sessionId: '', indice: 0 })
  const [enVivo, setEnVivo] = useState(false)
  const [error, setError] = useState<string>()
  const [actualizando, setActualizando] = useState(false)

  // Evita duplicados y conserva lo recibido por Realtime mientras termina la carga inicial.
  const vistas = useRef(new Map<string, Alert>())
  const versionCarga = useRef(0)

  const agregar = useCallback(
    (alerta: Alert) => {
      if (alerta.session_id !== id || vistas.current.has(alerta.id)) return
      vistas.current.set(alerta.id, alerta)
      setAlertasSesion((previo) => ({
        sessionId: id,
        datos: mergeAlerts(previo?.sessionId === id ? previo.datos : [], [alerta])
      }))
    },
    [id]
  )

  const cargarParticipantes = useCallback(() => {
    api
      .listParticipants(id, token)
      .then((datos) => {
        setEstadoParticipantes({ sessionId: id, datos })
        setFalloParticipantes(undefined)
      })
      .catch((fallo: Error) => setFalloParticipantes({ sessionId: id, mensaje: fallo.message }))
  }, [id, token])

  const cargarEventos = useCallback(() => {
    api
      .listEvents(id, token)
      .then((datos) =>
        setEventosSesion((previo) => ({
          sessionId: id,
          datos: mergeEvents(previo?.sessionId === id ? previo.datos : [], datos)
        }))
      )
      .catch((fallo: Error) => setError(fallo.message))
  }, [id, token])

  const cargarDatos = useCallback(() => {
    const version = ++versionCarga.current
    return Promise.all([
      api.getSession(id, token),
      api.listAlerts(id, token),
      api.listEvents(id, token)
    ])
      .then(([datosSesion, datosAlertas, datosEventos]) => {
        if (version !== versionCarga.current) return
        setError(undefined)
        setSesion(datosSesion)
        for (const alerta of datosAlertas) vistas.current.set(alerta.id, alerta)
        setAlertasSesion((previo) => ({
          sessionId: id,
          datos: mergeAlerts(
            datosAlertas,
            [...vistas.current.values()].filter((alerta) => alerta.session_id === id),
            previo?.sessionId === id ? previo.datos : []
          )
        }))
        setEventosSesion((previo) => ({
          sessionId: id,
          datos: mergeEvents(previo?.sessionId === id ? previo.datos : [], datosEventos)
        }))
      })
      .catch((fallo: unknown) => {
        if (version !== versionCarga.current) return
        setError(fallo instanceof Error ? fallo.message : 'No se pudieron actualizar los datos.')
      })
      .finally(() => {
        if (version === versionCarga.current) setActualizando(false)
      })
  }, [id, token])

  const eventos = useMemo(
    () => (eventosSesion?.sessionId === id ? eventosSesion.datos : []),
    [eventosSesion, id]
  )

  useEffect(() => {
    vistas.current.clear()
    void cargarDatos()
    return () => {
      versionCarga.current += 1
    }
  }, [id, cargarDatos])

  const actualizarDatos = useCallback(() => {
    setActualizando(true)
    void cargarDatos()
  }, [cargarDatos])

  useEffect(() => {
    cargarParticipantes()
  }, [cargarParticipantes])

  useEffect(() => {
    if (!supabase || !id) return

    // Se fija en una constante local: TypeScript no puede saber que el modulo
    // sigue siendo no nulo dentro de la funcion de limpieza.
    const cliente = supabase
    const canal = cliente
      .channel(`alertas-${id}`)
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'alerts', filter: `session_id=eq.${id}` },
        (mensaje) => agregar(mensaje.new as Alert)
      )
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'session_participants',
          filter: `session_id=eq.${id}`
        },
        cargarParticipantes
      )
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'events',
          filter: `session_id=eq.${id}`
        },
        cargarEventos
      )
      .subscribe((estado) => {
        setEnVivo(estado === 'SUBSCRIBED')
        if (estado === 'SUBSCRIBED') cargarEventos()
      })

    return () => {
      void cliente.removeChannel(canal)
      setEnVivo(false)
    }
  }, [id, agregar, cargarParticipantes, cargarEventos])

  const alertas = useMemo(
    () => (alertasSesion?.sessionId === id ? alertasSesion.datos : []),
    [alertasSesion, id]
  )
  const resumen = useMemo(() => {
    const porSeveridad = { high: 0, medium: 0, low: 0 }
    for (const alerta of alertas) porSeveridad[alerta.severity] += 1
    const estudiantes = new Set(eventos.map((e) => e.student_id)).size
    return { ...porSeveridad, estudiantes, eventos: eventos.length }
  }, [alertas, eventos])

  const participantes = useMemo(
    () => (estadoParticipantes?.sessionId === id ? estadoParticipantes.datos : []),
    [estadoParticipantes, id]
  )
  const errorParticipantes =
    falloParticipantes?.sessionId === id ? falloParticipantes.mensaje : undefined
  const participantesCargados =
    estadoParticipantes?.sessionId === id || falloParticipantes?.sessionId === id
  const participantesActivos = useMemo(
    () =>
      participantes.filter(
        (participante) => participante.can_take_exam && !participante.submitted_at
      ),
    [participantes]
  )
  /**
   * Cómo llamar a cada estudiante en las alertas.
   *
   * Las alertas decían «Estudiante e989cb23» mientras la lista de participantes
   * de esta misma pantalla tenía el nombre a mano. Un docente que revisa un
   * caso tiene que saber de quién habla: con un identificador recortado hay que
   * ir a otra pestaña a traducirlo, y eso con treinta estudiantes no se hace.
   *
   * Si no hay nombre se usa el correo, y solo si tampoco lo hay el
   * identificador. Un perfil incompleto no puede dejar la alerta sin dueno.
   */
  const comoSeLlama = useMemo(() => {
    const porId = new Map<string, string>()
    for (const participante of participantes) {
      const nombre = participante.student_name?.trim() || participante.student_email?.trim()
      if (nombre) porId.set(participante.student_id, nombre)
    }
    return porId
  }, [participantes])

  const totalPaginasCamaras = Math.ceil(participantesActivos.length / CAMARAS_POR_PAGINA)
  const indicePagina = paginaCamaras.sessionId === id ? paginaCamaras.indice : 0
  const paginaVisible = Math.min(indicePagina, Math.max(0, totalPaginasCamaras - 1))
  const camarasVisibles = participantesActivos.slice(
    paginaVisible * CAMARAS_POR_PAGINA,
    (paginaVisible + 1) * CAMARAS_POR_PAGINA
  )

  if (error && !sesion) {
    return (
      <div>
        <p className="aviso" role="alert">
          {error}
        </p>
        <button type="button" className="boton boton-secundario" onClick={actualizarDatos}>
          Reintentar carga
        </button>
      </div>
    )
  }
  if (!sesion) return <p className="tenue">Cargando examen…</p>

  const avisoNavegacion = obtenerAvisoDeRuta(location.state)

  return (
    <>
      {avisoNavegacion && (
        <p className="aviso aviso-neutro" role="status">
          {avisoNavegacion}
        </p>
      )}
      {error && (
        <p className="aviso" role="alert">
          {error}
        </p>
      )}
      <div className="encabezado-pagina">
        <div>
          <h1>{sesion.title}</h1>
          <p className="subtitulo">
            {fechaLarga(sesion.starts_at)} · {sesion.duration_minutes} min · supervisión{' '}
            {nombrePreset(sesion.preset).toLowerCase()}
          </p>
        </div>
        <div className="acciones-sesion">
          <button
            type="button"
            className="boton boton-secundario"
            onClick={actualizarDatos}
            disabled={actualizando}
          >
            {actualizando ? 'Actualizando…' : 'Actualizar alertas y señales'}
          </button>
          <div style={{ textAlign: 'right' }}>
            <CodigoAcceso codigo={sesion.access_code} />
          </div>
          <div className="fila">
            <Link to={`/sesiones/${id}/preguntas`} className="boton boton-secundario">
              Preguntas
            </Link>
            <Link to={`/sesiones/${id}/editar`} className="boton boton-secundario">
              Editar
            </Link>
            <Link to={`/sesiones/${id}/participantes`} className="boton boton-secundario">
              Sala de espera
            </Link>
            <Link to={`/sesiones/${id}/resultados`} className="boton boton-secundario">
              Resultados
            </Link>
          </div>
        </div>
      </div>

      <div className="panel-resumen">
        <Dato valor={resumen.high} etiqueta="Alertas altas" tono="high" />
        <Dato valor={resumen.medium} etiqueta="Alertas medias" tono="medium" />
        <Dato valor={resumen.eventos} etiqueta="Señales registradas" />
        <Dato valor={resumen.estudiantes} etiqueta="Estudiantes con actividad" />
      </div>

      <BancosDelExamen sessionId={id} />

      {'live_monitoring' in sesion.modules && (
        <section className="bloque">
          <div className="encabezado-seccion">
            <h2>Cámaras en vivo</h2>
            <span className="tenue">{participantesActivos.length} estudiantes rindiendo</span>
          </div>
          <div className="tarjeta">
            <div className="tarjeta-cuerpo">
              <p className="ayuda">
                No se está grabando. Las imágenes se transmiten solo mientras las miras y no se
                guardan. El estudiante ve en su pantalla cuando su cámara está siendo observada.
              </p>
              {errorParticipantes && <p className="aviso">{errorParticipantes}</p>}
              {!participantesCargados ? (
                <p className="tenue">Cargando participantes…</p>
              ) : participantesActivos.length === 0 ? (
                <p className="tenue">No hay estudiantes rindiendo en este momento.</p>
              ) : !userId ? (
                <p className="aviso">No se pudo identificar al docente para abrir las cámaras.</p>
              ) : (
                <>
                  <div className="cuadricula-camaras">
                    {camarasVisibles.map((participante) => (
                      <CamaraEnVivo
                        key={participante.student_id}
                        sessionId={id}
                        studentId={participante.student_id}
                        teacherId={userId}
                        nombre={participante.student_name ?? undefined}
                      />
                    ))}
                  </div>
                  {totalPaginasCamaras > 1 && (
                    <nav className="paginacion-camaras" aria-label="Páginas de cámaras">
                      <button
                        type="button"
                        className="boton boton-secundario"
                        onClick={() =>
                          setPaginaCamaras({
                            sessionId: id,
                            indice: Math.max(0, paginaVisible - 1)
                          })
                        }
                        disabled={paginaVisible === 0}
                      >
                        Anterior
                      </button>
                      <span className="tenue">
                        Página {paginaVisible + 1} de {totalPaginasCamaras}
                      </span>
                      <button
                        type="button"
                        className="boton boton-secundario"
                        onClick={() =>
                          setPaginaCamaras({
                            sessionId: id,
                            indice: Math.min(totalPaginasCamaras - 1, paginaVisible + 1)
                          })
                        }
                        disabled={paginaVisible >= totalPaginasCamaras - 1}
                      >
                        Siguiente
                      </button>
                    </nav>
                  )}
                </>
              )}
            </div>
          </div>
        </section>
      )}

      {!supabase && (
        <p className="aviso aviso-neutro">
          Supabase no está configurado, así que no hay alertas en vivo. Esta pantalla muestra lo que
          ya está registrado. Rellena <code>VITE_SUPABASE_URL</code> y{' '}
          <code>VITE_SUPABASE_PUBLISHABLE_KEY</code> para activarlas.
        </p>
      )}

      <div className="columnas">
        <section>
          <div className="encabezado-seccion">
            <h2>Alertas</h2>
            {supabase && (
              <span className="en-vivo">
                <span className={enVivo ? 'punto punto-activo' : 'punto'} />
                {enVivo ? 'En vivo' : 'Sin conexión'}
              </span>
            )}
          </div>

          <div className="tarjeta">
            {alertas.length === 0 ? (
              <div className="vacio">
                <h3>Sin alertas</h3>
                <p className="subtitulo">
                  Las señales leves se registran pero no interrumpen. Aquí solo aparece lo que
                  merece tu atención.
                </p>
              </div>
            ) : (
              <ul className="lista-alertas">
                {alertas.map((alerta) => (
                  <li key={alerta.id}>
                    <span className={`severidad severidad-${alerta.severity}`}>
                      {alerta.severity === 'high' ? 'Alta' : 'Media'}
                    </span>
                    <div>
                      <p className="motivo">{alerta.reason}</p>
                      <p className="ayuda">
                        {comoSeLlama.get(alerta.student_id) ??
                          `Estudiante ${alerta.student_id.slice(0, 8)}`}
                      </p>
                    </div>
                    <span className="hora">{soloHora(alerta.created_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section>
          <div className="encabezado-seccion">
            <h2>Todas las señales</h2>
          </div>

          <div className="tarjeta">
            {eventos.length === 0 ? (
              <div className="vacio">
                <h3>Todavía no hay actividad</h3>
                <p className="subtitulo">Aparecerá en cuanto un estudiante empiece el examen.</p>
              </div>
            ) : (
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Señal</th>
                    <th>Duración</th>
                    <th>Nivel</th>
                    <th>Hora</th>
                  </tr>
                </thead>
                <tbody>
                  {eventos.map((evento) => (
                    <tr key={evento.id}>
                      <td>{nombreEvento(evento.event_type)}</td>
                      <td className="tenue">
                        {evento.duration_ms > 0 ? duracion(evento.duration_ms) : '—'}
                      </td>
                      <td>
                        <span className={`severidad severidad-${evento.severity}`}>
                          {evento.severity}
                        </span>
                      </td>
                      <td className="hora">{soloHora(evento.started_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      </div>
    </>
  )
}

function obtenerAvisoDeRuta(estado: unknown): string | undefined {
  if (typeof estado !== 'object' || estado === null || !('aviso' in estado)) return
  return typeof estado.aviso === 'string' ? estado.aviso : undefined
}

function Dato({
  valor,
  etiqueta,
  tono
}: {
  valor: number
  etiqueta: string
  tono?: 'high' | 'medium'
}) {
  return (
    <div className="tarjeta dato">
      <p className={tono ? `cifra cifra-${tono}` : 'cifra'}>{valor}</p>
      <p className="etiqueta">{etiqueta}</p>
    </div>
  )
}
