import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChipEstado } from '../components/ChipEstado'
import { FormularioCodigo } from '../components/FormularioCodigo'
import { api, comoExamenUnido, type MyCourse, type MyExam } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { cuandoEmpieza, estadoExamen, fechaLarga, horaCorta } from '../lib/formato'

/**
 * El panel del estudiante: **qué le toca rendir, y cuándo**.
 *
 * Lo primero es lo que tiene por rendir, con el que se puede abrir ya delante
 * y la hora a la que se le cierra el ingreso: es lo que más importa en ese
 * momento, y antes no estaba en ninguna parte. Debajo, lo entregado con su
 * nota. Al lado, entrar con un código y sus clases, que son el complemento.
 *
 * Sigue el patrón de los paneles de Canvas y Moodle —«por hacer» con fechas y
 * lo entregado con su nota— pero corto: con demasiados datos el estudiante no
 * sabe qué mirar.
 */
export function PanelEstudiante() {
  const { token } = useAuth()
  const [examenes, setExamenes] = useState<MyExam[]>()
  const [clases, setClases] = useState<MyCourse[]>([])
  const [error, setError] = useState<string>()
  const [reintentos, setReintentos] = useState(0)
  // El ingreso se cierra a una hora: un reloj cada 30 s basta.
  const [ahora, setAhora] = useState(() => Date.now())

  useEffect(() => {
    const temporizador = setInterval(() => setAhora(Date.now()), 30_000)
    return () => clearInterval(temporizador)
  }, [])

  useEffect(() => {
    let cancelado = false
    api
      .myExams(token)
      .then((datos) => !cancelado && setExamenes(datos))
      .catch((fallo: Error) => !cancelado && setError(fallo.message))
    return () => {
      cancelado = true
    }
  }, [token, reintentos])

  // Las clases son un complemento: si fallan, el panel sigue sirviendo.
  useEffect(() => {
    let cancelado = false
    api
      .myCourses(token)
      .then((datos) => !cancelado && setClases(datos))
      .catch(() => undefined)
    return () => {
      cancelado = true
    }
  }, [token])

  const { porRendir, entregados } = useMemo(() => {
    const pendientes = (examenes ?? []).filter((e) => e.submitted_at === null)
    // Lo que se puede abrir ya, delante; después, por fecha.
    pendientes.sort(
      (a, b) =>
        Number(b.can_enter_now) - Number(a.can_enter_now) ||
        new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime()
    )
    return {
      porRendir: pendientes,
      entregados: (examenes ?? [])
        .filter((e) => e.submitted_at !== null)
        .sort(
          (a, b) =>
            new Date(b.submitted_at ?? 0).getTime() - new Date(a.submitted_at ?? 0).getTime()
        )
    }
  }, [examenes])

  const abierto = porRendir.find((e) => e.can_enter_now && !e.cancelled)
  const proximo = porRendir.find((e) => !e.cancelled && new Date(e.starts_at).getTime() > ahora)
  const hallazgo = !examenes
    ? undefined
    : abierto
      ? `Puedes entrar a ${abierto.title} ahora.`
      : proximo
        ? `Tu próximo examen empieza ${cuandoEmpieza(new Date(proximo.starts_at).getTime() - ahora)}.`
        : 'No tienes exámenes pendientes.'

  return (
    <div className="inicio-estudiante">
      <header className="encabezado-pagina">
        <div>
          <h1>Panel</h1>
          {hallazgo && <p className="inicio-hallazgo">{hallazgo}</p>}
        </div>
      </header>

      <div className="estudiante-columnas">
        <div className="estudiante-principal">
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

          <section className="tarjeta inicio-lista" aria-labelledby="por-rendir">
            <div className="encabezado-seccion">
              <h2 id="por-rendir">
                Por rendir {examenes && <span className="inicio-cuenta">{porRendir.length}</span>}
              </h2>
            </div>
            {!examenes && !error ? (
              <div className="inicio-cargando-bloque" aria-busy="true">
                <span className="barra-carga" style={{ width: '60%' }} />
                <span className="barra-carga" style={{ width: '40%' }} />
              </div>
            ) : porRendir.length === 0 ? (
              <p className="inicio-vacio">
                No tienes exámenes pendientes. Cuando tu docente te dé un código, escríbelo aquí al
                lado y aparecerá en esta lista.
              </p>
            ) : (
              <ul className="inicio-filas">
                {porRendir.map((examen) => (
                  <FilaPorRendir key={examen.session_id} examen={examen} ahora={ahora} />
                ))}
              </ul>
            )}
          </section>

          <section className="tarjeta inicio-lista" aria-labelledby="entregados">
            <div className="encabezado-seccion">
              <h2 id="entregados">Entregados</h2>
            </div>
            {!examenes && !error ? (
              <div className="inicio-cargando-bloque" aria-busy="true">
                <span className="barra-carga" style={{ width: '50%' }} />
              </div>
            ) : entregados.length === 0 ? (
              <p className="inicio-vacio">Todavía no has entregado ningún examen.</p>
            ) : (
              <ul className="inicio-filas">
                {entregados.map((examen) => (
                  <li key={examen.session_id}>
                    <div className="inicio-fila-texto">
                      <Link to={`/estudiante/examenes/${examen.session_id}`}>{examen.title}</Link>
                      <span>
                        Entregado el {fechaLarga(examen.submitted_at ?? examen.ends_at)} · Ver
                        respuestas y señales
                      </span>
                    </div>
                    <Nota examen={examen} />
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        <aside className="estudiante-lado">
          <section className="tarjeta estudiante-codigo" aria-labelledby="con-codigo">
            <h2 id="con-codigo">Entrar con un código</h2>
            <p className="subtitulo">El que te dio tu docente. Da igual si va en minúsculas.</p>
            <FormularioCodigo compacto principal={!abierto} />
          </section>

          {clases.length > 0 && (
            <section className="tarjeta inicio-lista" aria-labelledby="mis-clases">
              <div className="encabezado-seccion">
                <h2 id="mis-clases">Mis clases</h2>
              </div>
              <ul className="inicio-filas">
                {clases.map((clase) => (
                  <FilaClase key={clase.id} clase={clase} ahora={ahora} />
                ))}
              </ul>
            </section>
          )}
        </aside>
      </div>
    </div>
  )
}

function FilaPorRendir({ examen, ahora }: { examen: MyExam; ahora: number }) {
  const estado = estadoExamen(examen.starts_at, examen.duration_minutes, ahora, examen.cancelled)
  const inicio = new Date(examen.starts_at).getTime()
  const cierraIngreso = inicio + examen.entry_tolerance_minutes * 60_000

  let detalle: string
  // Lo primero: un examen cancelado no "empieza en 3 horas".
  if (examen.cancelled) detalle = 'Tu docente canceló este examen'
  else if (examen.can_enter_now)
    detalle = `Puedes entrar ahora · el ingreso cierra a las ${horaCorta(new Date(cierraIngreso).toISOString())}`
  else if (estado === 'programado') detalle = `Empieza ${cuandoEmpieza(inicio - ahora)}`
  else if (estado === 'en_curso') detalle = 'El plazo de ingreso terminó'
  else detalle = 'No lo entregaste a tiempo'

  return (
    <li className={examen.can_enter_now && !examen.cancelled ? 'estudiante-abierto' : undefined}>
      <div className="inicio-fila-texto">
        <strong>{examen.title}</strong>
        <span>
          {fechaLarga(examen.starts_at)} · {examen.duration_minutes} min
        </span>
        <span className={examen.can_enter_now ? 'estudiante-detalle activo' : 'estudiante-detalle'}>
          {detalle}
        </span>
      </div>
      {examen.cancelled ? (
        // Sin enlace: no hay a dónde ir, y un botón que lleva a una pantalla de
        // error es peor que no tener botón.
        <ChipEstado estado="cancelado" />
      ) : (
        <Link
          to={`/examen/${examen.session_id}/sala`}
          state={comoExamenUnido(examen)}
          className={examen.can_enter_now ? 'boton' : 'boton boton-secundario'}
        >
          {examen.can_enter_now ? 'Continuar' : 'Ver detalles'}
        </Link>
      )}
    </li>
  )
}

/**
 * La nota de un examen entregado.
 *
 * Nunca un cero inventado: sin calificación se dice que falta. Y si hay
 * desarrollos que el docente todavía no corrige, la nota es **parcial** y se
 * avisa, porque «5 de 10» sin esa aclaración parece definitiva.
 */
function Nota({ examen }: { examen: MyExam }) {
  if (examen.score === null) {
    return <span className="chip chip-programado">Pendiente de calificación</span>
  }

  return (
    <span className="estudiante-nota">
      <strong>
        {examen.score}
        {examen.max_score !== null && <span className="tenue"> / {examen.max_score}</span>}
      </strong>
      {examen.pending_manual_review && (
        <span className="chip chip-programado">Faltan desarrollos por calificar</span>
      )}
    </span>
  )
}

/**
 * Una clase y lo próximo que viene en ella.
 *
 * Solo muestra cuándo es cada examen. Estar en la clase no da acceso al examen:
 * para rendirlo hace falta el código que reparte el docente.
 */
function FilaClase({ clase, ahora }: { clase: MyCourse; ahora: number }) {
  const siguiente = clase.exams
    .filter((e) => new Date(e.starts_at).getTime() + e.duration_minutes * 60_000 >= ahora)
    .sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime())[0]

  return (
    <li>
      <div className="inicio-fila-texto">
        <Link to={`/estudiante/cursos/${clase.id}`}>
          {clase.name}
          {clase.section && <span className="tenue"> · Sección {clase.section}</span>}
        </Link>
        <span>
          {siguiente ? (
            <>
              {siguiente.title} ·{' '}
              <span className="sin-corte">{fechaLarga(siguiente.starts_at)}</span>
            </>
          ) : (
            'Sin exámenes próximos'
          )}
        </span>
      </div>
    </li>
  )
}
