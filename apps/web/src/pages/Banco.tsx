import { useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { EditorPregunta, ListaPreguntas } from '../components/EditorPregunta'
import { ImportarPreguntas } from '../components/ImportarPreguntas'
import { api, type NewQuestion, type Question, type QuestionBank } from '../lib/api'
import { useAuth } from '../lib/auth-context'

/** Las preguntas de un banco, con sus respuestas correctas. */
export function Banco() {
  const { id = '' } = useParams()
  const [searchParams] = useSearchParams()
  const { token } = useAuth()

  const [banco, setBanco] = useState<QuestionBank>()
  const [preguntas, setPreguntas] = useState<Question[]>()
  const [error, setError] = useState<string>()
  const [mostrarEditor, setMostrarEditor] = useState(false)
  const [avisoImportacion, setAvisoImportacion] = useState<string>()
  // En una referencia y no en estado: lo único que hace es recordar que la
  // próxima lista que llegue hay que traerla a la vista. Guardarlo en estado
  // obligaba a apagarlo desde dentro del efecto, que es un render en cascada
  // y lo que el linter rechaza.
  const desplazarALista = useRef(false)
  const listaRef = useRef<HTMLElement>(null)

  function recargarPreguntas(): void {
    api
      .listBankQuestions(id, token)
      .then((datos) => {
        setPreguntas(datos)
        if (datos.length === 0) setMostrarEditor(true)
      })
      .catch((fallo: Error) => setError(fallo.message))
  }

  useEffect(() => {
    // No hay endpoint de "un banco": se saca de la lista, que de todas formas
    // es la que trae el conteo.
    api
      .listBanks(token)
      .then((todos) => setBanco(todos.find((b) => b.id === id)))
      .catch(() => undefined)
    api
      .listBankQuestions(id, token)
      .then(setPreguntas)
      .catch((fallo: Error) => setError(fallo.message))
  }, [id, token])

  useEffect(() => {
    if (!desplazarALista.current || !preguntas) return
    desplazarALista.current = false
    listaRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [preguntas])

  function alImportar(_bancoId: string, importadas: number, completada: boolean): void {
    recargarPreguntas()
    if (!completada) return
    setMostrarEditor(false)
    setAvisoImportacion(
      `${importadas} pregunta${importadas === 1 ? '' : 's'} importada${importadas === 1 ? '' : 's'}. Ya puedes revisarla${importadas === 1 ? '' : 's'} en el banco.`
    )
    desplazarALista.current = true
  }

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
    if (!confirm('Se quitará esta pregunta del banco. ¿Seguro?')) return
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
      const creadas = await api.addBankQuestions(id, [nueva], token)
      setPreguntas((previas) => [...(previas ?? []), ...creadas])
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo guardar la pregunta')
      throw fallo
    }
  }

  const cuantas = preguntas?.length ?? 0
  const cursoId = banco?.course_id ?? searchParams.get('curso')
  const parametrosExamen = new URLSearchParams({ banco: id })
  if (cursoId) parametrosExamen.set('curso', cursoId)
  const rutaBancos = searchParams.toString() ? `/bancos?${searchParams.toString()}` : '/bancos'

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>{banco?.name ?? 'Banco de preguntas'}</h1>
          <p className="subtitulo">
            {preguntas ? `${cuantas} pregunta${cuantas === 1 ? '' : 's'}` : 'Cargando…'}
          </p>
        </div>
        <div className="fila">
          {banco && cuantas > 0 && (
            <Link to={`/sesiones/nueva?${parametrosExamen.toString()}`} className="boton">
              Crear examen con este banco
            </Link>
          )}
          <Link to={rutaBancos} className="boton boton-secundario">
            Volver a mis bancos
          </Link>
        </div>
      </div>

      {error && <p className="aviso">{error}</p>}

      <section className="bloque" ref={listaRef}>
        <div className="encabezado-seccion">
          <h2>Preguntas del banco</h2>
          <button
            type="button"
            className="boton boton-secundario"
            aria-expanded={mostrarEditor}
            aria-controls="editor-preguntas-banco"
            onClick={() => setMostrarEditor((abierto) => !abierto)}
          >
            {mostrarEditor ? 'Ocultar formulario' : 'Añadir o importar preguntas'}
          </button>
        </div>

        {mostrarEditor && (
          <div id="editor-preguntas-banco" className="preguntas-editor">
            <ImportarPreguntas
              bancoId={id}
              nombreBanco={banco?.name}
              onImportado={alImportar}
            />
            <div className="tarjeta">
              <div className="tarjeta-cuerpo">
                <h3>Crear una pregunta</h3>
                <EditorPregunta onGuardar={agregar} textoBoton="Añadir al banco" />
              </div>
            </div>
          </div>
        )}

        {avisoImportacion && (
          <p className="aviso aviso-exito" role="status">
            {avisoImportacion}
          </p>
        )}

        {!preguntas ? (
          <p className="tenue">Cargando preguntas…</p>
        ) : preguntas.length === 0 ? (
          <div className="tarjeta">
            <div className="vacio">
              <h3>El banco todavía está vacío</h3>
              <p className="subtitulo">
                Añade preguntas o impórtalas desde un archivo. Después podrás reutilizar este banco
                en tus exámenes.
              </p>
              {!mostrarEditor && (
                <button type="button" className="boton" onClick={() => setMostrarEditor(true)}>
                  Añadir o importar preguntas
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
