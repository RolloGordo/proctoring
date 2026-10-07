import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChipEstado } from '../components/ChipEstado'
import { api, type Alert, type ExamSessionSummary } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { cuandoEmpieza, estadoExamen, fechaLarga, nombrePreset, soloHora } from '../lib/formato'

/** Cuántos exámenes en curso se consultan por alertas. Cada uno es una petición. */
const MAX_CON_ALERTAS = 3

/**
 * El panel del docente: **qué pide su atención ahora**.
 *
 * Lo primero que necesita un docente al entrar no es una lista de todo lo que
 * creó, sino saber si hay un examen en marcha y cómo va. Si no lo hay, cuál es
 * el próximo. La lista completa está en "Mis exámenes".
 */
export function PanelDocente() {
  const { token, email } = useAuth()
  const [sesiones, setSesiones] = useState<ExamSessionSummary[]>()
  const [alertas, setAlertas] = useState<Record<string, Alert[]>>({})
  const [error, setError] = useState<string>()
  // El estado de un examen cambia con la hora; un reloj por minuto basta.
  const [ahora, setAhora] = useState(() => Date.now())

  useEffect(() => {
    const temporizador = setInterval(() => setAhora(Date.now()), 60_000)
    return () => clearInterval(temporizador)
  }, [])

  useEffect(() => {
    let cancelado = false
    api
      .listSessions(token)
      .then((datos) => !cancelado && setSesiones(datos))
      .catch((fallo: Error) => !cancelado && setError(fallo.message))
    return () => {
      cancelado = true
    }
  }, [token])

  const grupos = useMemo(() => {
    const todos = (sesiones ?? []).map((s) => ({
      ...s,
      estado: estadoExamen(s.starts_at, s.duration_minutes, ahora, s.status === 'cancelled')
    }))
    const porInicio = (a: { starts_at: string }, b: { starts_at: string }): number =>
      new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime()
    return {
      enCurso: todos.filter((s) => s.estado === 'en_curso').sort(porInicio),
      proximos: todos.filter((s) => s.estado === 'programado').sort(porInicio),
      terminados: todos.filter((s) => s.estado === 'terminado').sort((a, b) => porInicio(b, a)),
      todos
    }
  }, [sesiones, ahora])

  // Las alertas solo de lo que está en marcha: es donde importan ahora.
  const idsEnCurso = grupos.enCurso
    .slice(0, MAX_CON_ALERTAS)
    .map((s) => s.id)
    .join(',')
  useEffect(() => {
    if (!idsEnCurso) return
    let cancelado = false
    for (const id of idsEnCurso.split(',')) {
      api
        .listAlerts(id, token)
        .then((lista) => !cancelado && setAlertas((previas) => ({ ...previas, [id]: lista })))
        .catch(() => undefined)
    }
    return () => {
      cancelado = true
    }
  }, [idsEnCurso, token])

  const recientes = [...grupos.todos]
    .sort((a, b) => new Date(b.starts_at).getTime() - new Date(a.starts_at).getTime())
    .slice(0, 6)
  const proximo = grupos.proximos[0]

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>Panel del docente</h1>
          {email && <p className="subtitulo">{email}</p>}
        </div>
        <Link to="/sesiones/nueva" className="boton">
          Crear examen
        </Link>
      </div>

      {error && <p className="aviso">{error}</p>}
      {!sesiones && !error && <p className="tenue">Cargando…</p>}

      {sesiones && (
        <>
          <div className="panel-resumen">
            <Cifra valor={grupos.enCurso.length} etiqueta="En curso" tono="en-curso" />
            <Cifra valor={grupos.proximos.length} etiqueta="Próximos" />
            <Cifra valor={grupos.terminados.length} etiqueta="Terminados" />
          </div>

          {sesiones.length === 0 ? (
            <div className="tarjeta">
              <div className="vacio">
                <h3>Todavía no has creado ningún examen</h3>
                <p className="subtitulo">
                  Al crear uno obtienes un código de acceso para repartir a tus estudiantes.
                </p>
                <p style={{ marginTop: 'var(--e5)' }}>
                  <Link to="/sesiones/nueva" className="boton">
                    Crear el primero
                  </Link>
                </p>
              </div>
            </div>
          ) : (
            <>
              {grupos.enCurso.length > 0 && (
                <section className="bloque">
                  <h2>En curso ahora</h2>
                  <div className="apilado">
                    {grupos.enCurso.map((s) => (
                      <TarjetaExamen
                        key={s.id}
                        examen={s}
                        etiqueta={`Termina a las ${soloHoraCorta(
                          new Date(s.starts_at).getTime() + s.duration_minutes * 60_000
                        )}`}
                        alertas={alertas[s.id]}
                        principal="Ver en vivo"
                      />
                    ))}
                  </div>
                </section>
              )}

              {grupos.enCurso.length === 0 && proximo && (
                <section className="bloque">
                  <h2>Tu próximo examen</h2>
                  <TarjetaExamen
                    examen={proximo}
                    etiqueta={`Empieza ${cuandoEmpieza(new Date(proximo.starts_at).getTime() - ahora)}`}
                    principal="Abrir"
                  />
                </section>
              )}

              <section className="bloque">
                <div className="encabezado-seccion">
                  <h2>Exámenes recientes</h2>
                  <Link to="/sesiones">Ver todos</Link>
                </div>
                <div className="tarjeta">
                  <table className="tabla">
                    <thead>
                      <tr>
                        <th>Examen</th>
                        <th>Inicio</th>
                        <th>Supervisión</th>
                        <th>Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recientes.map((s) => (
                        <tr key={s.id}>
                          <td>
                            <Link to={`/sesiones/${s.id}`}>{s.title}</Link>
                          </td>
                          <td className="hora">{fechaLarga(s.starts_at)}</td>
                          <td>{nombrePreset(s.preset)}</td>
                          <td>
                            <ChipEstado estado={s.estado} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}
        </>
      )}
    </>
  )
}

function soloHoraCorta(ms: number): string {
  return soloHora(new Date(ms).toISOString()).slice(0, 5)
}

function Cifra({ valor, etiqueta, tono }: { valor: number; etiqueta: string; tono?: 'en-curso' }) {
  return (
    <div className="tarjeta dato">
      <p className={tono ? `cifra cifra-${tono}` : 'cifra'}>{valor}</p>
      <p className="etiqueta">{etiqueta}</p>
    </div>
  )
}

function TarjetaExamen({
  examen,
  etiqueta,
  alertas,
  principal
}: {
  examen: ExamSessionSummary
  etiqueta: string
  alertas?: Alert[]
  principal: string
}) {
  const altas = alertas?.filter((a) => a.severity === 'high').length ?? 0
  const medias = alertas?.filter((a) => a.severity === 'medium').length ?? 0

  return (
    <div className="tarjeta tarjeta-examen">
      <div className="tarjeta-examen-info">
        <h3>{examen.title}</h3>
        <p className="subtitulo">
          {fechaLarga(examen.starts_at)} · {examen.duration_minutes} min · {etiqueta}
        </p>
        {alertas && (
          <p className="alertas-resumen">
            {altas === 0 && medias === 0 ? (
              <span className="tenue">Sin alertas por ahora</span>
            ) : (
              <>
                {altas > 0 && (
                  <span className="severidad severidad-high">
                    {altas} {altas === 1 ? 'alta' : 'altas'}
                  </span>
                )}
                {medias > 0 && (
                  <span className="severidad severidad-medium">
                    {medias} {medias === 1 ? 'media' : 'medias'}
                  </span>
                )}
              </>
            )}
          </p>
        )}
      </div>
      <div className="tarjeta-examen-acciones">
        <div className="codigo-bloque">
          <span className="codigo-acceso">{examen.access_code}</span>
          <p className="ayuda">Código de acceso</p>
        </div>
        <div className="fila">
          <Link to={`/sesiones/${examen.id}`} className="boton">
            {principal}
          </Link>
          <Link to={`/sesiones/${examen.id}/preguntas`} className="boton boton-secundario">
            Preguntas
          </Link>
          <Link to={`/sesiones/${examen.id}/participantes`} className="boton boton-secundario">
            Sala de espera
          </Link>
        </div>
      </div>
    </div>
  )
}
