import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type CaseFile, type DecisionType } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import {
  DECISIONES,
  detalleEvento,
  duracion,
  fechaLarga,
  nombreDecision,
  nombreEvento,
  nombreNivel,
  soloHora
} from '../lib/formato'

/** Mismo mínimo que la API y la base: una justificación de tres letras no justifica nada. */
const MINIMO = 10

/**
 * La revisión de un caso: **mirar antes de decidir**.
 *
 * El sistema audita —reúne las señales y calcula un riesgo, con su desglose— y el
 * docente decide, con una justificación escrita. Nada aquí anula un examen: la
 * decisión se registra y no se edita; si el docente cambia de parecer, registra
 * otra y el historial queda.
 */
export function RevisionCaso() {
  const { id = '', estudianteId = '' } = useParams()
  const { token } = useAuth()

  const [caso, setCaso] = useState<CaseFile>()
  const [error, setError] = useState<string>()
  const [decision, setDecision] = useState<DecisionType>()
  const [justificacion, setJustificacion] = useState('')
  const [guardando, setGuardando] = useState(false)

  useEffect(() => {
    let cancelado = false
    api
      .reviewCase(id, estudianteId, token)
      .then((datos) => !cancelado && setCaso(datos))
      .catch((fallo: Error) => !cancelado && setError(fallo.message))
    return () => {
      cancelado = true
    }
  }, [id, estudianteId, token])

  async function decidir(evento: FormEvent): Promise<void> {
    evento.preventDefault()
    if (!decision) return
    setError(undefined)
    setGuardando(true)
    try {
      const registrada = await api.decide(id, estudianteId, decision, justificacion, token)
      setCaso((previo) =>
        previo ? { ...previo, decisions: [registrada, ...previo.decisions] } : previo
      )
      setDecision(undefined)
      setJustificacion('')
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo registrar la decisión')
    } finally {
      setGuardando(false)
    }
  }

  if (error && !caso) {
    return (
      <>
        <p className="aviso">{error}</p>
        <Link to={`/sesiones/${id}/participantes`}>Volver a la sala de espera</Link>
      </>
    )
  }
  if (!caso) return <p className="tenue">Cargando el caso…</p>

  const { participant, risk, events } = caso
  const vigente = caso.decisions[0]
  const quien = participant.student_name ?? participant.student_id.slice(0, 8)
  const longitud = justificacion.trim().length
  const puedeGuardar = decision !== undefined && longitud >= MINIMO && !guardando

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>{quien}</h1>
          <p className="subtitulo">{participant.student_email ?? 'Revisión de caso'}</p>
        </div>
        <Link to={`/sesiones/${id}/participantes`} className="boton boton-secundario">
          Volver a la sala de espera
        </Link>
      </div>

      <section className="bloque">
        <div className="encabezado-seccion">
          <h2>Riesgo</h2>
        </div>
        <div className="tarjeta">
          <div className="tarjeta-cuerpo">
            <div className="riesgo-cabecera">
              <p className={`riesgo-cifra riesgo-${risk.level}`}>{risk.score}</p>
              <div>
                <p className="riesgo-nivel">Nivel {nombreNivel(risk.level).toLowerCase()}</p>
                <p className="ayuda">
                  Orienta cuánta atención merece el caso, no lo resuelve. Cada punto sale de una
                  señal concreta, abajo.
                </p>
              </div>
            </div>

            {risk.signals.length === 0 ? (
              <p className="tenue">No se registró ninguna señal de este estudiante.</p>
            ) : (
              <table className="tabla" style={{ marginTop: 'var(--e4)' }}>
                <thead>
                  <tr>
                    <th>Señal</th>
                    <th>Veces</th>
                    <th>Tiempo</th>
                    <th>Aporta</th>
                  </tr>
                </thead>
                <tbody>
                  {risk.signals.map((s) => (
                    <tr key={s.event_type}>
                      <td>
                        {nombreEvento(s.event_type)}{' '}
                        <span className={`severidad severidad-${s.max_severity}`}>
                          {s.max_severity}
                        </span>
                      </td>
                      <td>{s.count}</td>
                      <td className="tenue">
                        {s.total_duration_ms > 0 ? duracion(s.total_duration_ms) : '—'}
                      </td>
                      <td>
                        <strong>{s.points}</strong> pts
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </section>

      <section className="bloque">
        <div className="encabezado-seccion">
          <h2>Línea de tiempo</h2>
          <span className="tenue">{events.length} señales</span>
        </div>
        <div className="tarjeta">
          {events.length === 0 ? (
            <div className="vacio">
              <h3>Sin señales</h3>
            </div>
          ) : (
            <table className="tabla">
              <thead>
                <tr>
                  <th>Hora</th>
                  <th>Señal</th>
                  <th>Detalle</th>
                  <th>Duración</th>
                  <th>Nivel</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.id}>
                    <td className="hora">{soloHora(e.started_at)}</td>
                    <td>{nombreEvento(e.event_type)}</td>
                    <td className="tenue">{detalleEvento(e.metadata) || '—'}</td>
                    <td className="tenue">{e.duration_ms > 0 ? duracion(e.duration_ms) : '—'}</td>
                    <td>
                      <span className={`severidad severidad-${e.severity}`}>{e.severity}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <section className="bloque">
        <div className="encabezado-seccion">
          <h2>Tu decisión</h2>
        </div>

        {vigente && (
          <div className="tarjeta decision-vigente">
            <div className="tarjeta-cuerpo">
              <p className="etiqueta">Decisión vigente</p>
              <h3>{nombreDecision(vigente.decision)}</h3>
              <p className="justificacion">{vigente.justification}</p>
              <p className="ayuda">{fechaLarga(vigente.decided_at)}</p>
            </div>
          </div>
        )}

        <div className="tarjeta">
          <div className="tarjeta-cuerpo">
            <form onSubmit={(e) => void decidir(e)} noValidate>
              {error && <p className="aviso">{error}</p>}

              <fieldset className="opciones-decision">
                <legend className="etiqueta">
                  {vigente ? 'Cambiar de parecer' : 'Qué decides'}
                </legend>
                {(Object.keys(DECISIONES) as DecisionType[]).map((tipo) => (
                  <label key={tipo} className={decision === tipo ? 'elegida' : ''}>
                    <input
                      type="radio"
                      name="decision"
                      value={tipo}
                      checked={decision === tipo}
                      onChange={() => setDecision(tipo)}
                    />
                    <span>
                      <strong>{DECISIONES[tipo].nombre}</strong>
                      <span className="ayuda">{DECISIONES[tipo].detalle}</span>
                    </span>
                  </label>
                ))}
              </fieldset>

              <label className="campo">
                <span>Justificación</span>
                <textarea
                  rows={4}
                  value={justificacion}
                  onChange={(e) => setJustificacion(e.target.value)}
                  maxLength={2000}
                  placeholder="Explica por qué decides así. Es lo que te va a servir si alguien pregunta."
                />
                <p className={longitud >= MINIMO ? 'ayuda' : 'ayuda ayuda-falta'}>
                  {longitud >= MINIMO
                    ? 'Queda registrada con tu nombre y no se edita.'
                    : `Escribe al menos ${MINIMO} caracteres (${longitud}/${MINIMO}).`}
                </p>
              </label>

              <button type="submit" className="boton" disabled={!puedeGuardar}>
                {guardando ? 'Registrando…' : 'Registrar decisión'}
              </button>
            </form>
          </div>
        </div>

        {caso.decisions.length > 1 && (
          <>
            <h4 style={{ margin: 'var(--e5) 0 var(--e3)' }}>Historial</h4>
            <ul className="historial-decisiones">
              {caso.decisions.slice(1).map((d) => (
                <li key={d.id} className="tarjeta">
                  <div className="tarjeta-cuerpo">
                    <strong>{nombreDecision(d.decision)}</strong>
                    <span className="tenue"> · {fechaLarga(d.decided_at)}</span>
                    <p className="justificacion">{d.justification}</p>
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
    </>
  )
}
