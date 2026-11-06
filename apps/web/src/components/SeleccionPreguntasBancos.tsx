import { useEffect, useMemo, useState } from 'react'
import { api, type BankQuestionPoint, type SessionBankQuestion } from '../lib/api'
import { useAuth } from '../lib/auth-context'

const OPCIONES_POR_PAGINA = [5, 10, 20, 50]

export function SeleccionPreguntasBancos({
  sessionId,
  revision = 0,
  onGuardado,
  bloqueado = false
}: {
  sessionId: string
  revision?: number
  onGuardado?: () => void
  bloqueado?: boolean
}) {
  const { token } = useAuth()
  const [preguntas, setPreguntas] = useState<SessionBankQuestion[]>()
  const [excluidas, setExcluidas] = useState<Set<string>>(new Set())
  const [excluidasOriginales, setExcluidasOriginales] = useState<Set<string>>(new Set())
  const [puntajes, setPuntajes] = useState<Record<string, string>>({})
  const [puntajesOriginales, setPuntajesOriginales] = useState<Record<string, string>>({})
  const [filtroBanco, setFiltroBanco] = useState('todos')
  const [busqueda, setBusqueda] = useState('')
  const [pagina, setPagina] = useState(1)
  const [porPagina, setPorPagina] = useState(5)
  const [bloqueadoPorParticipantes, setBloqueadoPorParticipantes] = useState(false)
  // La carga se deriva de qué petición terminó, en vez de ponerla a `true` a
  // mano dentro del efecto (react-hooks/set-state-in-effect).
  const [cargadoPara, setCargadoPara] = useState<string>()
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string>()
  const [aviso, setAviso] = useState<string>()

  useEffect(() => {
    let cancelado = false
    const clave = `${sessionId}:${revision}`
    Promise.all([
      api.listSessionBankQuestions(sessionId, token),
      api.listParticipants(sessionId, token)
    ])
      .then(([seleccion, participantes]) => {
        if (cancelado) return
        setPreguntas(seleccion)
        const excluidasCargadas = new Set(
          seleccion.filter((item) => !item.included).map((item) => item.question.id)
        )
        setExcluidas(excluidasCargadas)
        setExcluidasOriginales(excluidasCargadas)
        const puntos = Object.fromEntries(seleccion.map((item) => [item.question.id, item.question.points]))
        setPuntajes(puntos)
        setPuntajesOriginales(puntos)
        setBloqueadoPorParticipantes(participantes.length > 0)
        setError(undefined)
      })
      .catch((fallo: Error) => {
        if (!cancelado) setError(fallo.message)
      })
      .finally(() => {
        if (!cancelado) setCargadoPara(clave)
      })
    return () => {
      cancelado = true
    }
  }, [sessionId, token, revision])

  const cargando = cargadoPara !== `${sessionId}:${revision}`

  const bancos = useMemo(
    () => [...new Set((preguntas ?? []).map((item) => item.bank_name))],
    [preguntas]
  )
  const filtradas = useMemo(() => {
    const termino = busqueda.trim().toLocaleLowerCase()
    return (preguntas ?? []).filter((item) => {
      const coincideBanco = filtroBanco === 'todos' || item.bank_name === filtroBanco
      const coincideTexto = !termino || item.question.statement.toLocaleLowerCase().includes(termino)
      return coincideBanco && coincideTexto
    })
  }, [preguntas, filtroBanco, busqueda])
  const total = preguntas?.length ?? 0
  const incluidas = total - excluidas.size
  const paginas = Math.max(1, Math.ceil(filtradas.length / porPagina))
  const paginaActual = Math.min(pagina, paginas)
  const visibles = filtradas.slice((paginaActual - 1) * porPagina, paginaActual * porPagina)
  const huboCambios = !mismoConjunto(excluidas, excluidasOriginales) ||
    !mismoMapa(puntajes, puntajesOriginales)
  const puntajesValidos = (preguntas ?? []).every(({ question }) => esPuntajeValido(puntajes[question.id]))
  const totalPuntos = (preguntas ?? []).reduce((suma, { question }) => {
    if (excluidas.has(question.id)) return suma
    const valor = Number((puntajes[question.id] ?? '').replace(',', '.'))
    return suma + (Number.isFinite(valor) ? valor : 0)
  }, 0)
  const congelado = bloqueado || bloqueadoPorParticipantes

  function cambiarInclusion(id: string, incluir: boolean): void {
    setExcluidas((actuales) => {
      const siguiente = new Set(actuales)
      if (incluir) siguiente.delete(id)
      else siguiente.add(id)
      return siguiente
    })
    setAviso(undefined)
  }

  async function guardar(): Promise<void> {
    if (incluidas === 0 || !huboCambios || !puntajesValidos) return
    setError(undefined)
    setAviso(undefined)
    setGuardando(true)
    try {
      const detallePuntajes: BankQuestionPoint[] = (preguntas ?? []).map(({ question }) => ({
        question_id: question.id,
        points: (puntajes[question.id] ?? '').replace(',', '.')
      }))
      const guardadas = await api.saveSessionBankQuestionSelection(
        sessionId,
        [...excluidas],
        detallePuntajes,
        token
      )
      setPreguntas(guardadas)
      const nuevasExcluidas = new Set(
        guardadas.filter((item) => !item.included).map((item) => item.question.id)
      )
      setExcluidas(nuevasExcluidas)
      setExcluidasOriginales(nuevasExcluidas)
      const puntosActualizados = Object.fromEntries(guardadas.map((item) => [item.question.id, item.question.points]))
      setPuntajes(puntosActualizados)
      setPuntajesOriginales(puntosActualizados)
      setAviso('Seleccion y puntajes guardados para este examen.')
      onGuardado?.()
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo guardar la selección')
    } finally {
      setGuardando(false)
    }
  }

  function incluirTodas(): void {
    setExcluidas(new Set())
    setAviso(undefined)
  }

  return (
    <section className="seleccion-bancos tarjeta" aria-labelledby="titulo-seleccion-bancos">
      <div className="tarjeta-cuerpo">
        <div className="encabezado-seccion seleccion-bancos-cabecera">
          <div>
            <h3 id="titulo-seleccion-bancos">Seleccionar preguntas para este examen</h3>
            <p className="ayuda">
              Revisa juntas las preguntas de tus bancos. La etiqueta muestra su origen. Las excluidas siguen guardadas en su banco; al guardar, este examen conserva su seleccion y puntajes.
            </p>
          </div>
          {total > 0 && (
            <div className="seleccion-bancos-resumen-wrap">
              <span className="seleccion-bancos-resumen">{incluidas} de {total} para el examen</span>
              <span className="seleccion-bancos-total">Total: {totalPuntos.toLocaleString('es-PE', { maximumFractionDigits: 2 })} pts</span>
            </div>
          )}
        </div>

        {error && <p className="aviso" role="alert">{error}</p>}
        {aviso && <p className="aviso aviso-exito" role="status">{aviso}</p>}
        {congelado && total > 0 && (
          <p className="aviso aviso-neutro">
            Ya hay participantes en este examen. La selección está bloqueada para conservar las preguntas que recibieron.
          </p>
        )}

        {cargando ? (
          <p className="tenue" role="status">Cargando preguntas de los bancos…</p>
        ) : total === 0 ? (
          <p className="ayuda">Los bancos asociados todavia no tienen preguntas para revisar.</p>
        ) : (
          <>
            <div className="seleccion-bancos-controles">
              <label className="campo">
                <span>Buscar pregunta</span>
                <input
                  type="search"
                  value={busqueda}
                  onChange={(evento) => {
                    setBusqueda(evento.target.value)
                    setPagina(1)
                  }}
                  placeholder="Escribe parte del enunciado"
                />
              </label>
              <label className="campo">
                <span>Origen (banco)</span>
                <select
                  value={filtroBanco}
                  onChange={(evento) => {
                    setFiltroBanco(evento.target.value)
                    setPagina(1)
                  }}
                >
                  <option value="todos">Todos los bancos</option>
                  {bancos.map((banco) => <option key={banco} value={banco}>{banco}</option>)}
                </select>
              </label>
              <label className="campo">
                <span>Preguntas por página</span>
                <select
                  value={porPagina}
                  onChange={(evento) => {
                    setPorPagina(Number(evento.target.value))
                    setPagina(1)
                  }}
                >
                  {OPCIONES_POR_PAGINA.map((cantidad) => (
                    <option key={cantidad} value={cantidad}>{cantidad}</option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="boton boton-texto"
                onClick={incluirTodas}
                disabled={congelado || guardando || excluidas.size === 0}
              >
                Incluir todas
              </button>
            </div>

            <p className="preguntas-conteo" aria-live="polite">
              {filtradas.length} pregunta{filtradas.length === 1 ? '' : 's'}
              {filtroBanco !== 'todos' && ` de ${filtroBanco}`}
            </p>

            {visibles.length === 0 ? (
              <p className="ayuda">No hay preguntas con ese texto en el banco seleccionado.</p>
            ) : (
              <ol className="seleccion-bancos-lista" start={(paginaActual - 1) * porPagina + 1}>
                {visibles.map(({ question, bank_name: banco }) => {
                  const incluida = !excluidas.has(question.id)
                  return (
                    <li key={question.id} className={incluida ? '' : 'excluida'}>
                      <label className="seleccion-bancos-pregunta">
                        <input
                          type="checkbox"
                          checked={incluida}
                          disabled={congelado || guardando}
                          onChange={(evento) => cambiarInclusion(question.id, evento.target.checked)}
                        />
                        <span className="seleccion-bancos-texto">
                          <span className="seleccion-bancos-meta">
                            <span className="chip chip-programado">{banco}</span>
                            <span>{question.question_type.replaceAll('_', ' ')}</span>
                            <span>{puntajes[question.id] ?? question.points} pts</span>
                          </span>
                          <strong>{question.statement}</strong>
                        </span>
                        <span className="seleccion-bancos-estado">
                          {incluida ? 'Incluida' : 'Excluida'}
                        </span>
                      </label>
                      <label className="seleccion-bancos-puntaje">
                        <span>Puntos en este examen</span>
                        <input
                          type="text"
                          inputMode="decimal"
                          value={puntajes[question.id] ?? ''}
                          aria-label={`Puntos para la pregunta ${question.position} en este examen`}
                          disabled={congelado || guardando || !incluida}
                          onChange={(evento) => {
                            setPuntajes((actuales) => ({ ...actuales, [question.id]: evento.target.value }))
                            setAviso(undefined)
                          }}
                        />
                        <span>pts</span>
                      </label>
                      <details className="seleccion-bancos-detalle">
                        <summary>Ver alternativas y respuesta correcta</summary>
                        {question.options.length > 0 && (
                          <ul className="lista-opciones">
                            {question.options.map((opcion) => (
                              <li key={opcion.id} className={opcion.is_correct ? 'correcta' : ''}>
                                {opcion.option_text}
                              </li>
                            ))}
                          </ul>
                        )}
                        {question.correct_numeric_answer !== null && (
                          <p className="ayuda">Respuesta: {question.correct_numeric_answer}</p>
                        )}
                        {question.correct_text_answer && (
                          <p className="ayuda">Respuesta: {question.correct_text_answer}</p>
                        )}
                      </details>
                    </li>
                  )
                })}
              </ol>
            )}

            {paginas > 1 && (
              <nav className="preguntas-paginacion" aria-label="Páginas de selección de preguntas">
                <button type="button" className="boton boton-secundario" disabled={paginaActual <= 1} onClick={() => setPagina(paginaActual - 1)}>
                  Anterior
                </button>
                <span>Página {paginaActual} de {paginas}</span>
                <button type="button" className="boton boton-secundario" disabled={paginaActual >= paginas} onClick={() => setPagina(paginaActual + 1)}>
                  Siguiente
                </button>
              </nav>
            )}

            {incluidas === 0 && (
              <p className="aviso" role="alert">Incluye al menos una pregunta para guardar el examen.</p>
            )}
            {!puntajesValidos && (
              <p className="aviso" role="alert">Usa puntajes entre 0 y 100, con hasta dos decimales (por ejemplo, 1,25).</p>
            )}
            <button
              type="button"
              className="boton"
              disabled={congelado || guardando || !huboCambios || incluidas === 0 || !puntajesValidos}
              onClick={() => void guardar()}
            >
              {guardando ? 'Guardando contenido...' : 'Guardar contenido del examen'}
            </button>
          </>
        )}
      </div>
    </section>
  )
}

function esPuntajeValido(valor: string | undefined): boolean {
  if (!valor || !/^\d{1,3}([.,]\d{1,2})?$/.test(valor.trim())) return false
  const numero = Number(valor.replace(',', '.'))
  return Number.isFinite(numero) && numero >= 0 && numero <= 100
}

function mismoMapa(a: Record<string, string>, b: Record<string, string>): boolean {
  const ids = new Set([...Object.keys(a), ...Object.keys(b)])
  return [...ids].every((id) => a[id] === b[id])
}

function mismoConjunto(a: Set<string>, b: Set<string>): boolean {
  return a.size === b.size && [...a].every((elemento) => b.has(elemento))
}
