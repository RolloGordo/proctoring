import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type NewQuestion, type Question, type QuestionType } from '../lib/api'
import { useAuth } from '../lib/auth-context'

const TIPOS: Array<{ valor: QuestionType; nombre: string; ayuda: string }> = [
  {
    valor: 'multiple_choice',
    nombre: 'Opción múltiple',
    ayuda: 'Varias alternativas, una correcta.'
  },
  { valor: 'true_false', nombre: 'Verdadero o falso', ayuda: 'Exactamente dos opciones.' },
  { valor: 'numeric', nombre: 'Respuesta numérica', ayuda: 'Se compara con el valor exacto.' },
  { valor: 'fill_blank', nombre: 'Completar', ayuda: 'Se compara con el texto esperado.' },
  { valor: 'essay', nombre: 'Desarrollo', ayuda: 'La califica el docente a mano.' }
]

const LLEVA_OPCIONES = new Set<QuestionType>(['multiple_choice', 'true_false'])

interface OpcionEditable {
  option_text: string
  is_correct: boolean
}

const OPCIONES_INICIALES: OpcionEditable[] = [
  { option_text: '', is_correct: true },
  { option_text: '', is_correct: false }
]

export function Preguntas() {
  const { id = '' } = useParams()
  const { token } = useAuth()

  const [preguntas, setPreguntas] = useState<Question[]>()
  const [error, setError] = useState<string>()
  const [guardando, setGuardando] = useState(false)

  const [tipo, setTipo] = useState<QuestionType>('multiple_choice')
  const [enunciado, setEnunciado] = useState('')
  const [puntos, setPuntos] = useState('1')
  const [opciones, setOpciones] = useState<OpcionEditable[]>(OPCIONES_INICIALES)
  const [respuestaNumerica, setRespuestaNumerica] = useState('')
  const [respuestaTexto, setRespuestaTexto] = useState('')

  useEffect(() => {
    api
      .listQuestions(id, token)
      .then(setPreguntas)
      .catch((fallo: Error) => setError(fallo.message))
  }, [id, token])

  function limpiar(): void {
    setEnunciado('')
    setPuntos('1')
    setOpciones(OPCIONES_INICIALES)
    setRespuestaNumerica('')
    setRespuestaTexto('')
  }

  async function agregar(evento: FormEvent): Promise<void> {
    evento.preventDefault()
    setError(undefined)
    setGuardando(true)

    const nueva: NewQuestion = {
      question_type: tipo,
      statement: enunciado,
      points: puntos,
      ...(LLEVA_OPCIONES.has(tipo)
        ? { options: opciones.map((o) => ({ ...o, option_text: o.option_text.trim() })) }
        : {}),
      ...(tipo === 'numeric' ? { correct_numeric_answer: respuestaNumerica } : {}),
      ...(tipo === 'fill_blank' ? { correct_text_answer: respuestaTexto } : {})
    }

    try {
      const creadas = await api.addQuestions(id, [nueva], token)
      setPreguntas((previas) => [...(previas ?? []), ...creadas])
      limpiar()
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo guardar la pregunta')
    } finally {
      setGuardando(false)
    }
  }

  const elegido = TIPOS.find((t) => t.valor === tipo)
  const puntosTotales = (preguntas ?? []).reduce((suma, p) => suma + Number(p.points), 0)

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>Preguntas del examen</h1>
          <p className="subtitulo">
            {preguntas
              ? `${preguntas.length} pregunta${preguntas.length === 1 ? '' : 's'} · ${puntosTotales} puntos en total`
              : 'Cargando…'}
          </p>
        </div>
        <Link to={`/sesiones/${id}`} className="boton boton-secundario">
          Volver al examen
        </Link>
      </div>

      {error && <p className="aviso">{error}</p>}

      <div className="columnas">
        <section>
          <div className="encabezado-seccion">
            <h2>Añadir pregunta</h2>
          </div>

          <div className="tarjeta">
            <div className="tarjeta-cuerpo">
              <form onSubmit={(e) => void agregar(e)} noValidate>
                <label className="campo">
                  <span>Tipo</span>
                  <select
                    value={tipo}
                    onChange={(e) => {
                      setTipo(e.target.value as QuestionType)
                      limpiar()
                    }}
                  >
                    {TIPOS.map((t) => (
                      <option key={t.valor} value={t.valor}>
                        {t.nombre}
                      </option>
                    ))}
                  </select>
                  {elegido && <p className="ayuda">{elegido.ayuda}</p>}
                </label>

                <label className="campo">
                  <span>Enunciado</span>
                  <textarea
                    rows={3}
                    value={enunciado}
                    onChange={(e) => setEnunciado(e.target.value)}
                    maxLength={5000}
                    required
                  />
                </label>

                <label className="campo" style={{ maxWidth: '160px' }}>
                  <span>Puntos</span>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step="0.5"
                    value={puntos}
                    onChange={(e) => setPuntos(e.target.value)}
                  />
                </label>

                {LLEVA_OPCIONES.has(tipo) && (
                  <EditorOpciones
                    tipo={tipo}
                    opciones={opciones}
                    onCambio={setOpciones}
                  />
                )}

                {tipo === 'numeric' && (
                  <label className="campo">
                    <span>Respuesta correcta</span>
                    <input
                      type="number"
                      step="any"
                      value={respuestaNumerica}
                      onChange={(e) => setRespuestaNumerica(e.target.value)}
                      required
                    />
                  </label>
                )}

                {tipo === 'fill_blank' && (
                  <label className="campo">
                    <span>Respuesta correcta</span>
                    <input
                      value={respuestaTexto}
                      onChange={(e) => setRespuestaTexto(e.target.value)}
                      maxLength={1000}
                      required
                    />
                  </label>
                )}

                <button type="submit" className="boton" disabled={guardando || !enunciado.trim()}>
                  {guardando ? 'Guardando…' : 'Añadir pregunta'}
                </button>
              </form>
            </div>
          </div>
        </section>

        <section>
          <div className="encabezado-seccion">
            <h2>En el examen</h2>
          </div>

          {preguntas?.length === 0 ? (
            <div className="tarjeta">
              <div className="vacio">
                <h3>Todavía no hay preguntas</h3>
                <p className="subtitulo">
                  Un examen sin preguntas no se puede rendir. Añade la primera a la izquierda.
                </p>
              </div>
            </div>
          ) : (
            <ol className="lista-preguntas numerada">
              {preguntas?.map((pregunta) => (
                <li key={pregunta.id} className="tarjeta">
                  <div className="tarjeta-cuerpo">
                    <div className="fila" style={{ justifyContent: 'space-between' }}>
                      <h4>{TIPOS.find((t) => t.valor === pregunta.question_type)?.nombre}</h4>
                      <span className="tenue">{pregunta.points} pts</span>
                    </div>
                    <p className="motivo" style={{ marginTop: 'var(--e2)' }}>
                      {pregunta.statement}
                    </p>
                    {pregunta.options.length > 0 && (
                      <ul className="lista-opciones">
                        {pregunta.options.map((opcion) => (
                          <li key={opcion.id} className={opcion.is_correct ? 'correcta' : ''}>
                            {opcion.option_text}
                          </li>
                        ))}
                      </ul>
                    )}
                    {pregunta.correct_numeric_answer && (
                      <p className="ayuda">Respuesta: {pregunta.correct_numeric_answer}</p>
                    )}
                    {pregunta.correct_text_answer && (
                      <p className="ayuda">Respuesta: {pregunta.correct_text_answer}</p>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </>
  )
}

function EditorOpciones({
  tipo,
  opciones,
  onCambio
}: {
  tipo: QuestionType
  opciones: OpcionEditable[]
  onCambio: (opciones: OpcionEditable[]) => void
}) {
  // Verdadero o falso lleva exactamente dos: no tiene sentido dejar añadir más.
  const puedeAgregar = tipo === 'multiple_choice' && opciones.length < 10
  const puedeQuitar = opciones.length > 2

  function cambiar(indice: number, cambios: Partial<OpcionEditable>): void {
    onCambio(opciones.map((o, i) => (i === indice ? { ...o, ...cambios } : o)))
  }

  /** Marcar una correcta desmarca la anterior.
   *
   *  El dominio de la API admite varias correctas —hará falta al importar QTI—,
   *  pero una respuesta guardada apunta a **una** opción (`selected_option_id`).
   *  Una pregunta con dos correctas sería una que nadie puede responder entera,
   *  así que el editor solo produce lo que el sistema sabe calificar. */
  function marcarCorrecta(indice: number): void {
    onCambio(opciones.map((o, i) => ({ ...o, is_correct: i === indice })))
  }

  return (
    <div className="campo">
      <span>Opciones</span>
      <p className="ayuda" style={{ marginBottom: 'var(--e2)' }}>
        Marca cuál es la correcta. El estudiante elige una sola.
      </p>

      <ul className="editor-opciones">
        {opciones.map((opcion, indice) => (
          <li key={indice}>
            <input
              type="radio"
              name="opcion-correcta"
              checked={opcion.is_correct}
              onChange={() => marcarCorrecta(indice)}
              aria-label={`La opción ${indice + 1} es la correcta`}
            />
            <input
              value={opcion.option_text}
              onChange={(e) => cambiar(indice, { option_text: e.target.value })}
              placeholder={`Opción ${indice + 1}`}
              maxLength={1000}
            />
            {puedeQuitar && (
              <button
                type="button"
                className="boton boton-texto"
                onClick={() => onCambio(sinCorrectaHuerfana(opciones, indice))}
                aria-label={`Quitar opción ${indice + 1}`}
              >
                Quitar
              </button>
            )}
          </li>
        ))}
      </ul>

      {puedeAgregar && (
        <button
          type="button"
          className="boton boton-secundario"
          onClick={() => onCambio([...opciones, { option_text: '', is_correct: false }])}
        >
          Añadir opción
        </button>
      )}
    </div>
  )
}

/** Quita una opción y, si era la correcta, marca la primera que queda.
 *
 *  Sin esto, borrar la correcta dejaría la pregunta sin ninguna y la API la
 *  rechazaría con un error que el docente no sabría de dónde viene. */
function sinCorrectaHuerfana(opciones: OpcionEditable[], indice: number): OpcionEditable[] {
  const restantes = opciones.filter((_, i) => i !== indice)
  if (restantes.some((o) => o.is_correct)) return restantes
  return restantes.map((o, i) => ({ ...o, is_correct: i === 0 }))
}
