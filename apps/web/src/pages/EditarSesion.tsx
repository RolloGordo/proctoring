import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  api,
  type ExamSession,
  type ExamSessionChanges,
  type SupervisionModule,
  type SupervisionPreset
} from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { MODULOS_DE_PRESET, comoModulosElegidos, modulo } from '../lib/modulos'
import { SelectorModulos } from '../components/SelectorModulos'

const PRESETS: Array<{ valor: SupervisionPreset; nombre: string }> = [
  { valor: 'basic', nombre: 'Básica' },
  { valor: 'standard', nombre: 'Estándar' },
  { valor: 'strict', nombre: 'Estricta' },
  { valor: 'custom', nombre: 'Personalizada' }
]

/** Los módulos que tiene guardados un examen, solo los que se conocen. */
function modulosDe(sesion: ExamSession): Set<SupervisionModule> {
  return new Set(
    Object.keys(sesion.modules)
      .filter((id) => modulo(id))
      .map((id) => id as SupervisionModule)
  )
}

function mismos(a: ReadonlySet<string>, b: ReadonlySet<string>): boolean {
  return a.size === b.size && [...a].every((x) => b.has(x))
}

/**
 * Corregir un examen ya creado, cancelarlo o borrarlo.
 *
 * Las dos acciones del final no son la misma cosa y la pantalla lo dice: borrar
 * solo funciona si nadie entró, y en cuanto hay un estudiante lo que corresponde
 * es cancelar, que conserva la evidencia.
 */
export function EditarSesion({ enPanel = false }: { enPanel?: boolean }) {
  const { id = '' } = useParams()
  const { token } = useAuth()
  const navegar = useNavigate()

  const [sesion, setSesion] = useState<ExamSession>()
  const [error, setError] = useState<string>()
  const [aviso, setAviso] = useState<string>()
  const [guardando, setGuardando] = useState(false)

  const [titulo, setTitulo] = useState('')
  const [fecha, setFecha] = useState('')
  const [hora, setHora] = useState('')
  const [duracion, setDuracion] = useState(90)
  const [tolerancia, setTolerancia] = useState(10)
  const [preset, setPreset] = useState<SupervisionPreset>('standard')
  const [modulos, setModulos] = useState<Set<SupervisionModule>>(new Set())
  const [notaMaxima, setNotaMaxima] = useState('20')
  const [cantidadPreguntas, setCantidadPreguntas] = useState('')
  const [cantidadBancos, setCantidadBancos] = useState(0)
  const [descripcion, setDescripcion] = useState('')
  const [guardarCodigo, setGuardarCodigo] = useState(false)
  /** Si ya entró alguien, el nivel de supervisión deja de poderse cambiar. */
  const [hayEstudiantes, setHayEstudiantes] = useState(false)

  useEffect(() => {
    // Si esto falla no se bloquea nada: la API rechaza el cambio igual.
    api
      .listParticipants(id, token)
      .then((lista) => setHayEstudiantes(lista.length > 0))
      .catch(() => undefined)
  }, [id, token])

  useEffect(() => {
    api
      .getSession(id, token)
      .then((datos) => {
        setSesion(datos)
        setTitulo(datos.title)
        const inicio = aLocal(datos.starts_at)
        setFecha(inicio.fecha)
        setHora(inicio.hora)
        setDuracion(datos.duration_minutes)
        setTolerancia(datos.entry_tolerance_minutes)
        // Antes un examen personalizado se cargaba como «estándar», y al guardar
        // cualquier otra cosa se quedaba estándar sin que nadie lo pidiera.
        setPreset(datos.preset)
        setModulos(modulosDe(datos))
        setNotaMaxima(String(Number(datos.max_score)))
        setCantidadPreguntas(datos.question_pool_size === null ? '' : String(datos.question_pool_size))
        setDescripcion(datos.description ?? '')
        setGuardarCodigo(datos.reveal_code_at_start)
      })
      .catch((fallo: Error) => setError(fallo.message))
  }, [id, token])

  useEffect(() => {
    api.listSessionBanks(id, token)
      .then((bancos) => setCantidadBancos(bancos.length))
      .catch(() => setCantidadBancos(0))
  }, [id, token])

  async function guardar(evento: FormEvent): Promise<void> {
    evento.preventDefault()
    setError(undefined)
    setAviso(undefined)
    if (preset === 'custom' && modulos.size === 0) {
      setError('Elige al menos un módulo de supervisión, o un nivel ya armado.')
      return
    }
    // Lo que vigila el examen solo viaja si cambió: con estudiantes dentro la
    // API lo rechaza, y reenviar lo mismo no tiene por qué contar como cambio.
    const supervision: ExamSessionChanges = {}
    if (sesion && preset !== sesion.preset) supervision.preset = preset
    if (preset === 'custom' && (!sesion || !mismos(modulos, modulosDe(sesion)))) {
      supervision.preset = 'custom'
      supervision.modules = comoModulosElegidos(modulos)
    }
    setGuardando(true)
    try {
      // Rider: el título se edita en la cabecera del editor (`enPanel`), y lo
      // que no se puede cambiar con estudiantes dentro solo viaja si cambió.
      // HU-031: la supervisión (nivel y módulos) va en `supervision`, que ya
      // solo lleva lo que cambió.
      const cambios: ExamSessionChanges = {
        ...(enPanel ? {} : { title: titulo }),
        starts_at: new Date(`${fecha}T${hora}`).toISOString(),
        duration_minutes: duracion,
        entry_tolerance_minutes: tolerancia,
        reveal_code_at_start: guardarCodigo,
        // Vaciar la descripción necesita el `clear_`: con `undefined` el
        // backend entiende "no lo cambies".
        ...(descripcion.trim()
          ? { description: descripcion.trim() }
          : { clear_description: true }),
        ...(hayEstudiantes ? {} : supervision),
        ...(sesion && Number(notaMaxima) !== Number(sesion.max_score) && !hayEstudiantes
          ? { max_score: notaMaxima }
          : {}),
        ...(sesion &&
        cantidadPreguntas !==
          (sesion.question_pool_size === null ? '' : String(sesion.question_pool_size)) &&
        !hayEstudiantes
          ? cantidadPreguntas.trim()
            ? { question_pool_size: Number(cantidadPreguntas) }
            : { clear_pool_size: true }
          : {})
      }
      const actualizada = await api.updateSession(id, cambios, token)
      setSesion(actualizada)
      setModulos(modulosDe(actualizada))
      setAviso('Cambios guardados.')
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudieron guardar los cambios')
    } finally {
      setGuardando(false)
    }
  }

  async function cancelar(): Promise<void> {
    if (
      !confirm(
        'Se cancelará el examen. Su código dejará de servir y los estudiantes que lo usen ' +
          'verán que lo cancelaste. Lo que ya ocurrió se conserva. ¿Seguro?'
      )
    ) {
      return
    }
    setError(undefined)
    try {
      setSesion(await api.cancelSession(id, token))
      setAviso('El examen quedó cancelado.')
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo cancelar')
    }
  }

  async function borrar(): Promise<void> {
    if (!confirm('Se borrará el examen para siempre. ¿Seguro?')) return
    setError(undefined)
    try {
      await api.deleteSession(id, token)
      navegar('/sesiones')
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo borrar')
    }
  }

  if (error && !sesion) return <p className="aviso">{error}</p>
  if (!sesion) return <p className="tenue">Cargando examen…</p>

  const cancelado = sesion.status === 'cancelled'

  return (
    <div className={enPanel ? 'configuracion-examen-panel' : 'configuracion-examen-pagina'}>
      {!enPanel && <div className="encabezado-pagina">
        <div>
          <h1>Editar examen</h1>
          <p className="subtitulo">
            {sesion.access_code === null ? (
              <>El código se genera automáticamente y se revela al empezar; no se puede editar.</>
            ) : (
              <>
                Código generado automáticamente <strong>{sesion.access_code}</strong> — no se puede
                editar, aunque cambies el resto del examen
              </>
            )}
          </p>
        </div>
        <Link to={`/sesiones/${id}`} className="boton boton-secundario">
          Volver al examen
        </Link>
      </div>}

      {error && <p className="aviso">{error}</p>}
      {aviso && <p className="aviso aviso-neutro">{aviso}</p>}

      {cancelado && (
        <p className="aviso">
          Este examen está cancelado, así que ya no se edita. Sus estudiantes ven que lo cancelaste.
        </p>
      )}

      <div className="tarjeta configuracion-examen-tarjeta">
        <div className="tarjeta-cuerpo">
          <form onSubmit={(e) => void guardar(e)} noValidate>
            <fieldset disabled={cancelado} style={{ border: 0, padding: 0, margin: 0 }}>
              {!enPanel && <label className="campo">
                <span>Título del examen</span>
                <input
                  value={titulo}
                  onChange={(e) => setTitulo(e.target.value)}
                  maxLength={200}
                  required
                />
              </label>}

              <div className="rejilla-campos rejilla-horario">
                <label className="campo">
                  <span>Fecha de inicio</span>
                  <input
                    type="date"
                    value={fecha}
                    onChange={(e) => setFecha(e.target.value)}
                    required
                  />
                </label>

                <label className="campo">
                  <span>Hora de inicio</span>
                  <input
                    type="time"
                    value={hora}
                    onChange={(e) => setHora(e.target.value)}
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

                <label className="campo">
                  <span>Nota máxima</span>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    step="0.5"
                    value={notaMaxima}
                    disabled={hayEstudiantes}
                    onChange={(e) => setNotaMaxima(e.target.value)}
                  />
                </label>
              </div>

              {(cantidadBancos > 0 || sesion.question_pool_size !== null) && (
                <label className="campo">
                  <span>Cantidad de preguntas para cada estudiante</span>
                  <input
                    type="number"
                    min={1}
                    max={500}
                    value={cantidadPreguntas}
                    disabled={hayEstudiantes}
                    onChange={(e) => setCantidadPreguntas(e.target.value)}
                    placeholder="Todas las preguntas disponibles"
                  />
                  <span className="ayuda">
                    Se sortean de los {cantidadBancos} banco{cantidadBancos === 1 ? '' : 's'} asociados en conjunto. Déjalo vacío para usar todas. Máximo 500.
                  </span>
                </label>
              )}

              <p className="ayuda" style={{ marginTop: 'calc(-1 * var(--e3))' }}>
                Los puntos de cada pregunta se reparten sobre esta nota. Puedes poner 2 puntos a una
                pregunta y 1 a otra sin preocuparte de que sumen {notaMaxima || '20'}. Con
                estudiantes ya dentro, la nota máxima deja de poderse cambiar.
              </p>

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
                  Hasta la hora de inicio no se muestra en ninguna pantalla, tampoco en la tuya.
                </p>
              </div>

              <label className="campo">
                <span>Nivel de supervisión</span>
                <select
                  value={preset}
                  disabled={hayEstudiantes}
                  onChange={(e) => {
                    const nuevo = e.target.value as SupervisionPreset
                    if (nuevo === 'custom' && preset !== 'custom') {
                      setModulos(new Set(MODULOS_DE_PRESET[preset]))
                    }
                    setPreset(nuevo)
                  }}
                >
                  {PRESETS.map((p) => (
                    <option key={p.valor} value={p.valor}>
                      {p.nombre}
                    </option>
                  ))}
                </select>
                {hayEstudiantes && (
                  <span className="ayuda">
                    Ya hay estudiantes en este examen. Lo que se observó mientras lo rendían es un
                    hecho ocurrido, y cambiarlo ahora dejaría un expediente que no se corresponde
                    con lo que pasó.
                  </span>
                )}
              </label>

              {preset === 'custom' && (
                <SelectorModulos
                  elegidos={modulos}
                  onChange={setModulos}
                  deshabilitado={hayEstudiantes}
                />
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

              <button type="submit" className="boton" disabled={guardando}>
                {guardando ? 'Guardando…' : 'Guardar cambios'}
              </button>
            </fieldset>
          </form>
        </div>
      </div>

      {!enPanel && <div className="tarjeta zona-peligro configuracion-examen-tarjeta">
        <div className="tarjeta-cuerpo">
          <h3>Retirar este examen</h3>

          {!cancelado && (
            <>
              <p className="ayuda">
                <strong>Cancelar</strong> retira el examen pero conserva todo: los eventos, las
                alertas y lo que respondieron tus estudiantes. El código deja de servir y quien lo
                use leerá que lo cancelaste.
              </p>
              <button
                type="button"
                className="boton boton-secundario"
                onClick={() => void cancelar()}
              >
                Cancelar examen
              </button>
            </>
          )}

          <p className="ayuda" style={{ marginTop: 'var(--e4)' }}>
            <strong>Borrar</strong> lo elimina para siempre, y solo funciona si todavía no entró
            nadie. Es para el examen que acabas de crear con la fecha mal.
          </p>
          <button type="button" className="boton boton-peligro" onClick={() => void borrar()}>
            Borrar examen
          </button>
        </div>
      </div>}
    </div>
  )
}

/** Divide un ISO en fecha y hora locales para los controles del formulario. */
function aLocal(iso: string): { fecha: string; hora: string } {
  const inicio = new Date(iso)
  const pad = (n: number): string => String(n).padStart(2, '0')
  return {
    fecha: `${inicio.getFullYear()}-${pad(inicio.getMonth() + 1)}-${pad(inicio.getDate())}`,
    hora: `${pad(inicio.getHours())}:${pad(inicio.getMinutes())}`
  }
}
