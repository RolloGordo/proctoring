import { useState, type FormEvent } from 'react'
import type { NewQuestion, Question, QuestionType } from '../lib/api'
import {
  LLEVA_OPCIONES,
  OPCIONES_INICIALES,
  TIPOS,
  VARIAS_CORRECTAS,
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
  const [busqueda, setBusqueda] = useState('')
  const [tipoFiltro, setTipoFiltro] = useState('')
  const [pagina, setPagina] = useState(1)
  const [porPagina, setPorPagina] = useState(5)
  const termino = normalizar(busqueda.trim())
  const filtradas = preguntas.filter((pregunta) => {
    if (tipoFiltro && pregunta.question_type !== tipoFiltro) return false
    if (!termino) return true
    const texto = normalizar(
      [pregunta.statement, ...pregunta.options.map((opcion) => opcion.option_text)].join(' ')
    )
    return texto.includes(termino)
  })
  const paginas = Math.max(1, Math.ceil(filtradas.length / porPagina))
  const paginaActual = Math.min(pagina, paginas)
  const inicio = (paginaActual - 1) * porPagina
  const visibles = filtradas.slice(inicio, inicio + porPagina)

  return (
    <>
      <div className="preguntas-controles">
        <label className="campo preguntas-busqueda">
          <span>Buscar preguntas</span>
          <input
            type="search"
            value={busqueda}
            onChange={(evento) => {
              setBusqueda(evento.target.value)
              setPagina(1)
            }}
            placeholder="Escribe parte del enunciado o una opción"
          />
        </label>
        <label className="campo preguntas-filtro">
          <span>Tipo de pregunta</span>
          <select
            value={tipoFiltro}
            onChange={(evento) => {
              setTipoFiltro(evento.target.value)
              setPagina(1)
            }}
          >
            <option value="">Todos los tipos</option>
            {TIPOS.map((tipo) => (
              <option key={tipo.valor} value={tipo.valor}>
                {tipo.nombre}
              </option>
            ))}
          </select>
        </label>
        <label className="campo preguntas-cantidad">
          <span>Preguntas por página</span>
          <select
            value={porPagina}
            onChange={(evento) => {
              setPorPagina(Number(evento.target.value))
              setPagina(1)
            }}
          >
            {[5, 10, 20, 50].map((cantidad) => (
              <option key={cantidad} value={cantidad}>
                {cantidad}
              </option>
            ))}
          </select>
        </label>
      </div>

      <p className="preguntas-conteo" aria-live="polite">
        {filtradas.length === preguntas.length
          ? `${preguntas.length} preguntas`
          : `${filtradas.length} de ${preguntas.length} preguntas`}
        {filtradas.length > 0 && ` · mostrando ${inicio + 1}–${inicio + visibles.length}`}
      </p>

      {filtradas.length === 0 ? (
        <div className="tarjeta">
          <p className="tarjeta-cuerpo">
            {preguntas.length === 0
              ? 'Todavía no hay preguntas.'
              : 'No hay preguntas que coincidan. Prueba otra búsqueda o tipo.'}
          </p>
        </div>
      ) : (
        <>
          <PaginacionPreguntas pagina={paginaActual} paginas={paginas} alCambiar={setPagina} />
          <ol
            className="lista-preguntas numerada preguntas-compactas"
            style={{ counterReset: `pregunta ${inicio}` }}
          >
            {visibles.map((pregunta) => (
              <li key={pregunta.id} className="tarjeta">
                <details className="pregunta-desplegable">
                  <summary className="pregunta-resumen">
                    <div className="pregunta-resumen-texto">
                      <h4>{nombreDeTipo(pregunta.question_type)}</h4>
                      <p>{pregunta.statement}</p>
                    </div>
                    <span className="pregunta-puntos">{pregunta.points} pts</span>
                  </summary>
                  <div className="tarjeta-cuerpo pregunta-detalle">
                    {pregunta.options.length > 0 && (
                      <ul className="lista-opciones">
                        {pregunta.options.map((opcion) => (
                          <li key={opcion.id} className={opcion.is_correct ? 'correcta' : ''}>
                            {opcion.option_text}
                          </li>
                        ))}
                      </ul>
                    )}
                    {pregunta.correct_numeric_answer !== null && (
                      <p className="ayuda">Respuesta: {pregunta.correct_numeric_answer}</p>
                    )}
                    {pregunta.correct_text_answer && (
                      <p className="ayuda">Respuesta: {pregunta.correct_text_answer}</p>
                    )}
                    {onCambiarPuntos && (
                      <PuntosEditables
                        puntos={pregunta.points}
                        onGuardar={(valor) => onCambiarPuntos(pregunta.id, valor)}
                      />
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
                </details>
              </li>
            ))}
          </ol>
          <PaginacionPreguntas pagina={paginaActual} paginas={paginas} alCambiar={setPagina} />
        </>
      )}
    </>
  )
}

function PaginacionPreguntas({
  pagina,
  paginas,
  alCambiar
}: {
  pagina: number
  paginas: number
  alCambiar: (pagina: number) => void
}) {
  if (paginas <= 1) return null

  return (
    <nav className="preguntas-paginacion" aria-label="Páginas de preguntas">
      <button
        type="button"
        className="boton boton-secundario"
        disabled={pagina === 1}
        onClick={() => alCambiar(pagina - 1)}
      >
        Anterior
      </button>
      <span>
        Página {pagina} de {paginas}
      </span>
      <button
        type="button"
        className="boton boton-secundario"
        disabled={pagina === paginas}
        onClick={() => alCambiar(pagina + 1)}
      >
        Siguiente
      </button>
    </nav>
  )
}

function normalizar(texto: string): string {
  return texto
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase()
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
  const puedeAgregar = tipo !== 'true_false' && opciones.length < 10
  const varias = tipo === VARIAS_CORRECTAS
  const puedeQuitar = opciones.length > 2

  function cambiar(indice: number, cambios: Partial<OpcionEditable>): void {
    onCambio(opciones.map((o, i) => (i === indice ? { ...o, ...cambios } : o)))
  }

  /** En una de respuesta única, marcar una desmarca la anterior.
   *
   *  El dominio de la API admite varias correctas en `multiple_choice` —hace
   *  falta al importar QTI, y significa «vale cualquiera de ellas»—, pero la
   *  respuesta guardada apunta a **una** opción. Con varias marcadas el
   *  estudiante no podría expresar su respuesta entera, así que el editor solo
   *  produce lo que el sistema sabe calificar. Para marcar varias existe el
   *  tipo de varias correctas, que se guarda distinto. */
  function marcarCorrecta(indice: number): void {
    onCambio(opciones.map((o, i) => ({ ...o, is_correct: i === indice })))
  }

  /** En una de varias correctas cada opción se marca y desmarca por su cuenta. */
  function alternarCorrecta(indice: number): void {
    onCambio(opciones.map((o, i) => (i === indice ? { ...o, is_correct: !o.is_correct } : o)))
  }

  return (
    <div className="campo">
      <span>Opciones</span>
      <p className="ayuda" style={{ marginBottom: 'var(--e2)' }}>
        {varias
          ? 'Marca todas las correctas, al menos dos. El estudiante acierta si marca exactamente esas.'
          : 'Marca cuál es la correcta. El estudiante elige una sola.'}
      </p>

      <ul className="editor-opciones">
        {opciones.map((opcion, indice) => (
          <li key={indice}>
            <input
              type={varias ? 'checkbox' : 'radio'}
              name={varias ? undefined : 'opcion-correcta'}
              checked={opcion.is_correct}
              onChange={() => (varias ? alternarCorrecta(indice) : marcarCorrecta(indice))}
              aria-label={
                varias
                  ? `La opción ${indice + 1} es una de las correctas`
                  : `La opción ${indice + 1} es la correcta`
              }
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
