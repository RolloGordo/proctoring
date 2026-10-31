import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type ExamSessionSummary } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { ChipEstado } from '../components/ChipEstado'
import { estadoExamen, fechaLarga, nombrePreset } from '../lib/formato'
import { CodigoAcceso } from '../components/CodigoAcceso'

export function Sesiones() {
  const { token } = useAuth()
  const [sesiones, setSesiones] = useState<ExamSessionSummary[]>()
  const [error, setError] = useState<string>()
  const [reintentos, setReintentos] = useState(0)

  useEffect(() => {
    let cancelado = false
    api
      .listSessions(token)
      .then((datos) => !cancelado && setSesiones(datos))
      .catch((fallo: Error) => !cancelado && setError(fallo.message))
    return () => {
      cancelado = true
    }
  }, [token, reintentos])

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>Exámenes</h1>
          <p className="subtitulo">
            Abre un examen para ver sus alertas, revisar sus preguntas o gestionar a sus
            participantes.
          </p>
        </div>
        <Link to="/sesiones/nueva" className="boton">
          Crear examen
        </Link>
      </div>

      {error && (
        <div className="aviso" role="alert">
          <p>{error}</p>
          <button
            type="button"
            className="boton boton-secundario"
            onClick={() => {
              setError(undefined)
              setReintentos((actual) => actual + 1)
            }}
          >
            Reintentar
          </button>
        </div>
      )}

      {!sesiones && !error && <p className="tenue">Cargando exámenes…</p>}

      {sesiones?.length === 0 && (
        <div className="tarjeta">
          <div className="vacio">
            <h3>Todavía no has creado ningún examen</h3>
            <p className="subtitulo">
              Al crear uno obtendrás un código de acceso para repartir a tus estudiantes.
            </p>
            <p style={{ marginTop: 'var(--e5)' }}>
              <Link to="/sesiones/nueva" className="boton">
                Crear el primero
              </Link>
            </p>
          </div>
        </div>
      )}

      {sesiones && sesiones.length > 0 && (
        <div className="tarjeta">
          <table className="tabla">
            <thead>
              <tr>
                <th>Examen</th>
                <th>Inicio</th>
                <th>Código</th>
                <th>Estado</th>
                <th aria-label="Accesos directos" />
              </tr>
            </thead>
            <tbody>
              {sesiones.map((sesion) => (
                <tr key={sesion.id}>
                  {/* Duración y supervisión bajan a una segunda línea bajo el
                      título: siete columnas en una tarjeta estrecha le robaban
                      el ancho al nombre del examen, que acababa partido en una
                      palabra por renglón. */}
                  <td className="celda-titulo">
                    <Link to={`/sesiones/${sesion.id}`}>{sesion.title}</Link>
                    <span className="celda-detalle">
                      {sesion.duration_minutes} min · supervisión{' '}
                      {nombrePreset(sesion.preset).toLowerCase()}
                    </span>
                  </td>
                  <td className="hora">{fechaLarga(sesion.starts_at)}</td>
                  <td>
                    <CodigoAcceso codigo={sesion.access_code} etiqueta={null} />
                  </td>
                  <td>
                    <ChipEstado
                      estado={estadoExamen(
                        sesion.starts_at,
                        sesion.duration_minutes,
                        undefined,
                        sesion.status === 'cancelled'
                      )}
                    />
                  </td>
                  <td>
                    <div className="fila">
                      <Link to={`/sesiones/${sesion.id}/preguntas`} className="boton boton-texto">
                        Preguntas
                      </Link>
                      <Link
                        to={`/sesiones/${sesion.id}/participantes`}
                        className="boton boton-texto"
                      >
                        Participantes
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
