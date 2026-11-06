import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, type Course, type CourseMember, type QuestionBank } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { fechaLarga } from '../lib/formato'
import { CrearBancoCurso } from '../components/CrearBancoCurso'
import { EditorPortadaCurso } from '../components/EditorPortadaCurso'
import { NuevaSesion } from './NuevaSesion'

/**
 * Un curso: sus estudiantes, y cómo matricular más.
 *
 * Se matricula **por correo**: el estudiante tiene que haberse registrado antes.
 * Si el correo no existe, o es de un docente, el mensaje es el mismo: distinguirlos
 * le diría a cualquiera quién tiene cuenta y con qué rol.
 */
export function Curso() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const { token } = useAuth()
  const [curso, setCurso] = useState<Course>()
  const [miembrosData, setMiembrosData] = useState<{
    courseId: string
    miembros: CourseMember[]
  }>()
  const [errorCursoCarga, setErrorCursoCarga] = useState<{ courseId: string; message: string }>()
  const [errorMiembrosCarga, setErrorMiembrosCarga] = useState<{
    courseId: string
    message: string
  }>()
  const [errorAccion, setErrorAccion] = useState<string>()
  const [errorEliminarCurso, setErrorEliminarCurso] = useState<string>()
  const [aviso, setAviso] = useState<string>()
  const [correo, setCorreo] = useState('')
  const [matriculando, setMatriculando] = useState(false)
  const [abrirCrearExamen, setAbrirCrearExamen] = useState(false)
  const [abrirCrearBanco, setAbrirCrearBanco] = useState(false)
  const [bancoCreado, setBancoCreado] = useState<QuestionBank>()
  const [eliminandoCurso, setEliminandoCurso] = useState(false)
  const [reintentoMiembros, setReintentoMiembros] = useState(0)

  useEffect(() => {
    let cancelado = false
    api
      .getCourse(id, token)
      .then((datosCurso) => {
        if (cancelado) return
        setCurso(datosCurso)
        setErrorCursoCarga(undefined)
      })
      .catch((fallo: Error) => {
        if (!cancelado) setErrorCursoCarga({ courseId: id, message: fallo.message })
      })
    api
      .listCourseMembers(id, token)
      .then((datosMiembros) => {
        if (cancelado) return
        setMiembrosData({ courseId: id, miembros: datosMiembros })
        setErrorMiembrosCarga(undefined)
      })
      .catch((fallo: Error) => {
        if (!cancelado) setErrorMiembrosCarga({ courseId: id, message: fallo.message })
      })
    return () => {
      cancelado = true
    }
  }, [id, token, reintentoMiembros])

  async function matricular(evento: FormEvent): Promise<void> {
    evento.preventDefault()
    setErrorAccion(undefined)
    setAviso(undefined)
    setMatriculando(true)
    try {
      const resultado = await api.enrollStudent(id, correo, token)
      if (resultado.already_enrolled) {
        setAviso('Ese estudiante ya estaba en el curso.')
      } else {
        setMiembrosData((previos) => ({
          courseId: id,
          miembros: [...(previos?.courseId === id ? previos.miembros : []), resultado.student]
        }))
        setAviso(`${resultado.student.full_name ?? resultado.student.email} se unió al curso.`)
      }
      setCorreo('')
    } catch (fallo) {
      setErrorAccion(fallo instanceof Error ? fallo.message : 'No se pudo matricular')
    } finally {
      setMatriculando(false)
    }
  }

  const cursoActual = curso?.id === id ? curso : undefined
  const miembros = miembrosData?.courseId === id ? miembrosData.miembros : undefined
  const errorCurso = errorCursoCarga?.courseId === id ? errorCursoCarga.message : undefined
  const errorMiembros = errorMiembrosCarga?.courseId === id ? errorMiembrosCarga.message : undefined
  const cerrarCrearExamen = useCallback(() => setAbrirCrearExamen(false), [])
  const cerrarCrearBanco = useCallback(() => setAbrirCrearBanco(false), [])

  async function eliminarCurso(): Promise<void> {
    if (
      !cursoActual ||
      !confirm(
        `¿Eliminar el curso "${cursoActual.name}"? Solo se puede borrar si no tiene estudiantes, exámenes ni bancos asociados.`
      )
    )
      return
    setErrorEliminarCurso(undefined)
    setEliminandoCurso(true)
    try {
      await api.deleteCourse(id, token)
      navigate('/cursos', { replace: true })
    } catch (fallo) {
      setErrorEliminarCurso(fallo instanceof Error ? fallo.message : 'No se pudo eliminar el curso')
    } finally {
      setEliminandoCurso(false)
    }
  }

  if (errorCurso && !cursoActual) {
    return (
      <div className="aviso" role="alert">
        <p>No se pudo cargar el curso: {errorCurso}</p>
        <button
          type="button"
          className="boton boton-secundario"
          onClick={() => setReintentoMiembros((valor) => valor + 1)}
        >
          Volver a cargar el curso
        </button>
      </div>
    )
  }
  if (!cursoActual) return <p className="tenue">Cargando…</p>

  return (
    <>
      <EditorPortadaCurso curso={cursoActual} token={token} onCambio={setCurso} />

      <div className="encabezado-pagina">
        <div>
          <h1>{cursoActual.name}</h1>
          <p className="subtitulo">
            {cursoActual.section ? `Sección ${cursoActual.section} · ` : ''}
            {miembros?.length ?? cursoActual.student_count}{' '}
            {(miembros?.length ?? cursoActual.student_count) === 1 ? 'estudiante' : 'estudiantes'}
          </p>
        </div>
        <div className="fila">
          <button
            type="button"
            className="boton boton-peligro"
            disabled={eliminandoCurso}
            onClick={() => void eliminarCurso()}
          >
            {eliminandoCurso ? 'Eliminando…' : 'Eliminar curso vacío'}
          </button>
          <Link to="/cursos" className="boton boton-secundario">
            Volver a mis cursos
          </Link>
        </div>
      </div>

      <section className="bloque tarjeta">
        <div className="tarjeta-cuerpo">
          <h2>Preparar una evaluación</h2>
          <p className="ayuda">
            Si ya tienes preguntas, crea el examen y selecciónalas allí. Si aún no, prepara un banco
            para reutilizarlas. También puedes crear el examen y añadir preguntas después.
          </p>
          <div className="fila">
            <button type="button" className="boton" onClick={() => setAbrirCrearExamen(true)}>
              Crear examen para este curso
            </button>
            <button
              type="button"
              className="boton boton-secundario"
              onClick={() => setAbrirCrearBanco(true)}
            >
              Crear banco de preguntas
            </button>
            <Link to={`/bancos?curso=${encodeURIComponent(id)}`} className="boton boton-texto">
              Ver bancos del curso
            </Link>
          </div>
        </div>
      </section>

      {abrirCrearExamen && (
        <NuevaSesion comoPanel cursoInicialId={id} onCerrar={cerrarCrearExamen} />
      )}

      {abrirCrearBanco && (
        <CrearBancoCurso
          courseId={id}
          courseName={cursoActual.name}
          onClose={cerrarCrearBanco}
          onCreated={setBancoCreado}
        />
      )}

      {bancoCreado && (
        <p className="aviso aviso-exito" role="status">
          Banco creado: <strong>{bancoCreado.name}</strong>.{' '}
          <Link to={`/bancos/${bancoCreado.id}`}>Agregar preguntas</Link>
        </p>
      )}

      {errorEliminarCurso && (
        <p className="aviso" role="alert">
          {errorEliminarCurso}
        </p>
      )}

      <section className="bloque">
        <div className="tarjeta">
          <div className="tarjeta-cuerpo">
            <h2>Estudiantes del curso</h2>
            <p className="ayuda">
              Añadirlos aquí organiza la lista del curso. Para entrar al examen, cada estudiante
              sigue necesitando el código de acceso que se genera al crearlo.
            </p>
            <form onSubmit={(e) => void matricular(e)} className="formulario-curso">
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
              </label>
              <button type="submit" className="boton" disabled={matriculando || !correo.trim()}>
                {matriculando ? 'Matriculando…' : 'Matricular'}
              </button>
            </form>
            {/* Fuera de la etiqueta: dentro, el `align-items: flex-end` del
                formulario alineaba el botón con el final de esta ayuda en vez
                de con el campo, y quedaba un escalón. */}
            <p className="ayuda">Tiene que haberse registrado antes en el sistema.</p>
            {errorAccion && <p className="aviso">{errorAccion}</p>}
            {aviso && <p className="aviso aviso-neutro">{aviso}</p>}
          </div>
        </div>
      </section>

      <section className="bloque">
        <h2>Estudiantes</h2>
        {errorMiembros ? (
          <div className="aviso" role="alert">
            <p>No se pudo cargar la lista de estudiantes: {errorMiembros}</p>
            <button
              type="button"
              className="boton boton-secundario"
              onClick={() => setReintentoMiembros((valor) => valor + 1)}
            >
              Volver a cargar estudiantes
            </button>
          </div>
        ) : !miembros ? (
          <p className="tenue">Cargando estudiantes…</p>
        ) : miembros.length === 0 ? (
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
                {miembros.map((m) => (
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
