import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, type ExamSession, type SupervisionPreset } from '../lib/api'
import { useAuth } from '../lib/auth-context'

const PRESETS: Array<{ valor: SupervisionPreset; nombre: string }> = [
  { valor: 'basic', nombre: 'Básica' },
  { valor: 'standard', nombre: 'Estándar' },
  { valor: 'strict', nombre: 'Estricta' }
]

/**
 * Corregir un examen ya creado, cancelarlo o borrarlo.
 *
 * Las dos acciones del final no son la misma cosa y la pantalla lo dice: borrar
 * solo funciona si nadie entró, y en cuanto hay un estudiante lo que corresponde
 * es cancelar, que conserva la evidencia.
 */
export function EditarSesion() {
  const { id = '' } = useParams()
  const { token } = useAuth()
  const navegar = useNavigate()

  const [sesion, setSesion] = useState<ExamSession>()
  const [error, setError] = useState<string>()
  const [aviso, setAviso] = useState<string>()
  const [guardando, setGuardando] = useState(false)

  const [titulo, setTitulo] = useState('')
  const [fecha, setFecha] = useState('')
  const [duracion, setDuracion] = useState(90)
  const [tolerancia, setTolerancia] = useState(10)
  const [preset, setPreset] = useState<SupervisionPreset>('standard')
  const [notaMaxima, setNotaMaxima] = useState('20')
  const [descripcion, setDescripcion] = useState('')

  useEffect(() => {
    api
      .getSession(id, token)
      .then((datos) => {
        setSesion(datos)
        setTitulo(datos.title)
        setFecha(aLocal(datos.starts_at))
        setDuracion(datos.duration_minutes)
        setTolerancia(datos.entry_tolerance_minutes)
        setPreset(datos.preset === 'custom' ? 'standard' : datos.preset)
        setNotaMaxima(String(Number(datos.max_score)))
        setDescripcion(datos.description ?? '')
      })
      .catch((fallo: Error) => setError(fallo.message))
  }, [id, token])

  async function guardar(evento: FormEvent): Promise<void> {
    evento.preventDefault()
    setError(undefined)
    setAviso(undefined)
    setGuardando(true)
    try {
      const actualizada = await api.updateSession(
        id,
        {
          title: titulo,
          starts_at: new Date(fecha).toISOString(),
          duration_minutes: duracion,
          entry_tolerance_minutes: tolerancia,
          preset,
          max_score: notaMaxima,
          // Vaciar la descripción necesita el `clear_`: con `undefined` el
          // backend entiende "no lo cambies".
          ...(descripcion.trim()
            ? { description: descripcion.trim() }
            : { clear_description: true })
        },
        token
      )
      setSesion(actualizada)
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
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>Editar examen</h1>
          <p className="subtitulo">
            Código <strong>{sesion.access_code}</strong> — no cambia aunque edites el resto
          </p>
        </div>
        <Link to={`/sesiones/${id}`} className="boton boton-secundario">
          Volver al examen
        </Link>
      </div>

      {error && <p className="aviso">{error}</p>}
      {aviso && <p className="aviso aviso-neutro">{aviso}</p>}

      {cancelado && (
        <p className="aviso">
          Este examen está cancelado, así que ya no se edita. Sus estudiantes ven que lo
          cancelaste.
        </p>
      )}

      <div className="tarjeta" style={{ maxWidth: '760px' }}>
        <div className="tarjeta-cuerpo">
          <form onSubmit={(e) => void guardar(e)} noValidate>
            <fieldset disabled={cancelado} style={{ border: 0, padding: 0, margin: 0 }}>
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

                <label className="campo">
                  <span>Nota máxima</span>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    step="0.5"
                    value={notaMaxima}
                    onChange={(e) => setNotaMaxima(e.target.value)}
                  />
                </label>
              </div>

              <p className="ayuda" style={{ marginTop: 'calc(-1 * var(--e3))' }}>
                Los puntos de cada pregunta se reparten sobre esta nota. Puedes poner 2 puntos a
                una pregunta y 1 a otra sin preocuparte de que sumen {notaMaxima || '20'}.
                Con estudiantes ya dentro, la nota máxima deja de poderse cambiar.
              </p>

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

              <button type="submit" className="boton" disabled={guardando}>
                {guardando ? 'Guardando…' : 'Guardar cambios'}
              </button>
            </fieldset>
          </form>
        </div>
      </div>

      <div className="tarjeta zona-peligro" style={{ maxWidth: '760px' }}>
        <div className="tarjeta-cuerpo">
          <h3>Retirar este examen</h3>

          {!cancelado && (
            <>
              <p className="ayuda">
                <strong>Cancelar</strong> retira el examen pero conserva todo: los eventos, las
                alertas y lo que respondieron tus estudiantes. El código deja de servir y quien lo
                use leerá que lo cancelaste.
              </p>
              <button type="button" className="boton boton-secundario" onClick={() => void cancelar()}>
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
      </div>
    </>
  )
}

/** Un ISO en UTC al formato local que espera `datetime-local`. */
function aLocal(iso: string): string {
  const fecha = new Date(iso)
  const pad = (n: number): string => String(n).padStart(2, '0')
  return `${fecha.getFullYear()}-${pad(fecha.getMonth() + 1)}-${pad(fecha.getDate())}T${pad(fecha.getHours())}:${pad(fecha.getMinutes())}`
}
