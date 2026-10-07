import { useState, type FormEvent } from 'react'
import type { NewQuestion, Question, QuestionType } from '../lib/api'
import {
  LLEVA_OPCIONES,
  OPCIONES_INICIALES,
  TIPOS,
  nombreDeTipo,
  sinCorrectaHuerfana,
  type OpcionEditable
} from '../lib/preguntas'

/**
 * El editor de una pregunta y la lista de las que ya hay.
 *
 * Vive aparte porque lo usan dos pantallas: las preguntas de un examen y las de
 * un banco. Duplicarlo haría que una se quedara atrás —el banco, con cien
 * preguntas importadas, es justo donde más duele.
 */

/**
 * Formulario de una pregunta nueva.
 *
 * `onGuardar` decide a dónde va: a un examen o a un banco. El editor no lo sabe
 * ni le importa.
 */
export function EditorPregunta({
  onGuardar,
  textoBoton = 'Añadir pregunta'
}: {
  onGuardar: (nueva: NewQuestion) => Promise<void>
  textoBoton?: string
}) {
  const [tipo, setTipo] = useState<QuestionType>('multiple_choice')
  const [enunciado, setEnunciado] = useState('')
  const [puntos, setPuntos] = useState('1')
  const [opciones, setOpciones] = useState<OpcionEditable[]>(OPCIONES_INICIALES)
  const [respuestaNumerica, setRespuestaNumerica] = useState('')
  const [respuestaTexto, setRespuestaTexto] = useState('')
  const [guardando, setGuardando] = useState(false)

  function limpiar(): void {
    setEnunciado('')
    setPuntos('1')
    setOpciones(OPCIONES_INICIALES)
    setRespuestaNumerica('')
    setRespuestaTexto('')
  }

  async function enviar(evento: FormEvent): Promise<void> {
    evento.preventDefault()
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
      await onGuardar(nueva)
      // Solo se limpia si se guardó: si falló, el docente no pierde lo escrito.
      limpiar()
    } finally {
      setGuardando(false)
    }
  }

  const elegido = TIPOS.find((t) => t.valor === tipo)

  return (
    <form onSubmit={(e) => void enviar(e)} noValidate>
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
        <EditorOpciones tipo={tipo} opciones={opciones} onCambio={setOpciones} />
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
        {guardando ? 'Guardando…' : textoBoton}
      </button>
    </form>
  )
}

/**
 * Las preguntas con sus respuestas correctas. Solo la ve el docente.
 *
 * Con `onCambiarPuntos` y `onBorrar` cada una se puede corregir ahí mismo. Sin
 * ellos la lista es de solo lectura, que es como la usan las pantallas que no
 * dejan editar.
 */
export function ListaPreguntas({
  preguntas,
  onCambiarPuntos,
  onBorrar
}: {
  preguntas: Question[]
  onCambiarPuntos?: (id: string, puntos: string) => Promise<void>
  onBorrar?: (id: string) => Promise<void>
}) {
  return (
    <ol className="lista-preguntas numerada">
      {preguntas.map((pregunta) => (
        <li key={pregunta.id} className="tarjeta">
          <div className="tarjeta-cuerpo">
            <div className="fila" style={{ justifyContent: 'space-between' }}>
              <h4>{nombreDeTipo(pregunta.question_type)}</h4>
              {onCambiarPuntos ? (
                <PuntosEditables
                  puntos={pregunta.points}
                  onGuardar={(valor) => onCambiarPuntos(pregunta.id, valor)}
                />
              ) : (
                <span className="tenue">{pregunta.points} pts</span>
              )}
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
            {onBorrar && (
              <button
                type="button"
                className="boton boton-texto"
                onClick={() => void onBorrar(pregunta.id)}
              >
                Quitar esta pregunta
              </button>
            )}
          </div>
        </li>
      ))}
    </ol>
  )
}

/**
 * Los puntos de una pregunta, editables en el sitio.
 *
 * Se guarda al salir del campo y no con un botón: en una lista de cuarenta
 * preguntas, cuarenta botones "guardar" son ruido.
 */
function PuntosEditables({
  puntos,
  onGuardar
}: {
  puntos: string
  onGuardar: (valor: string) => Promise<void>
}) {
  const [valor, setValor] = useState(puntos)
  const [guardando, setGuardando] = useState(false)

  async function alSalir(): Promise<void> {
    if (valor === puntos) return
    setGuardando(true)
    try {
      await onGuardar(valor)
    } catch {
      // Si falló, se vuelve a lo que había: el número que se ve es el guardado.
      setValor(puntos)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <span className="puntos-editables">
      <input
        type="number"
        min={0}
        max={100}
        step="0.5"
        value={valor}
        disabled={guardando}
        onChange={(e) => setValor(e.target.value)}
        onBlur={() => void alSalir()}
        aria-label="Puntos de esta pregunta"
      />
      <span className="tenue">pts</span>
    </span>
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
