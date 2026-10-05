import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type Course, type CourseMember } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { fechaLarga } from '../lib/formato'

/**
 * Un curso: sus estudiantes, y cómo matricular más.
 *
 * Se matricula **por correo**: el estudiante tiene que haberse registrado antes.
 * Si el correo no existe, o es de un docente, el mensaje es el mismo: distinguirlos
 * le diría a cualquiera quién tiene cuenta y con qué rol.
 */
export function Curso() {
  const { id = '' } = useParams()
  const { token } = useAuth()
  const [curso, setCurso] = useState<Course>()
  const [miembros, setMiembros] = useState<CourseMember[]>()
  const [error, setError] = useState<string>()
  const [aviso, setAviso] = useState<string>()
  const [correo, setCorreo] = useState('')
  const [matriculando, setMatriculando] = useState(false)

  useEffect(() => {
    let cancelado = false
    Promise.all([api.getCourse(id, token), api.listCourseMembers(id, token)])
      .then(([datosCurso, datosMiembros]) => {
        if (cancelado) return
        setCurso(datosCurso)
        setMiembros(datosMiembros)
      })
      .catch((fallo: Error) => !cancelado && setError(fallo.message))
    return () => {
      cancelado = true
    }
  }, [id, token])

  async function matricular(evento: FormEvent): Promise<void> {
    evento.preventDefault()
    setError(undefined)
    setAviso(undefined)
    setMatriculando(true)
    try {
      const resultado = await api.enrollStudent(id, correo, token)
      if (resultado.already_enrolled) {
        setAviso('Ese estudiante ya estaba en el curso.')
      } else {
        setMiembros((previos) => [...(previos ?? []), resultado.student])
        setAviso(`${resultado.student.full_name ?? resultado.student.email} se unió al curso.`)
      }
      setCorreo('')
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo matricular')
    } finally {
      setMatriculando(false)
    }
  }

  if (error && !curso) return <p className="aviso">{error}</p>
  if (!curso) return <p className="tenue">Cargando…</p>

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>{curso.name}</h1>
          <p className="subtitulo">
            {curso.section ? `Sección ${curso.section} · ` : ''}
            {miembros?.length ?? curso.student_count}{' '}
            {(miembros?.length ?? curso.student_count) === 1 ? 'estudiante' : 'estudiantes'}
          </p>
        </div>
        <Link to="/cursos" className="boton boton-secundario">
          Volver a mis cursos
        </Link>
      </div>

      <section className="bloque">
        <div className="tarjeta">
          <div className="tarjeta-cuerpo">
            <h2>Matricular a un estudiante</h2>
            <form onSubmit={(e) => void matricular(e)} noValidate className="formulario-curso">
              <label className="campo">
                <span>Correo del estudiante</span>
                <input
                  type="email"
                  value={correo}
                  onChange={(e) => setCorreo(e.target.value)}
                  placeholder="estudiante@upao.edu.pe"
                  autoComplete="off"
                  required
                />
                <p className="ayuda">Tiene que haberse registrado antes en el sistema.</p>
              </label>
              <button type="submit" className="boton" disabled={matriculando || !correo.trim()}>
                {matriculando ? 'Matriculando…' : 'Matricular'}
              </button>
            </form>
            {error && <p className="aviso">{error}</p>}
            {aviso && <p className="aviso aviso-neutro">{aviso}</p>}
          </div>
        </div>
      </section>

      <section className="bloque">
        <h2>Estudiantes</h2>
        {miembros?.length === 0 ? (
          <div className="tarjeta">
            <div className="vacio">
              <h3>Nadie está matriculado todavía</h3>
              <p className="subtitulo">Escribe el correo de un estudiante arriba.</p>
            </div>
          </div>
        ) : (
          <div className="tarjeta">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Correo</th>
                  <th>Se unió</th>
                </tr>
              </thead>
              <tbody>
                {miembros?.map((m) => (
                  <tr key={m.student_id}>
                    <td>{m.full_name ?? <span className="tenue">Sin perfil</span>}</td>
                    <td className="tenue">{m.email ?? '—'}</td>
                    <td className="hora">{fechaLarga(m.enrolled_at)}</td>
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
