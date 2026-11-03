import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { ChipEstado } from '../components/ChipEstado'
import { CodigoAcceso } from '../components/CodigoAcceso'
import { api, type Alert, type ExamSessionSummary, type Severity } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { cuandoEmpieza, estadoExamen, fechaLarga, horaCorta, nombrePreset } from '../lib/formato'
import { haceCuanto, lineaExamen } from '../lib/linea-examen'

/** Cuántos exámenes en curso se consultan por alertas. Cada uno es una petición. */
const MAX_CON_ALERTAS = 3
/** Filas de las dos listas de abajo: las mismas en las dos, para que acaben a la par. */
const FILAS = 4

/**
 * El panel del docente: **qué pide su atención ahora**.
 *
 * Su pregunta es «¿hay un examen en marcha y algo que mirar?». Por eso lo más
 * grande son los exámenes en curso, cada uno con su línea: la duración, lo que
 * ya pasó y cada alerta en el minuto en que llegó, con la última dicha en
 * palabras y «Ver en vivo» al lado. Es lo único de este panel que no tendría
 * otro producto. Debajo, a la par, lo que viene y lo que terminó.
 *
 * Sin cifras en tarjetas: los totales ya están en la línea de debajo del
 * título y en las cabeceras de cada lista, y repetirlos en tres cajas no
 * añadía nada.
 */
export function PanelDocente() {
  const { token } = useAuth()
  const [sesiones, setSesiones] = useState<ExamSessionSummary[]>()
  const [alertas, setAlertas] = useState<Record<string, Alert[]>>({})
  const [error, setError] = useState<string>()
  const [reintentos, setReintentos] = useState(0)
  // La línea de un examen en curso avanza sola: un reloj cada 30 s basta.
  const [ahora, setAhora] = useState(() => Date.now())

  useEffect(() => {
    const temporizador = setInterval(() => setAhora(Date.now()), 30_000)
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
  }, [token, reintentos])

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
      pasados: todos
        .filter((s) => s.estado === 'terminado' || s.estado === 'cancelado')
        .sort((a, b) => porInicio(b, a))
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

  const enCurso = grupos.enCurso.length
  const altas = grupos.enCurso.reduce(
    (suma, s) => suma + (alertas[s.id]?.filter((a) => a.severity === 'high').length ?? 0),
    0
  )
  const proximo = grupos.proximos[0]
  const hallazgo = !sesiones
    ? undefined
    : enCurso > 0
      ? `${enCurso} ${enCurso === 1 ? 'examen en curso' : 'exámenes en curso'}` +
        (altas > 0 ? ` · ${altas} ${altas === 1 ? 'alerta alta' : 'alertas altas'}` : '')
      : proximo
        ? `Tu próximo examen empieza ${cuandoEmpieza(new Date(proximo.starts_at).getTime() - ahora)}.`
        : sesiones.length > 0
          ? 'No tienes exámenes programados.'
          : undefined

  return (
    <div className="inicio-docente">
      <header className="encabezado-pagina">
        <div>
          <h1>Panel</h1>
          {hallazgo && <p className="inicio-hallazgo">{hallazgo}</p>}
        </div>
        {/* La primera vez, las acciones van en la tarjeta de bienvenida, donde
         * luego estarán los exámenes: aquí arriba repetían el mismo botón. */}
        {sesiones?.length !== 0 && (
          <div className="fila">
            <Link to="/cursos" className="boton boton-secundario">
              Preparar un curso
            </Link>
            {/* Una sola acción principal: con un examen en marcha es «Ver en
             * vivo», en su tarjeta; sin él, crear el siguiente. */}
            <Link to="/sesiones/nueva" className={enCurso > 0 ? 'boton boton-secundario' : 'boton'}>
              Crear examen
            </Link>
          </div>
        )}
      </header>

      {error && (
        <div className="aviso" role="alert">
          <p>No se pudieron cargar tus exámenes: {error}</p>
          <button
            type="button"
            className="boton boton-secundario"
            onClick={() => {
              setError(undefined)
              setReintentos((actual) => actual + 1)
            }}
          >
            Reintentar
          </button>
        </div>
      )}

      {!sesiones && !error && <Cargando />}

      {sesiones && sesiones.length === 0 && (
        <section className="tarjeta inicio-primero">
          <h2>Crea tu primer examen</h2>
          <p className="subtitulo">
            Al crearlo recibes un código de acceso para repartir a tus estudiantes. Si vas a
            supervisar a un grupo fijo, prepara antes su curso.
          </p>
          <div className="fila">
            <Link to="/sesiones/nueva" className="boton">
              Crear examen
            </Link>
            <Link to="/cursos" className="boton boton-secundario">
              Preparar un curso
            </Link>
          </div>
        </section>
      )}

      {sesiones && sesiones.length > 0 && (
        <>
          {enCurso > 0 && (
            <section className="bloque" aria-labelledby="en-curso">
              <div className="encabezado-seccion">
                <h2 id="en-curso">
                  En curso <span className="inicio-cuenta">{enCurso}</span>
                </h2>
              </div>
              <div className="inicio-en-curso">
                {grupos.enCurso.map((s) => (
                  <ExamenEnCurso key={s.id} examen={s} alertas={alertas[s.id]} ahora={ahora} />
                ))}
              </div>
            </section>
          )}

          <div className="inicio-listas">
            <section className="tarjeta inicio-lista" aria-labelledby="proximos">
              <div className="encabezado-seccion">
                <h2 id="proximos">
                  Próximos <span className="inicio-cuenta">{grupos.proximos.length}</span>
                </h2>
                {grupos.proximos.length > FILAS && <Link to="/sesiones">Ver todos</Link>}
              </div>
              {grupos.proximos.length === 0 ? (
                <p className="inicio-vacio">No hay exámenes programados.</p>
              ) : (
                <ul className="inicio-filas">
                  {grupos.proximos.slice(0, FILAS).map((s) => (
                    <li key={s.id}>
                      <div className="inicio-fila-texto">
                        <Link to={`/sesiones/${s.id}`}>{s.title}</Link>
                        <span>
                          {cuandoEmpiezaCorto(new Date(s.starts_at).getTime() - ahora)} ·{' '}
                          {s.duration_minutes} min · Supervisión{' '}
                          {nombrePreset(s.preset).toLowerCase()}
                        </span>
                      </div>
                      <span className="inicio-fila-dato">
                        {s.access_code ?? <span className="tenue">Código al empezar</span>}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="tarjeta inicio-lista" aria-labelledby="pasados">
              <div className="encabezado-seccion">
                <h2 id="pasados">Terminados</h2>
                <Link to="/sesiones">Ver todos</Link>
              </div>
              {grupos.pasados.length === 0 ? (
                <p className="inicio-vacio">Todavía no ha terminado ningún examen.</p>
              ) : (
                <ul className="inicio-filas">
                  {grupos.pasados.slice(0, FILAS).map((s) => (
                    <li key={s.id}>
                      <div className="inicio-fila-texto">
                        <Link to={`/sesiones/${s.id}`}>{s.title}</Link>
                        <span className="hora">{fechaLarga(s.starts_at)}</span>
                      </div>
                      {s.estado === 'cancelado' ? (
                        <ChipEstado estado="cancelado" />
                      ) : (
                        <Link to={`/sesiones/${s.id}/resultados`} className="inicio-fila-accion">
                          Resultados
                        </Link>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  )
}

/** «Hoy, 16:30», «Mañana, 09:00» o la fecha: cuándo empieza, sin hacer cuentas. */
function cuandoEmpiezaCorto(ms: number): string {
  const inicio = new Date(Date.now() + ms)
  const hoy = new Date()
  const manana = new Date(hoy.getTime() + 86_400_000)
  const hora = horaCorta(inicio.toISOString())
  if (inicio.toDateString() === hoy.toDateString()) return `Hoy, ${hora}`
  if (inicio.toDateString() === manana.toDateString()) return `Mañana, ${hora}`
  return fechaLarga(inicio.toISOString())
}

const NOMBRES: Record<Severity, [string, string]> = {
  high: ['alta', 'altas'],
  medium: ['media', 'medias'],
  low: ['baja', 'bajas']
}

type Estilo = CSSProperties & Record<'--en', string>

function ExamenEnCurso({
  examen,
  alertas,
  ahora
}: {
  examen: ExamSessionSummary
  alertas?: Alert[]
  ahora: number
}) {
  const linea = lineaExamen(examen.starts_at, examen.duration_minutes, ahora, alertas)
  const pasaron = Math.round(linea.transcurrido * examen.duration_minutes)
  const severidades = (['high', 'medium', 'low'] as Severity[]).filter((s) => linea.cuenta[s] > 0)

  return (
    <article className="tarjeta en-curso" aria-labelledby={`examen-${examen.id}`}>
      <div className="en-curso-cabeza">
        <div>
          <h3 id={`examen-${examen.id}`}>{examen.title}</h3>
          <p className="subtitulo">
            Supervisión {nombrePreset(examen.preset).toLowerCase()} · {examen.duration_minutes} min
          </p>
        </div>
        <CodigoAcceso codigo={examen.access_code} />
      </div>

      {/* La línea del examen: la pista es la duración, lo ámbar lo que ya
       * pasó y cada marca una alerta en su minuto, del color de su
       * severidad. Para el lector de pantalla, lo mismo dicho en una frase. */}
      <div
        className="linea"
        role="img"
        aria-label={`Han pasado ${pasaron} de ${examen.duration_minutes} minutos y faltan ${linea.faltan}. ${
          alertas ? `${linea.marcas.length} alertas.` : ''
        }`}
      >
        <div className="linea-pista">
          <div
            className="linea-hecho"
            style={{ '--en': `${linea.transcurrido * 100}%` } as Estilo}
          />
          {linea.marcas.map((marca) => (
            <span
              key={marca.id}
              className={`linea-marca linea-marca-${marca.severidad}`}
              style={{ '--en': `${marca.en * 100}%` } as Estilo}
              title={marca.motivo}
            />
          ))}
        </div>
        <div className="linea-horas">
          <span>{horaCorta(examen.starts_at)}</span>
          <span className="linea-faltan">
            {linea.faltan > 0 ? `Faltan ${linea.faltan} min` : 'Terminando'}
          </span>
          <span>{horaCorta(new Date(linea.finMs).toISOString())}</span>
        </div>
      </div>

      <div className="en-curso-pie">
        <div className="en-curso-alertas">
          {!alertas ? (
            <span className="tenue">Cargando alertas…</span>
          ) : severidades.length === 0 ? (
            <span className="tenue">Sin alertas por ahora</span>
          ) : (
            <>
              <span className="fila en-curso-cuentas">
                {severidades.map((s) => (
                  <span key={s} className={`severidad severidad-${s}`}>
                    {linea.cuenta[s]} {NOMBRES[s][linea.cuenta[s] === 1 ? 0 : 1]}
                  </span>
                ))}
              </span>
              {linea.ultima && (
                <span className="en-curso-ultima">
                  Última: {linea.ultima.reason}{' '}
                  <span className="tenue">
                    · {haceCuanto(ahora - new Date(linea.ultima.created_at).getTime())}
                  </span>
                </span>
              )}
            </>
          )}
        </div>
        <div className="fila">
          <Link to={`/sesiones/${examen.id}/participantes`} className="boton boton-texto">
            Participantes
          </Link>
          <Link to={`/sesiones/${examen.id}`} className="boton">
            Ver en vivo
          </Link>
        </div>
      </div>
    </article>
  )
}

/** Mientras cargan: el sitio de cada bloque, sin brillos ni saltos al llegar. */
function Cargando() {
  return (
    <div className="inicio-cargando" aria-busy="true" aria-label="Cargando tus exámenes">
      <div className="tarjeta inicio-cargando-bloque">
        <span className="barra-carga" style={{ width: '40%' }} />
        <span className="barra-carga" style={{ width: '100%', height: 6 }} />
        <span className="barra-carga" style={{ width: '60%' }} />
      </div>
      <div className="inicio-listas">
        <div className="tarjeta inicio-cargando-bloque">
          <span className="barra-carga" style={{ width: '50%' }} />
          <span className="barra-carga" style={{ width: '80%' }} />
        </div>
        <div className="tarjeta inicio-cargando-bloque">
          <span className="barra-carga" style={{ width: '50%' }} />
          <span className="barra-carga" style={{ width: '80%' }} />
        </div>
      </div>
    </div>
  )
}
