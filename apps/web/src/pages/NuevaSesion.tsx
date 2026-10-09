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
    detalle: 'Añade copiar/pegar, monitores adicionales, mirada y persona extra.'
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
  const [fecha, setFecha] = useState(valorFechaPorDefecto())
  const [duracion, setDuracion] = useState(90)
  const [tolerancia, setTolerancia] = useState(10)
  const [guardarCodigo, setGuardarCodigo] = useState(false)
  const [preset, setPreset] = useState<SupervisionPreset>('standard')
  const [descripcion, setDescripcion] = useState('')
  const [cursos, setCursos] = useState<Course[]>([])
  const [cursoId, setCursoId] = useState('')
  const [bancos, setBancos] = useState<QuestionBank[]>([])
  const [elegidos, setElegidos] = useState<string[]>([])
  const [cuantas, setCuantas] = useState('')
  const [error, setError] = useState<string>()
  const [enviando, setEnviando] = useState(false)

  // Cursos y bancos son opcionales: si no se pueden cargar, el examen se crea
  // igual, solo que sin curso y sin bancos.
  useEffect(() => {
    let cancelado = false
    api
      .listCourses(token)
      .then((datos) => !cancelado && setCursos(datos))
      .catch(() => undefined)
    api
      .listBanks(token)
      .then((datos) => !cancelado && setBancos(datos))
      .catch(() => undefined)
    return () => {
      cancelado = true
    }
  }, [token])

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
    setEnviando(true)
    try {
      const sesion = await api.createSession(
        {
          title: titulo,
          // El input datetime-local da hora local sin zona; la API exige UTC.
          starts_at: new Date(fecha).toISOString(),
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
        setError(
          `El examen se creó, pero no se pudieron atar estos bancos: ${fallidos.join(', ')}. ` +
            'Puedes atarlos desde la pantalla del examen.'
        )
        setEnviando(false)
        return
      }

      navegar(`/sesiones/${sesion.id}`)
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo crear el examen')
      setEnviando(false)
    }
  }

  const elegido = PRESETS.find((p) => p.valor === preset)
  const demasiadas = Boolean(cuantas) && Number(cuantas) > disponibles && disponibles > 0

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>Crear examen</h1>
          <p className="subtitulo">
            Elige de qué bancos salen las preguntas y obtendrás el código de acceso para repartir
          </p>
        </div>
      </div>

      <div className="tarjeta" style={{ maxWidth: '760px' }}>
        <div className="tarjeta-cuerpo">
          <form onSubmit={(e) => void enviar(e)} noValidate>
            {error && <p className="aviso">{error}</p>}

            <label className="campo">
              <span>Título del examen</span>
              <input
                value={titulo}
                onChange={(e) => setTitulo(e.target.value)}
                maxLength={200}
                required
              />
            </label>

            <div className="rejilla-campos">
              <label className="campo">
                <span>Fecha y hora de inicio</span>
                <input
                  type="datetime-local"
                  value={fecha}
                  onChange={(e) => setFecha(e.target.value)}
                  required
                />
              </label>

              <label className="campo">
                <span>Duración (minutos)</span>
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
                Hasta la hora de inicio no se muestra en ninguna pantalla, tampoco en la tuya. Un
                código que puedes leer con dos días de antelación es un código que puede circular
                con dos días de antelación.
              </p>
            </div>

            <div className="campo">
              <span>Preguntas</span>
              {bancos.length === 0 ? (
                <p className="ayuda">
                  No tienes bancos todavía. Puedes crear el examen y escribir las preguntas
                  después, pero conviene{' '}
                  <Link to="/bancos">crear un banco</Link> y escribirlas una sola vez: así se
                  reutilizan y cada estudiante recibe un sorteo distinto.
                </p>
              ) : (
                <>
                  <p className="ayuda" style={{ marginBottom: 0 }}>
                    Marca de qué bancos sale este examen. Si no marcas ninguno, escribirás las
                    preguntas a mano después.
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
                          <span>{banco.name}</span>
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
              {elegido && <p className="ayuda">{elegido.detalle}</p>}
            </label>

            {cursos.length > 0 && (
              <label className="campo">
                <span>Curso (opcional)</span>
                <select value={cursoId} onChange={(e) => setCursoId(e.target.value)}>
                  <option value="">Sin curso</option>
                  {cursos.map((curso) => (
                    <option key={curso.id} value={curso.id}>
                      {curso.name}
                      {curso.section ? ` — sección ${curso.section}` : ''}
                    </option>
                  ))}
                </select>
                <p className="ayuda">
                  Los estudiantes del curso verán la fecha del examen en su panel. Para rendirlo
                  siguen necesitando el código de acceso.
                </p>
              </label>
            )}

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

/** Mañana a las 08:00, en el formato que espera `datetime-local`. */
function valorFechaPorDefecto(): string {
  const manana = new Date()
  manana.setDate(manana.getDate() + 1)
  manana.setHours(8, 0, 0, 0)
  const pad = (n: number): string => String(n).padStart(2, '0')
  return `${manana.getFullYear()}-${pad(manana.getMonth() + 1)}-${pad(manana.getDate())}T${pad(manana.getHours())}:${pad(manana.getMinutes())}`
}
