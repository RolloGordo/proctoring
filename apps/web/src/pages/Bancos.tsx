import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, type Course, type QuestionBank } from '../lib/api'
import { useAuth } from '../lib/auth-context'

/**
 * Los bancos del docente.
 *
 * Un banco es un montón de preguntas que no pertenece a ningún examen: se
 * escribe una vez y se reutiliza. Es también donde cae lo que se importe de un
 * QTI.
 */
export function Bancos() {
  const { token } = useAuth()
  const [bancos, setBancos] = useState<QuestionBank[]>()
  const [cursos, setCursos] = useState<Course[]>([])
  const [error, setError] = useState<string>()

  const [nombre, setNombre] = useState('')
  const [cursoId, setCursoId] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [creando, setCreando] = useState(false)

  useEffect(() => {
    api
      .listBanks(token)
      .then(setBancos)
      .catch((fallo: Error) => setError(fallo.message))
    api
      .listCourses(token)
      .then(setCursos)
      .catch(() => undefined)
  }, [token])

  async function crear(evento: FormEvent): Promise<void> {
    evento.preventDefault()
    setError(undefined)
    setCreando(true)
    try {
      const nuevo = await api.createBank(
        {
          name: nombre.trim(),
          course_id: cursoId || null,
          description: descripcion.trim() || null
        },
        token
      )
      setBancos((previos) => [nuevo, ...(previos ?? [])])
      setNombre('')
      setDescripcion('')
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo crear el banco')
    } finally {
      setCreando(false)
    }
  }

  const totalPreguntas = (bancos ?? []).reduce((suma, b) => suma + b.question_count, 0)

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>Bancos de preguntas</h1>
          <p className="subtitulo">
            {bancos
              ? `${bancos.length} banco${bancos.length === 1 ? '' : 's'} · ${totalPreguntas} pregunta${totalPreguntas === 1 ? '' : 's'} en total`
              : 'Cargando…'}
          </p>
        </div>
      </div>

      {error && <p className="aviso">{error}</p>}

      <div className="columnas">
        <section>
          <div className="encabezado-seccion">
            <h2>Nuevo banco</h2>
          </div>

          <div className="tarjeta">
            <div className="tarjeta-cuerpo">
              <form onSubmit={(e) => void crear(e)} noValidate>
                <label className="campo">
                  <span>Nombre</span>
                  <input
                    value={nombre}
                    onChange={(e) => setNombre(e.target.value)}
                    maxLength={120}
                    placeholder="Bases de datos — unidades 1 a 4"
                    required
                  />
                </label>

                {cursos.length > 0 && (
                  <label className="campo">
                    <span>Curso (opcional)</span>
                    <select value={cursoId} onChange={(e) => setCursoId(e.target.value)}>
                      <option value="">Sin curso: sirve para cualquier examen</option>
                      {cursos.map((curso) => (
                        <option key={curso.id} value={curso.id}>
                          {curso.name}
                          {curso.section ? ` — sección ${curso.section}` : ''}
                        </option>
                      ))}
                    </select>
                    <p className="ayuda">
                      Atarlo a un curso es solo para ordenarte: cualquier banco tuyo se puede usar
                      en cualquiera de tus exámenes.
                    </p>
                  </label>
                )}

                <label className="campo">
                  <span>Nota para ti (opcional)</span>
                  <textarea
                    rows={2}
                    value={descripcion}
                    onChange={(e) => setDescripcion(e.target.value)}
                    maxLength={1000}
                  />
                </label>

                <button type="submit" className="boton" disabled={creando || !nombre.trim()}>
                  {creando ? 'Creando…' : 'Crear banco'}
                </button>
              </form>
            </div>
          </div>
        </section>

        <section>
          <div className="encabezado-seccion">
            <h2>Mis bancos</h2>
          </div>

          {bancos?.length === 0 ? (
            <div className="tarjeta">
              <div className="vacio">
                <h3>Todavía no tienes bancos</h3>
                <p className="subtitulo">
                  Crea uno y escribe las preguntas una sola vez. Después se ata a cuantos exámenes
                  quieras, y cada estudiante recibe un sorteo distinto.
                </p>
              </div>
            </div>
          ) : (
            <ul className="lista-bancos">
              {bancos?.map((banco) => (
                <li key={banco.id} className="tarjeta">
                  <div className="tarjeta-cuerpo">
                    <div className="fila" style={{ justifyContent: 'space-between' }}>
                      <h4>{banco.name}</h4>
                      <span className="tenue">
                        {banco.question_count} pregunta{banco.question_count === 1 ? '' : 's'}
                      </span>
                    </div>
                    {banco.description && <p className="ayuda">{banco.description}</p>}
                    <div className="fila" style={{ marginTop: 'var(--e2)' }}>
                      <Link to={`/bancos/${banco.id}`} className="boton boton-secundario">
                        Ver y añadir preguntas
                      </Link>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  )
}
