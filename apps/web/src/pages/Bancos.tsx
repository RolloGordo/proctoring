import { useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ImportarPreguntas } from '../components/ImportarPreguntas'
import { api, type Course, type QuestionBank } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { BANCOS_SIN_CURSO, filtrarBancosPorCurso, TODOS_LOS_CURSOS } from '../lib/bank-list'

/**
 * Los bancos del docente.
 *
 * Un banco es un montón de preguntas que no pertenece a ningún examen: se
 * escribe una vez y se reutiliza. Se puede organizar por curso, crear vacío o
 * importarlo directamente desde un archivo.
 */
export function Bancos() {
  const { token } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [bancos, setBancos] = useState<QuestionBank[]>()
  const [cursos, setCursos] = useState<Course[]>([])
  const [error, setError] = useState<string>()
  const [errorBancos, setErrorBancos] = useState<string>()
  const [errorCursos, setErrorCursos] = useState<string>()
  const [reintentoBancos, setReintentoBancos] = useState(0)
  const [reintentoCursos, setReintentoCursos] = useState(0)

  const [nombre, setNombre] = useState('')
  const [cursoId, setCursoId] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [creando, setCreando] = useState(false)
  const [eliminando, setEliminando] = useState<string>()

  useEffect(() => {
    let cancelado = false
    api
      .listBanks(token)
      .then((datos) => {
        if (cancelado) return
        setBancos(datos)
        setErrorBancos(undefined)
      })
      .catch((fallo: Error) => {
        if (!cancelado) setErrorBancos(fallo.message)
      })
    return () => {
      cancelado = true
    }
  }, [token, reintentoBancos])

  useEffect(() => {
    let cancelado = false
    api
      .listCourses(token)
      .then((datos) => {
        if (cancelado) return
        setCursos(datos)
        setErrorCursos(undefined)
      })
      .catch((fallo: Error) => {
        if (cancelado) return
        setErrorCursos(fallo.message)
      })
    return () => {
      cancelado = true
    }
  }, [token, reintentoCursos])

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
      setErrorBancos(undefined)
      setNombre('')
      setDescripcion('')
      setCursoId('')
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo crear el banco')
    } finally {
      setCreando(false)
    }
  }

  async function crearBancoParaImportar(): Promise<QuestionBank> {
    if (!nombre.trim()) throw new Error('Escribe el nombre del banco antes de importar.')
    return api.createBank(
      {
        name: nombre.trim(),
        course_id: cursoId || null,
        description: descripcion.trim() || null
      },
      token
    )
  }

  function actualizarTrasImportacion(
    _bancoId: string,
    _importadas: number,
    completada: boolean
  ): void {
    api
      .listBanks(token)
      .then((datos) => {
        setBancos(datos)
        setErrorBancos(undefined)
      })
      .catch((fallo: Error) => setErrorBancos(fallo.message))
    if (completada) {
      setNombre('')
      setDescripcion('')
      setCursoId('')
    }
  }

  async function eliminar(banco: QuestionBank): Promise<void> {
    if (
      !confirm(
        `¿Eliminar el banco "${banco.name}" y sus ${banco.question_count} preguntas? Esta acción no se puede deshacer.`
      )
    ) {
      return
    }
    setError(undefined)
    setEliminando(banco.id)
    try {
      await api.deleteBank(banco.id, token)
      setBancos((previos) => (previos ?? []).filter((item) => item.id !== banco.id))
      setErrorBancos(undefined)
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo eliminar el banco')
    } finally {
      setEliminando(undefined)
    }
  }

  const totalPreguntas = (bancos ?? []).reduce((suma, b) => suma + b.question_count, 0)
  const filtroCurso = searchParams.get('curso') ?? TODOS_LOS_CURSOS
  const bancosVisibles = filtrarBancosPorCurso(bancos ?? [], filtroCurso)
  const tieneBancosSinCurso = (bancos ?? []).some((banco) => banco.course_id === null)
  const cursoPorId = new Map(cursos.map((curso) => [curso.id, curso]))

  function cambiarFiltroCurso(curso: string): void {
    const nuevosParametros = new URLSearchParams(searchParams)
    if (curso === TODOS_LOS_CURSOS) nuevosParametros.delete('curso')
    else nuevosParametros.set('curso', curso)
    setSearchParams(nuevosParametros)
  }

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
      {errorBancos && (
        <div className="aviso" role="alert">
          <p>No se pudieron cargar tus bancos: {errorBancos}</p>
          <button
            type="button"
            className="boton boton-secundario"
            onClick={() => setReintentoBancos((valor) => valor + 1)}
          >
            Volver a cargar bancos
          </button>
        </div>
      )}
      {errorCursos && (
        <div className="aviso" role="alert">
          <p>No se pudieron cargar tus cursos: {errorCursos}</p>
          <button
            type="button"
            className="boton boton-secundario"
            onClick={() => setReintentoCursos((valor) => valor + 1)}
          >
            Volver a cargar cursos
          </button>
          <Link to="/cursos" className="boton boton-secundario">
            Ir a mis cursos
          </Link>
        </div>
      )}

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
                  {cursos.length === 0 && !errorCursos ? (
                    <p className="ayuda">
                      Aún no tienes cursos. Puedes crear el banco sin curso o{' '}
                      <Link to="/cursos">crear un curso primero</Link>.
                    </p>
                  ) : (
                    <p className="ayuda">
                      Asociarlo ayuda a organizar tus bancos. También puedes usar un banco en
                      cualquiera de tus exámenes.
                    </p>
                  )}
                </label>

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
              <hr className="separador" />
              <ImportarPreguntas
                nombreBanco={nombre}
                crearBanco={crearBancoParaImportar}
                onImportado={actualizarTrasImportacion}
              />
            </div>
          </div>
        </section>

        <section>
          <div className="encabezado-seccion">
            <h2>Mis bancos</h2>
          </div>

          {bancos && bancos.length > 0 && (
            <label className="campo">
              <span>Ver bancos de</span>
              <select
                value={filtroCurso}
                onChange={(evento) => cambiarFiltroCurso(evento.target.value)}
              >
                <option value={TODOS_LOS_CURSOS}>Todos mis cursos</option>
                {cursos.map((curso) => (
                  <option key={curso.id} value={curso.id}>
                    {curso.name}
                    {curso.section ? ` — sección ${curso.section}` : ''}
                  </option>
                ))}
                {tieneBancosSinCurso && <option value={BANCOS_SIN_CURSO}>Sin curso</option>}
              </select>
              <span className="ayuda">
                {bancosVisibles.length} de {bancos.length} banco
                {bancos.length === 1 ? '' : 's'}
              </span>
            </label>
          )}

          {!bancos && !errorBancos && <p className="tenue">Cargando tus bancos…</p>}
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
          ) : bancos ? (
            bancosVisibles.length === 0 ? (
              <div className="tarjeta">
                <div className="vacio">
                  <h3>No hay bancos en este curso</h3>
                  <p className="subtitulo">
                    Puedes cambiar el filtro o crear un banco y asociarlo a este curso.
                  </p>
                  <button
                    type="button"
                    className="boton boton-secundario"
                    onClick={() => cambiarFiltroCurso(TODOS_LOS_CURSOS)}
                  >
                    Ver todos los bancos
                  </button>
                </div>
              </div>
            ) : (
              <ul className="lista-bancos">
                {bancosVisibles.map((banco) => (
                  <li key={banco.id} className="tarjeta">
                    <div className="tarjeta-cuerpo">
                      <div className="fila" style={{ justifyContent: 'space-between' }}>
                        <h4>{banco.name}</h4>
                        <span className="tenue">
                          {banco.question_count} pregunta{banco.question_count === 1 ? '' : 's'}
                        </span>
                      </div>
                      <p className="ayuda">
                        {banco.course_id
                          ? `Curso: ${cursoPorId.get(banco.course_id)?.name ?? 'curso asociado'}`
                          : 'Sin curso · disponible para cualquiera de tus exámenes'}
                      </p>
                      {banco.description && <p className="ayuda">{banco.description}</p>}
                      <div className="fila fila-banco-acciones" style={{ marginTop: 'var(--e2)' }}>
                        <Link to={`/bancos/${banco.id}`} className="boton boton-secundario">
                          Ver y añadir preguntas
                        </Link>
                        <button
                          type="button"
                          className="boton boton-peligro"
                          disabled={eliminando !== undefined}
                          onClick={() => void eliminar(banco)}
                        >
                          {eliminando === banco.id ? 'Eliminando…' : 'Eliminar banco'}
                        </button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )
          ) : null}
        </section>
      </div>
    </>
  )
}
