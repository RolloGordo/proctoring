import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { BancosDelExamen } from '../components/BancosDelExamen'
import { api, type Alert, type ExamSession, type ProctoringEvent } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { supabase } from '../lib/supabase'
import { duracion, fechaLarga, nombreEvento, nombrePreset, soloHora } from '../lib/formato'

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
  const { token } = useAuth()

  const [sesion, setSesion] = useState<ExamSession>()
  const [alertas, setAlertas] = useState<Alert[]>([])
  const [eventos, setEventos] = useState<ProctoringEvent[]>([])
  const [enVivo, setEnVivo] = useState(false)
  const [error, setError] = useState<string>()

  // Evita duplicar una alerta que llegue por Realtime y por la carga inicial.
  const vistas = useRef(new Set<string>())

  const agregar = useCallback((alerta: Alert) => {
    if (vistas.current.has(alerta.id)) return
    vistas.current.add(alerta.id)
    setAlertas((previas) => [alerta, ...previas])
  }, [])

  useEffect(() => {
    if (!id) return
    let cancelado = false

    Promise.all([api.getSession(id, token), api.listAlerts(id, token), api.listEvents(id, token)])
      .then(([datosSesion, datosAlertas, datosEventos]) => {
        if (cancelado) return
        setSesion(datosSesion)
        datosAlertas.forEach((a) => vistas.current.add(a.id))
        setAlertas(datosAlertas)
        setEventos(datosEventos)
      })
      .catch((fallo: Error) => !cancelado && setError(fallo.message))

    return () => {
      cancelado = true
    }
  }, [id, token])

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
      .subscribe((estado) => setEnVivo(estado === 'SUBSCRIBED'))

    return () => {
      void cliente.removeChannel(canal)
      setEnVivo(false)
    }
  }, [id, agregar])

  const resumen = useMemo(() => {
    const porSeveridad = { high: 0, medium: 0, low: 0 }
    for (const alerta of alertas) porSeveridad[alerta.severity] += 1
    const estudiantes = new Set(eventos.map((e) => e.student_id)).size
    return { ...porSeveridad, estudiantes, eventos: eventos.length }
  }, [alertas, eventos])

  if (error) return <p className="aviso">{error}</p>
  if (!sesion) return <p className="tenue">Cargando examen…</p>

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>{sesion.title}</h1>
          <p className="subtitulo">
            {fechaLarga(sesion.starts_at)} · {sesion.duration_minutes} min · supervisión{' '}
            {nombrePreset(sesion.preset).toLowerCase()}
          </p>
        </div>
        <div className="acciones-sesion">
          <div style={{ textAlign: 'right' }}>
            <span className="codigo-acceso">{sesion.access_code}</span>
            <p className="ayuda">Código de acceso</p>
          </div>
          <div className="fila">
            <Link to={`/sesiones/${id}/preguntas`} className="boton boton-secundario">
              Preguntas
            </Link>
            <Link to={`/sesiones/${id}/participantes`} className="boton boton-secundario">
              Sala de espera
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
                      <p className="ayuda">Estudiante {alerta.student_id.slice(0, 8)}</p>
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
