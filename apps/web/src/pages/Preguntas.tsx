import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { EditorPregunta, ListaPreguntas } from '../components/EditorPregunta'
import { api, type NewQuestion, type Question, type QuestionBank } from '../lib/api'
import { useAuth } from '../lib/auth-context'

export function Preguntas() {
  const { id = '' } = useParams()
  const location = useLocation()
  const { token } = useAuth()

  const [preguntas, setPreguntas] = useState<Question[]>()
  const [bancos, setBancos] = useState<QuestionBank[]>([])
  /** Cuántos ya entregaron. En cuanto hay uno, el examen deja de ser editable. */
  const [entregados, setEntregados] = useState(0)
  const [error, setError] = useState<string>()
  const [mostrarEditor, setMostrarEditor] = useState(() =>
    Boolean(obtenerAvisoDeRuta(location.state))
  )

  useEffect(() => {
    api
      .listQuestions(id, token)
      .then(setPreguntas)
      .catch((fallo: Error) => setError(fallo.message))
    // Si el examen extrae de bancos, estas preguntas propias no son las que
    // verá el estudiante. Hay que decirlo, o el docente añadiría aquí
    // preguntas que nunca aparecen.
    api
      .listSessionBanks(id, token)
      .then(setBancos)
      .catch(() => undefined)
    // Para saber si el examen sigue siendo editable. Si esto falla, no se
    // bloquea nada: la API es la que manda, y rechaza igual.
    api
      .listParticipants(id, token)
      .then((lista) => setEntregados(lista.filter((p) => p.submitted_at !== null).length))
      .catch(() => undefined)
  }, [id, token])

  async function cambiarPuntos(preguntaId: string, puntos: string): Promise<void> {
    setError(undefined)
    try {
      const corregida = await api.updateQuestion(preguntaId, { points: puntos }, token)
      setPreguntas((previas) => (previas ?? []).map((p) => (p.id === preguntaId ? corregida : p)))
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudieron cambiar los puntos')
      throw fallo
    }
  }

  async function borrar(preguntaId: string): Promise<void> {
    if (!confirm('Se quitará esta pregunta del examen. ¿Seguro?')) return
    setError(undefined)
    try {
      await api.deleteQuestion(preguntaId, token)
      setPreguntas((previas) => (previas ?? []).filter((p) => p.id !== preguntaId))
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo quitar la pregunta')
    }
  }

  async function agregar(nueva: NewQuestion): Promise<void> {
    setError(undefined)
    try {
      const creadas = await api.addQuestions(id, [nueva], token)
      setPreguntas((previas) => [...(previas ?? []), ...creadas])
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo guardar la pregunta')
      throw fallo
    }
  }

  const puntosTotales = (preguntas ?? []).reduce((suma, p) => suma + Number(p.points), 0)
  const avisoInicial = obtenerAvisoDeRuta(location.state)
  const delBanco = bancos.reduce((suma, b) => suma + b.question_count, 0)

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

      {avisoInicial && (
        <p className="aviso aviso-neutro" role="status">
          {avisoInicial}
        </p>
      )}
      {error && <p className="aviso">{error}</p>}

      {bancos.length > 0 && (
        <div className="tarjeta" style={{ marginBottom: 'var(--e4)' }}>
          <div className="tarjeta-cuerpo">
            <h4>
              Este examen extrae de {bancos.length === 1 ? 'un banco' : `${bancos.length} bancos`}
            </h4>
            <p className="ayuda">
              Las preguntas del estudiante salen de {delBanco} pregunta{delBanco === 1 ? '' : 's'}{' '}
              de {bancos.map((b) => b.name).join(', ')}. Las que añadas aquí abajo{' '}
              <strong>no se usarán</strong> mientras haya bancos atados.
            </p>
            <Link to={`/sesiones/${id}`} className="boton boton-texto">
              Gestionar los bancos del examen
            </Link>
          </div>
        </div>
      )}

      {/* Un examen que alguien ya rindió no se toca.
        *
        * La API lo rechaza desde el 30/10, pero si la pantalla sigue ofreciendo
        * el botón, el docente se lleva un error donde antes no lo había y no
        * entiende por qué. Mejor explicarlo antes de que lo intente. */}
      {entregados > 0 && (
        <p className="aviso aviso-neutro">
          {entregados === 1
            ? 'Un estudiante ya entregó este examen'
            : `${entregados} estudiantes ya entregaron este examen`}
          , así que sus preguntas quedaron fijas. Una pregunta añadida ahora aparecería en el
          expediente como si hubiera formado parte de la prueba. Si necesitas una versión con más
          preguntas, duplica el examen.
        </p>
      )}

      <section className="bloque">
        <div className="encabezado-seccion">
          <h2>Preguntas del examen</h2>
          {entregados === 0 && (
            <button
              type="button"
              className="boton boton-secundario"
              aria-expanded={mostrarEditor}
              aria-controls="editor-pregunta-examen"
              onClick={() => setMostrarEditor((abierto) => !abierto)}
            >
              {mostrarEditor ? 'Ocultar formulario' : 'Añadir pregunta'}
            </button>
          )}
        </div>

        {mostrarEditor && entregados === 0 && (
          <div id="editor-pregunta-examen" className="tarjeta preguntas-editor">
            <div className="tarjeta-cuerpo">
              <EditorPregunta onGuardar={agregar} />
            </div>
          </div>
        )}

        {!preguntas ? (
          <p className="tenue">Cargando preguntas…</p>
        ) : preguntas.length === 0 ? (
          <div className="tarjeta">
            <div className="vacio">
              <h3>Todavía no hay preguntas propias</h3>
              <p className="subtitulo">
                Un examen sin preguntas no se puede rendir. Añade una pregunta o asocia un banco.
              </p>
              {!mostrarEditor && entregados === 0 && (
                <button type="button" className="boton" onClick={() => setMostrarEditor(true)}>
                  Añadir pregunta
                </button>
              )}
            </div>
          </div>
        ) : (
          <ListaPreguntas preguntas={preguntas} onCambiarPuntos={cambiarPuntos} onBorrar={borrar} />
        )}
      </section>
    </>
  )
}

function obtenerAvisoDeRuta(estado: unknown): string | undefined {
  if (typeof estado !== 'object' || estado === null || !('aviso' in estado)) return
  return typeof estado.aviso === 'string' ? estado.aviso : undefined
}
