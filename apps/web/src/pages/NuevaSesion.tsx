import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type SupervisionPreset } from '../lib/api'
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
  const [preset, setPreset] = useState<SupervisionPreset>('standard')
  const [descripcion, setDescripcion] = useState('')
  const [error, setError] = useState<string>()
  const [enviando, setEnviando] = useState(false)

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
          description: descripcion.trim() || null
        },
        token
      )
      navegar(`/sesiones/${sesion.id}`)
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo crear el examen')
    } finally {
      setEnviando(false)
    }
  }

  const elegido = PRESETS.find((p) => p.valor === preset)

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>Crear examen</h1>
          <p className="subtitulo">
            Al guardarlo obtendrás un código de acceso para repartir a tus estudiantes
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
