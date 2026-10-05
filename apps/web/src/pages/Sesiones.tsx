import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type ExamSessionSummary } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { ChipEstado } from '../components/ChipEstado'
import { estadoExamen, fechaLarga, nombrePreset } from '../lib/formato'

export function Sesiones() {
  const { token } = useAuth()
  const [sesiones, setSesiones] = useState<ExamSessionSummary[]>()
  const [error, setError] = useState<string>()

  useEffect(() => {
    api
      .listSessions(token)
      .then(setSesiones)
      .catch((fallo: Error) => setError(fallo.message))
  }, [token])

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>Mis exámenes</h1>
          <p className="subtitulo">
            Entra a un examen para ver sus alertas en vivo, o ve directo a sus preguntas y a su sala
            de espera
          </p>
        </div>
        <Link to="/sesiones/nueva" className="boton">
          Crear examen
        </Link>
      </div>

      {error && <p className="aviso">{error}</p>}

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
                <th>Duración</th>
                <th>Supervisión</th>
                <th>Código</th>
                <th>Estado</th>
                <th aria-label="Accesos directos" />
              </tr>
            </thead>
            <tbody>
              {sesiones.map((sesion) => (
                <tr key={sesion.id}>
                  <td>
                    <Link to={`/sesiones/${sesion.id}`}>{sesion.title}</Link>
                  </td>
                  <td className="hora">{fechaLarga(sesion.starts_at)}</td>
                  <td>{sesion.duration_minutes} min</td>
                  <td>{nombrePreset(sesion.preset)}</td>
                  <td>
                    <span className="codigo-acceso">{sesion.access_code}</span>
                  </td>
                  <td>
                    <ChipEstado estado={estadoExamen(sesion.starts_at, sesion.duration_minutes)} />
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
                        Sala de espera
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
