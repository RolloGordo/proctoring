import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { EditorPregunta, ListaPreguntas } from '../components/EditorPregunta'
import { api, type NewQuestion, type Question, type QuestionBank } from '../lib/api'
import { useAuth } from '../lib/auth-context'

export function Preguntas() {
  const { id = '' } = useParams()
  const { token } = useAuth()

  const [preguntas, setPreguntas] = useState<Question[]>()
  const [bancos, setBancos] = useState<QuestionBank[]>([])
  const [error, setError] = useState<string>()

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
  }, [id, token])

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

      {error && <p className="aviso">{error}</p>}

      {bancos.length > 0 && (
        <div className="tarjeta" style={{ marginBottom: 'var(--e4)' }}>
          <div className="tarjeta-cuerpo">
            <h4>Este examen extrae de {bancos.length === 1 ? 'un banco' : `${bancos.length} bancos`}</h4>
            <p className="ayuda">
              Las preguntas del estudiante salen de {delBanco} pregunta{delBanco === 1 ? '' : 's'} de{' '}
              {bancos.map((b) => b.name).join(', ')}. Las que añadas aquí abajo{' '}
              <strong>no se usarán</strong> mientras haya bancos atados.
            </p>
            <Link to={`/sesiones/${id}`} className="boton boton-texto">
              Gestionar los bancos del examen
            </Link>
          </div>
        </div>
      )}

      <div className="columnas">
        <section>
          <div className="encabezado-seccion">
            <h2>Añadir pregunta</h2>
          </div>

          <div className="tarjeta">
            <div className="tarjeta-cuerpo">
              <EditorPregunta onGuardar={agregar} />
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
                  Un examen sin preguntas no se puede rendir. Añade la primera a la izquierda, o
                  ata un banco al examen para reutilizar las de otro ciclo.
                </p>
              </div>
            </div>
          ) : (
            <ListaPreguntas preguntas={preguntas ?? []} />
          )}
        </section>
      </div>
    </>
  )
}
