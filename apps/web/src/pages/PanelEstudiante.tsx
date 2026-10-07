import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChipEstado } from '../components/ChipEstado'
import { FormularioCodigo } from '../components/FormularioCodigo'
import { api, comoExamenUnido, type MyCourse, type MyExam } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { cuandoEmpieza, estadoExamen, fechaLarga } from '../lib/formato'

/**
 * El panel del estudiante: lo que le toca hacer y lo que ya hizo.
 *
 * Sigue el patrón de los paneles de Canvas y Moodle —una lista de "por hacer"
 * con fechas y lo ya entregado con su nota— pero corto: con demasiados datos el
 * estudiante no sabe qué mirar, y con muy pocos se pierde.
 */
export function PanelEstudiante() {
  const { token, email } = useAuth()
  const [examenes, setExamenes] = useState<MyExam[]>()
  const [clases, setClases] = useState<MyCourse[]>([])
  const [error, setError] = useState<string>()
  const [ahora, setAhora] = useState(() => Date.now())

  useEffect(() => {
    const temporizador = setInterval(() => setAhora(Date.now()), 60_000)
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
  }, [token])

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

  const { porRendir, entregados } = useMemo(
    () => ({
      porRendir: (examenes ?? []).filter((e) => e.submitted_at === null),
      entregados: (examenes ?? []).filter((e) => e.submitted_at !== null)
    }),
    [examenes]
  )

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>Mi panel</h1>
          {email && <p className="subtitulo">{email}</p>}
        </div>
      </div>

      <section className="bloque">
        <div className="tarjeta">
          <div className="tarjeta-cuerpo tarjeta-codigo">
            <div>
              <h2>Entrar a un examen</h2>
              <p className="subtitulo">Escribe el código que te dio tu docente</p>
            </div>
            <FormularioCodigo compacto />
          </div>
        </div>
      </section>

      {clases.length > 0 && (
        <section className="bloque">
          <h2>Mis clases</h2>
          <div className="rejilla-clases">
            {clases.map((clase) => (
              <TarjetaClase key={clase.id} clase={clase} ahora={ahora} />
            ))}
          </div>
        </section>
      )}

      {error && <p className="aviso">{error}</p>}
      {!examenes && !error && <p className="tenue">Cargando tus exámenes…</p>}

      {examenes && (
        <>
          <section className="bloque">
            <h2>Por rendir</h2>
            {porRendir.length === 0 ? (
              <div className="tarjeta">
                <div className="vacio">
                  <h3>No tienes exámenes pendientes</h3>
                  <p className="subtitulo">
                    Cuando tu docente te dé un código, escríbelo arriba y aparecerá aquí.
                  </p>
                </div>
              </div>
            ) : (
              <ul className="lista-examenes">
                {porRendir.map((examen) => (
                  <FilaPorRendir key={examen.session_id} examen={examen} ahora={ahora} />
                ))}
              </ul>
            )}
          </section>

          <section className="bloque">
            <h2>Entregados</h2>
            {entregados.length === 0 ? (
              <div className="tarjeta">
                <div className="vacio">
                  <h3>Todavía no has entregado ningún examen</h3>
                </div>
              </div>
            ) : (
              <div className="tarjeta">
                <table className="tabla">
                  <thead>
                    <tr>
                      <th>Examen</th>
                      <th>Entregado</th>
                      <th>Nota</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entregados.map((examen) => (
                      <tr key={examen.session_id}>
                        <td>{examen.title}</td>
                        <td className="hora">
                          {examen.submitted_at ? fechaLarga(examen.submitted_at) : '—'}
                        </td>
                        <td>
                          <Nota examen={examen} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </>
  )
}

function FilaPorRendir({ examen, ahora }: { examen: MyExam; ahora: number }) {
  const estado = estadoExamen(
    examen.starts_at,
    examen.duration_minutes,
    ahora,
    examen.cancelled
  )
  const empiezaEn = new Date(examen.starts_at).getTime() - ahora

  let detalle: string
  // Lo primero: un examen cancelado no "empieza en 3 horas".
  if (examen.cancelled) detalle = 'Tu docente canceló este examen'
  else if (examen.can_enter_now) detalle = 'Puedes entrar ahora'
  else if (estado === 'programado') detalle = `Empieza ${cuandoEmpieza(empiezaEn)}`
  else if (estado === 'en_curso') detalle = 'El plazo de ingreso terminó'
  else detalle = 'No lo entregaste a tiempo'

  return (
    <li className="tarjeta fila-examen">
      <div>
        <h3>{examen.title}</h3>
        <p className="subtitulo">
          {fechaLarga(examen.starts_at)} · {examen.duration_minutes} min
        </p>
        <p className={examen.can_enter_now ? 'detalle-examen activo' : 'detalle-examen'}>
          {detalle}
        </p>
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
    <>
      <strong>
        {examen.score}
        {examen.max_score !== null && ` de ${examen.max_score}`}
      </strong>
      {examen.pending_manual_review && (
        <span className="chip chip-programado nota-aviso">Faltan desarrollos por calificar</span>
      )}
    </>
  )
}

/**
 * Una clase y lo que viene en ella.
 *
 * Solo muestra cuándo es cada examen. Estar en la clase no da acceso al examen:
 * para rendirlo hace falta el código que reparte el docente.
 */
function TarjetaClase({ clase, ahora }: { clase: MyCourse; ahora: number }) {
  const proximos = clase.exams
    .filter((e) => new Date(e.starts_at).getTime() + e.duration_minutes * 60_000 >= ahora)
    .slice(0, 3)

  return (
    <div className="tarjeta tarjeta-clase">
      <h3>{clase.name}</h3>
      {clase.section && <p className="subtitulo">Sección {clase.section}</p>}
      {proximos.length === 0 ? (
        <p className="ayuda">No hay exámenes próximos.</p>
      ) : (
        <ul className="lista-clase">
          {proximos.map((examen) => (
            <li key={examen.session_id}>
              <strong>{examen.title}</strong>
              <span className="tenue">{fechaLarga(examen.starts_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
