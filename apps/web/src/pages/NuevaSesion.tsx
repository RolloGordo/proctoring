import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type Course, type QuestionBank, type SupervisionPreset } from '../lib/api'
import { useAuth } from '../lib/auth-context'

/**
 * Qué vigila cada nivel. El texto sale de `PRESET_MODULES` en el dominio de la
 * API: si allí cambian los módulos, hay que actualizar esta descripción.
 */
const PRESETS: Array<{ valor: SupervisionPreset; nombre: string; detalle: string }> = [
  {
    valor: 'basic',
    nombre: 'Básica',
    detalle: 'Identidad y salida de la ventana del examen.'
  },
  {
    valor: 'standard',
    nombre: 'Estándar',
    detalle: 'Añade copiar/pegar, monitores, mirada, persona extra y detección de celulares.'
  },
  {
    valor: 'strict',
    nombre: 'Estricta',
    detalle:
      'Añade reverificación de identidad, voces externas, consulta a IA por voz, captura de pantalla y monitoreo en vivo.'
  }
]

export function NuevaSesion() {
  const { token } = useAuth()
  const navegar = useNavigate()
  const [titulo, setTitulo] = useState('')
  const [inicio, setInicio] = useState(inicioPorDefecto)
  const [duracion, setDuracion] = useState(90)
  const [tolerancia, setTolerancia] = useState(10)
  const [guardarCodigo, setGuardarCodigo] = useState(false)
  const [preset, setPreset] = useState<SupervisionPreset>('standard')
  const [descripcion, setDescripcion] = useState('')
  const [cursos, setCursos] = useState<Course[]>([])
  const [cargandoCursos, setCargandoCursos] = useState(true)
  const [errorCursos, setErrorCursos] = useState<string>()
  const [reintentoCursos, setReintentoCursos] = useState(0)
  const [cursoId, setCursoId] = useState('')
  const [bancos, setBancos] = useState<QuestionBank[]>([])
  const [cargandoBancos, setCargandoBancos] = useState(true)
  const [errorBancos, setErrorBancos] = useState<string>()
  const [reintentoBancos, setReintentoBancos] = useState(0)
  const [elegidos, setElegidos] = useState<string[]>([])
  const [cuantas, setCuantas] = useState('')
  const [error, setError] = useState<string>()
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    let cancelado = false
    api
      .listCourses(token)
      .then((datos) => {
        if (cancelado) return
        setCursos(datos)
        setErrorCursos(undefined)
      })
      .catch((fallo: Error) => !cancelado && setErrorCursos(fallo.message))
      .finally(() => !cancelado && setCargandoCursos(false))
    return () => {
      cancelado = true
    }
  }, [token, reintentoCursos])

  useEffect(() => {
    let cancelado = false
    api
      .listBanks(token)
      .then((datos) => {
        if (cancelado) return
        setBancos(datos)
        setErrorBancos(undefined)
      })
      .catch((fallo: Error) => !cancelado && setErrorBancos(fallo.message))
      .finally(() => !cancelado && setCargandoBancos(false))
    return () => {
      cancelado = true
    }
  }, [token, reintentoBancos])

  const disponibles = bancos
    .filter((b) => elegidos.includes(b.id))
    .reduce((suma, b) => suma + b.question_count, 0)

  function alternar(bankId: string): void {
    setElegidos((previos) =>
      previos.includes(bankId) ? previos.filter((i) => i !== bankId) : [...previos, bankId]
    )
  }

  async function enviar(evento: FormEvent): Promise<void> {
    evento.preventDefault()
    setError(undefined)
    if (!titulo.trim()) {
      setError('Escribe el título del examen.')
      return
    }
    setEnviando(true)
    try {
      const sesion = await api.createSession(
        {
          title: titulo.trim(),
          // El input datetime-local da hora local sin zona; la API exige UTC.
          starts_at: new Date(`${inicio.fecha}T${inicio.hora}`).toISOString(),
          duration_minutes: duracion,
          entry_tolerance_minutes: tolerancia,
          preset,
          description: descripcion.trim() || null,
          course_id: cursoId || null,
          // Vacío significa "todas las del banco".
          question_pool_size: cuantas ? Number(cuantas) : null,
          reveal_code_at_start: guardarCodigo
        },
        token
      )

      // Los bancos se atan después porque el examen tiene que existir primero.
      // Si uno falla, el examen ya está creado: se avisa y se deja al docente en
      // la pantalla del examen, donde puede atarlos a mano, en vez de perderlo.
      const fallidos: string[] = []
      for (const bankId of elegidos) {
        try {
          await api.attachBank(sesion.id, bankId, token)
        } catch {
          fallidos.push(bancos.find((b) => b.id === bankId)?.name ?? bankId)
        }
      }

      if (fallidos.length > 0) {
        navegar(`/sesiones/${sesion.id}`, {
          state: {
            aviso:
              `El examen se creó, pero no se pudieron asociar estos bancos: ${fallidos.join(', ')}. ` +
              'Asócialos desde «Bancos de preguntas» en el examen antes de compartir el código.'
          }
        })
        return
      }

      navegar(`/sesiones/${sesion.id}`)
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo crear el examen')
      setEnviando(false)
    }
  }

  function reintentarCursos(): void {
    setCargandoCursos(true)
    setErrorCursos(undefined)
    setReintentoCursos((valor) => valor + 1)
  }

  function reintentarBancos(): void {
    setCargandoBancos(true)
    setErrorBancos(undefined)
    setReintentoBancos((valor) => valor + 1)
  }

  const elegido = PRESETS.find((p) => p.valor === preset)
  const demasiadas = Boolean(cuantas) && Number(cuantas) > disponibles && disponibles > 0
  const cursoPorId = new Map(cursos.map((curso) => [curso.id, curso]))

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>Crear examen</h1>
          <p className="subtitulo">
            Completa los datos, elige las preguntas y al final obtendrás un código de acceso.
          </p>
        </div>
      </div>

      <div className="tarjeta" style={{ maxWidth: '760px' }}>
        <div className="tarjeta-cuerpo">
          <form onSubmit={(e) => void enviar(e)}>
            {error && (
              <p className="aviso" role="alert">
                {error}
              </p>
            )}

            <section className="bloque">
              <h2>1. Datos del examen</h2>
            </section>
            <label className="campo">
              <span>Título del examen (obligatorio)</span>
              <input
                value={titulo}
                onChange={(e) => setTitulo(e.target.value)}
                maxLength={200}
                required
              />
            </label>

            <label className="campo">
              <span>Curso (opcional)</span>
              {cursos.length > 0 ? (
                <select value={cursoId} onChange={(e) => setCursoId(e.target.value)}>
                  <option value="">Sin curso</option>
                  {cursos.map((curso) => (
                    <option key={curso.id} value={curso.id}>
                      {curso.name}
                      {curso.section ? ` — sección ${curso.section}` : ''}
                    </option>
                  ))}
                </select>
              ) : (
                <span className="ayuda">
                  {cargandoCursos
                    ? 'Cargando cursos…'
                    : errorCursos
                      ? 'No se pudieron cargar los cursos; puedes reintentar o continuar sin asociar uno.'
                      : 'No tienes cursos todavía. Puedes crear el examen sin asociarlo a un curso.'}
                </span>
              )}
              {errorCursos && (
                <span className="fila">
                  <span className="ayuda" role="alert">
                    {errorCursos}
                  </span>
                  <button
                    type="button"
                    className="boton boton-secundario"
                    onClick={reintentarCursos}
                  >
                    Reintentar cursos
                  </button>
                </span>
              )}
              {cursos.length > 0 && (
                <span className="ayuda">
                  Asociarlo ayuda a organizar los exámenes; los estudiantes aún necesitan el código
                  para ingresar.
                </span>
              )}
            </label>

            <section className="bloque">
              <h2>Horario</h2>
              <p className="ayuda">
                La fecha y la hora se interpretan según la zona horaria de este equipo.
              </p>
            </section>
            <div className="rejilla-campos rejilla-horario">
              <label className="campo">
                <span>Fecha de inicio (obligatorio)</span>
                <input
                  type="date"
                  value={inicio.fecha}
                  onChange={(e) => setInicio((actual) => ({ ...actual, fecha: e.target.value }))}
                  required
                />
              </label>

              <label className="campo">
                <span>Hora de inicio (obligatorio)</span>
                <input
                  type="time"
                  value={inicio.hora}
                  onChange={(e) => setInicio((actual) => ({ ...actual, hora: e.target.value }))}
                  required
                />
              </label>

              <label className="campo">
                <span>Duración (minutos, obligatorio)</span>
                <input
                  type="number"
                  min={1}
                  max={600}
                  value={duracion}
                  onChange={(e) => setDuracion(Number(e.target.value))}
                  required
                />
              </label>

              <label className="campo">
                <span>Tolerancia de ingreso (minutos)</span>
                <input
                  type="number"
                  min={0}
                  max={120}
                  value={tolerancia}
                  onChange={(e) => setTolerancia(Number(e.target.value))}
                />
              </label>
            </div>

            <div className="campo">
              <label className="casilla">
                <input
                  type="checkbox"
                  checked={guardarCodigo}
                  onChange={(e) => setGuardarCodigo(e.target.checked)}
                />
                <span>Mostrar el código de acceso solo al empezar</span>
              </label>
              <p className="ayuda">
                Si marcas esta opción, el código no se mostrará antes de la hora de inicio, tampoco
                en tu pantalla.
              </p>
            </div>

            <section className="bloque">
              <h2>2. Preguntas del examen</h2>
            </section>
            <div className="campo">
              <span>Bancos de preguntas (opcional)</span>
              {cargandoBancos ? (
                <p className="tenue">Cargando bancos…</p>
              ) : errorBancos ? (
                <div className="aviso" role="alert">
                  <p>No se pudo cargar la lista de bancos: {errorBancos}</p>
                  <button
                    type="button"
                    className="boton boton-secundario"
                    onClick={reintentarBancos}
                  >
                    Reintentar bancos
                  </button>
                  <p className="ayuda">
                    Si continúas sin un banco, podrás añadir preguntas después, pero primero
                    verifica que no estés dejando fuera uno que querías usar.
                  </p>
                </div>
              ) : bancos.length === 0 ? (
                <p className="ayuda">
                  Aún no tienes bancos. Puedes <Link to="/bancos">crear o importar un banco</Link>,
                  o continuar y escribir preguntas en el examen después.
                </p>
              ) : (
                <>
                  <p className="ayuda" style={{ marginBottom: 0 }}>
                    Selecciona uno o más bancos. Las preguntas se tomarán de estos bancos; si no
                    marcas ninguno, podrás añadir preguntas directamente al examen.
                  </p>
                  <ul className="selector-bancos">
                    {bancos.map((banco) => (
                      <li key={banco.id}>
                        <label>
                          <input
                            type="checkbox"
                            checked={elegidos.includes(banco.id)}
                            onChange={() => alternar(banco.id)}
                          />
                          <span className="selector-banco-detalle">
                            <strong>{banco.name}</strong>
                            <span className="ayuda">
                              {banco.course_id
                                ? `Curso: ${cursoPorId.get(banco.course_id)?.name ?? 'asociado'}`
                                : 'Sin curso'}
                            </span>
                          </span>
                          <span className="cuenta">
                            {banco.question_count} pregunta{banco.question_count === 1 ? '' : 's'}
                          </span>
                        </label>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>

            {elegidos.length > 0 && (
              <label className="campo" style={{ maxWidth: '280px' }}>
                <span>Preguntas por estudiante</span>
                <input
                  type="number"
                  min={1}
                  max={disponibles || undefined}
                  value={cuantas}
                  onChange={(e) => setCuantas(e.target.value)}
                  placeholder={`Todas (${disponibles})`}
                />
                <p className="ayuda">
                  De las {disponibles} disponibles. Cada estudiante recibe su propio sorteo, y
                  siempre el mismo aunque recargue la página.
                </p>
                {demasiadas && (
                  <p className="aviso">
                    Solo hay {disponibles} preguntas en los bancos marcados. Cada estudiante
                    recibirá esas {disponibles}.
                  </p>
                )}
              </label>
            )}

            <section className="bloque">
              <h2>3. Supervisión y otras indicaciones</h2>
            </section>
            <label className="campo">
              <span>Nivel de supervisión</span>
              <select
                value={preset}
                onChange={(e) => setPreset(e.target.value as SupervisionPreset)}
              >
                {PRESETS.map((p) => (
                  <option key={p.valor} value={p.valor}>
                    {p.nombre}
                  </option>
                ))}
              </select>
              {elegido && <span className="ayuda">{elegido.detalle}</span>}
            </label>

            <label className="campo">
              <span>Indicaciones para el estudiante (opcional)</span>
              <textarea
                rows={3}
                value={descripcion}
                onChange={(e) => setDescripcion(e.target.value)}
                maxLength={2000}
              />
            </label>

            <div className="fila">
              <button type="submit" className="boton" disabled={enviando}>
                {enviando ? 'Creando…' : 'Crear examen'}
              </button>
              <button
                type="button"
                className="boton boton-secundario"
                onClick={() => navegar('/sesiones')}
              >
                Cancelar
              </button>
            </div>
          </form>
        </div>
      </div>
    </>
  )
}

/** Mañana a las 08:00 en la zona horaria local. */
function inicioPorDefecto(): { fecha: string; hora: string } {
  const manana = new Date()
  manana.setDate(manana.getDate() + 1)
  manana.setHours(8, 0, 0, 0)
  const pad = (n: number): string => String(n).padStart(2, '0')
  return {
    fecha: `${manana.getFullYear()}-${pad(manana.getMonth() + 1)}-${pad(manana.getDate())}`,
    hora: `${pad(manana.getHours())}:${pad(manana.getMinutes())}`
  }
}
