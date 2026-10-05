import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { FormularioCodigo } from '../components/FormularioCodigo'
import { api, comoExamenUnido, type MyExam } from '../lib/api'
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
                          {examen.score !== null ? (
                            <strong>{examen.score}</strong>
                          ) : (
                            <span className="chip chip-programado">Pendiente de calificación</span>
                          )}
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
  const estado = estadoExamen(examen.starts_at, examen.duration_minutes, ahora)
  const empiezaEn = new Date(examen.starts_at).getTime() - ahora

  let detalle: string
  if (examen.can_enter_now) detalle = 'Puedes entrar ahora'
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
      <Link
        to={`/examen/${examen.session_id}/sala`}
        state={comoExamenUnido(examen)}
        className={examen.can_enter_now ? 'boton' : 'boton boton-secundario'}
      >
        {examen.can_enter_now ? 'Continuar' : 'Ver detalles'}
      </Link>
    </li>
  )
}
