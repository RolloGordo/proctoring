import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { EditorPregunta, ListaPreguntas } from '../components/EditorPregunta'
import { ImportarQti } from '../components/ImportarQti'
import { api, type NewQuestion, type Question, type QuestionBank } from '../lib/api'
import { useAuth } from '../lib/auth-context'

/** Las preguntas de un banco, con sus respuestas correctas. */
export function Banco() {
  const { id = '' } = useParams()
  const { token } = useAuth()

  const [banco, setBanco] = useState<QuestionBank>()
  const [preguntas, setPreguntas] = useState<Question[]>()
  const [error, setError] = useState<string>()

  function recargar(): void {
    api
      .listBankQuestions(id, token)
      .then(setPreguntas)
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

  async function cambiarPuntos(preguntaId: string, puntos: string): Promise<void> {
    setError(undefined)
    try {
      const corregida = await api.updateQuestion(preguntaId, { points: puntos }, token)
      setPreguntas((previas) =>
        (previas ?? []).map((p) => (p.id === preguntaId ? corregida : p))
      )
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

  return (
    <>
      <div className="encabezado-pagina">
        <div>
          <h1>{banco?.name ?? 'Banco de preguntas'}</h1>
          <p className="subtitulo">
            {preguntas ? `${cuantas} pregunta${cuantas === 1 ? '' : 's'}` : 'Cargando…'}
          </p>
        </div>
        <Link to="/bancos" className="boton boton-secundario">
          Volver a mis bancos
        </Link>
      </div>

      {error && <p className="aviso">{error}</p>}

      <div className="columnas">
        <section>
          <div className="encabezado-seccion">
            <h2>Añadir preguntas</h2>
          </div>

          <div className="tarjeta">
            <div className="tarjeta-cuerpo">
              <ImportarQti bancoId={id} onImportado={recargar} />
              <hr className="separador" />
              <EditorPregunta onGuardar={agregar} textoBoton="Añadir al banco" />
            </div>
          </div>
        </section>

        <section>
          <div className="encabezado-seccion">
            <h2>En el banco</h2>
          </div>

          {preguntas?.length === 0 ? (
            <div className="tarjeta">
              <div className="vacio">
                <h3>El banco está vacío</h3>
                <p className="subtitulo">
                  Añade la primera pregunta a la izquierda. Un banco con muchas preguntas es lo que
                  permite que cada estudiante reciba un examen distinto.
                </p>
              </div>
            </div>
          ) : (
            <ListaPreguntas
              preguntas={preguntas ?? []}
              onCambiarPuntos={cambiarPuntos}
              onBorrar={borrar}
            />
          )}
        </section>
      </div>
    </>
  )
}
