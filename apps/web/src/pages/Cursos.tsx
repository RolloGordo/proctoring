import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, type Course } from '../lib/api'
import { useAuth } from '../lib/auth-context'

/**
 * Los cursos del docente: los grupos a los que toma exámenes.
 *
 * Un curso agrupa a sus estudiantes y a sus exámenes. Estar en un curso **no da
 * acceso a sus exámenes**: para rendir uno el estudiante sigue necesitando el
 * código de acceso.
 */
export function Cursos() {
  const { token } = useAuth()
  const [cursos, setCursos] = useState<Course[]>()
  const [error, setError] = useState<string>()
  const [nombre, setNombre] = useState('')
  const [seccion, setSeccion] = useState('')
  const [creando, setCreando] = useState(false)

  useEffect(() => {
    let cancelado = false
    api
      .listCourses(token)
      .then((datos) => !cancelado && setCursos(datos))
      .catch((fallo: Error) => !cancelado && setError(fallo.message))
    return () => {
      cancelado = true
    }
  }, [token])

  async function crear(evento: FormEvent): Promise<void> {
    evento.preventDefault()
    setError(undefined)
    setCreando(true)
    try {
      const curso = await api.createCourse(nombre, seccion.trim() || null, token)
      setCursos((previos) => [curso, ...(previos ?? [])])
      setNombre('')
      setSeccion('')
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo crear el curso')
    } finally {
      setCreando(false)
    }
  }

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>Mis cursos</h1>
          <p className="subtitulo">Los grupos a los que tomas exámenes</p>
        </div>
      </div>

      {error && <p className="aviso">{error}</p>}

      <section className="bloque">
        <div className="tarjeta">
          <div className="tarjeta-cuerpo">
            <h2>Crear un curso</h2>
            <form onSubmit={(e) => void crear(e)} noValidate className="formulario-curso">
              <label className="campo">
                <span>Nombre</span>
                <input
                  value={nombre}
                  onChange={(e) => setNombre(e.target.value)}
                  maxLength={120}
                  placeholder="Taller Integrador 1"
                  required
                />
              </label>
              <label className="campo campo-corto">
                <span>Sección</span>
                <input
                  value={seccion}
                  onChange={(e) => setSeccion(e.target.value)}
                  maxLength={40}
                  placeholder="A"
                />
              </label>
              <button type="submit" className="boton" disabled={creando || !nombre.trim()}>
                {creando ? 'Creando…' : 'Crear curso'}
              </button>
            </form>
          </div>
        </div>
      </section>

      <section className="bloque">
        {!cursos && !error && <p className="tenue">Cargando…</p>}

        {cursos?.length === 0 && (
          <div className="tarjeta">
            <div className="vacio">
              <h3>Todavía no tienes cursos</h3>
              <p className="subtitulo">
                Crea el primero arriba. Después matriculas a tus estudiantes por su correo.
              </p>
            </div>
          </div>
        )}

        {cursos && cursos.length > 0 && (
          <div className="tarjeta">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Curso</th>
                  <th>Sección</th>
                  <th>Estudiantes</th>
                </tr>
              </thead>
              <tbody>
                {cursos.map((curso) => (
                  <tr key={curso.id}>
                    <td>
                      <Link to={`/cursos/${curso.id}`}>{curso.name}</Link>
                    </td>
                    <td className="tenue">{curso.section ?? '—'}</td>
                    <td>{curso.student_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}
