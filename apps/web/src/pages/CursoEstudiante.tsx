import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type MyCourse, type MyCourseExam, type MyExam } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { estadoExamen, fechaLarga } from '../lib/formato'
import { ChipEstado } from '../components/ChipEstado'

/**
 * Un curso del estudiante, con **todos** sus exámenes.
 *
 * El panel solo muestra los tres próximos de cada clase, que sirve para saber
 * qué viene pero no para repasar el curso entero. Aquí están también los ya
 * rendidos, con su nota y un enlace a lo que respondió.
 *
 * Los datos salen de los dos endpoints que ya existen: `myCourses` sabe qué
 * exámenes tiene cada curso y `myExams` sabe qué hizo el estudiante en ellos.
 * Cruzarlos aquí evita un endpoint nuevo para lo mismo.
 */
export function CursoEstudiante() {
  const { id = '' } = useParams()
  const { token } = useAuth()
  const [curso, setCurso] = useState<MyCourse | null>()
  const [mios, setMios] = useState<MyExam[]>([])
  const [error, setError] = useState<string>()

  useEffect(() => {
    let cancelado = false

    Promise.all([api.myCourses(token), api.myExams(token)])
      .then(([cursos, examenes]) => {
        if (cancelado) return
        setCurso(cursos.find((c) => c.id === id) ?? null)
        setMios(examenes)
      })
      .catch((fallo: Error) => !cancelado && setError(fallo.message))

    return () => {
      cancelado = true
    }
  }, [id, token])

  if (error) return <p className="aviso">{error}</p>
  if (curso === undefined) return <p className="tenue">Cargando el curso…</p>
  if (curso === null) {
    return (
      <>
        <p className="aviso">No estás matriculado en este curso.</p>
        <Link to="/estudiante" className="boton boton-secundario">
          Volver a mi panel
        </Link>
      </>
    )
  }

  const porFecha = [...curso.exams].sort(
    (a, b) => new Date(b.starts_at).getTime() - new Date(a.starts_at).getTime()
  )
  const mio = new Map(mios.map((examen) => [examen.session_id, examen]))

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>{curso.name}</h1>
          <p className="subtitulo">
            {curso.section ? `Sección ${curso.section} · ` : ''}
            {porFecha.length} {porFecha.length === 1 ? 'examen' : 'exámenes'}
          </p>
        </div>
        <Link to="/estudiante" className="boton boton-secundario">
          Volver a mi panel
        </Link>
      </div>

      {porFecha.length === 0 ? (
        <div className="tarjeta">
          <div className="vacio">
            <h3>Este curso todavía no tiene exámenes</h3>
            <p className="subtitulo">Cuando tu docente cree uno, aparecerá aquí.</p>
          </div>
        </div>
      ) : (
        <div className="tarjeta">
          <table className="tabla">
            <thead>
              <tr>
                <th>Examen</th>
                <th>Inicio</th>
                <th>Estado</th>
                <th className="numero">Nota</th>
              </tr>
            </thead>
            <tbody>
              {porFecha.map((examen) => (
                <FilaExamen key={examen.session_id} examen={examen} mio={mio.get(examen.session_id)} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

function FilaExamen({ examen, mio }: { examen: MyCourseExam; mio: MyExam | undefined }) {
  const entregado = mio?.submitted_at != null
  const estado = estadoExamen(
    examen.starts_at,
    examen.duration_minutes,
    undefined,
    mio?.cancelled
  )

  return (
    <tr>
      <td className="celda-titulo">
        {entregado ? (
          <Link to={`/estudiante/examenes/${examen.session_id}`}>{examen.title}</Link>
        ) : (
          <strong>{examen.title}</strong>
        )}
        <span className="celda-detalle">
          {examen.duration_minutes} min
          {entregado ? ' · ver respuestas y señales' : ''}
        </span>
      </td>
      <td className="hora">{fechaLarga(examen.starts_at)}</td>
      <td>
        <ChipEstado estado={entregado ? 'terminado' : estado} />
      </td>
      <td className="numero">
        {/* Sin entregar no hay nota, y un cero ahí se leería como un suspenso. */}
        {!entregado || mio?.score == null ? (
          <span className="tenue">—</span>
        ) : (
          <>
            {mio.score}
            {mio.max_score !== null && <span className="tenue"> / {mio.max_score}</span>}
          </>
        )}
      </td>
    </tr>
  )
}
