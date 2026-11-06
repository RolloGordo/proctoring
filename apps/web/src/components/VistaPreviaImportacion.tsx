import { useState } from 'react'
import type { NewQuestion } from '../lib/api'

export interface GrupoPreguntasImportadas {
  id: string
  nombre: string
  preguntas: NewQuestion[]
}

function observaciones(pregunta: NewQuestion): string[] {
  const mensajes: string[] = []
  const requiereOpciones = ['multiple_choice', 'true_false', 'multiple_select'].includes(pregunta.question_type)
  if (!pregunta.statement.trim()) mensajes.push('Falta el enunciado.')
  if (requiereOpciones && !pregunta.options?.length) mensajes.push('Faltan las alternativas.')
  else if (requiereOpciones && !pregunta.options?.some((opcion) => opcion.is_correct)) mensajes.push('No se marcó una respuesta correcta.')
  if (pregunta.question_type === 'numeric' && !pregunta.correct_numeric_answer?.trim()) mensajes.push('Falta la respuesta numérica correcta.')
  return mensajes
}

export function VistaPreviaImportacion({
  grupos,
  seleccionable = false,
  seleccionDeshabilitada = false,
  onSeleccionadasChange
}: {
  grupos: GrupoPreguntasImportadas[]
  seleccionable?: boolean
  seleccionDeshabilitada?: boolean
  onSeleccionadasChange?: (preguntas: NewQuestion[]) => void
}) {
  const [grupoId, setGrupoId] = useState(grupos[0]?.id ?? '')
  const [indiceSeleccionado, setIndiceSeleccionado] = useState(0)
  const [excluidas, setExcluidas] = useState<Set<string>>(() => new Set())

  // Si el archivo elegido desaparece de la lista, se muestra el primero desde
  // su primera pregunta. Se deriva aquí en vez de corregir el estado dentro de
  // un efecto (react-hooks/set-state-in-effect).
  const grupoElegido = grupos.find((item) => item.id === grupoId)
  const grupo = grupoElegido ?? grupos[0]
  const indice = grupoElegido ? indiceSeleccionado : 0
  const pregunta = grupo?.preguntas[indice]
  if (!grupo) return null

  function elegirGrupo(id: string): void {
    setGrupoId(id)
    setIndiceSeleccionado(0)
  }

  function alternarInclusion(incluir: boolean): void {
    if (!grupo || !onSeleccionadasChange) return
    const clave = `${grupo.id}:${indice}`
    const nuevasExcluidas = new Set(excluidas)
    if (incluir) nuevasExcluidas.delete(clave)
    else nuevasExcluidas.add(clave)
    setExcluidas(nuevasExcluidas)
    onSeleccionadasChange(grupos.flatMap((item) => item.preguntas.filter((_, indice) =>
      !nuevasExcluidas.has(`${item.id}:${indice}`)
    )))
  }

  return (
    <section className="vista-previa-archivos" aria-label="Revisión de archivos y preguntas">
      <div className="vista-previa-archivos-cabecera">
        {grupos.length > 1 ? (
          <label className="campo">
            <span>Archivo de origen</span>
            <select value={grupo.id} onChange={(evento) => elegirGrupo(evento.target.value)}>
              {grupos.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.nombre} ({item.preguntas.length} preguntas)
                </option>
              ))}
            </select>
          </label>
        ) : (
          <div>
            <span className="vista-previa-archivos-etiqueta">Archivo de origen</span>
            <strong className="vista-previa-archivos-nombre">{grupo.nombre}</strong>
          </div>
        )}
        {seleccionable ? (
          <span className="vista-previa-archivos-conteo">
            {grupos.reduce((total, item) => total + item.preguntas.filter((_, indice) => !excluidas.has(`${item.id}:${indice}`)).length, 0)} de {grupos.reduce((total, item) => total + item.preguntas.length, 0)} seleccionadas
          </span>
        ) : (
          <span className="vista-previa-archivos-conteo">
            {grupo.preguntas.length} pregunta{grupo.preguntas.length === 1 ? '' : 's'}
          </span>
        )}
      </div>

      {grupo.preguntas.length > 0 && (
        <div className="vista-previa-pregunta-selector">
          <button
            type="button"
            className="boton boton-secundario"
            disabled={indice <= 0}
            onClick={() => setIndiceSeleccionado(indice - 1)}
          >Anterior</button>
          <label className="campo">
            <span>Pregunta a revisar</span>
            <select value={indice} onChange={(evento) => setIndiceSeleccionado(Number(evento.target.value))}>
              {grupo.preguntas.map((item, indice) => (
                <option key={`${indice}-${item.statement}`} value={indice}>
                  {indice + 1}. {item.statement.slice(0, 90)}
                </option>
              ))}
            </select>
          </label>
          <span className="vista-previa-archivos-conteo">{indice + 1} de {grupo.preguntas.length}</span>
          <button
            type="button"
            className="boton boton-secundario"
            disabled={indice >= grupo.preguntas.length - 1}
            onClick={() => setIndiceSeleccionado(indice + 1)}
          >Siguiente</button>
        </div>
      )}

      {pregunta && (
        <article className="importacion-simulacion">
          <div className="importacion-simulacion-cabecera">
            <div>
              <span className="importacion-pregunta-tipo">Vista del estudiante</span>
              <h4>Pregunta {indice + 1} de {grupo.preguntas.length}</h4>
            </div>
            <span className="importacion-simulacion-puntos">{pregunta.points ?? '1'} pts</span>
          </div>
          {seleccionable && (
            <label className="vista-previa-incluir">
              <input
                type="checkbox"
                checked={!excluidas.has(`${grupo.id}:${indice}`)}
                disabled={seleccionDeshabilitada}
                onChange={(evento) => alternarInclusion(evento.target.checked)}
              />
              <span>Incluir esta pregunta en el banco</span>
            </label>
          )}
          <div className="importacion-simulacion-cuerpo">
            <p className="importacion-enunciado">{pregunta.statement}</p>
            {pregunta.options?.length ? (
              <ul className="importacion-respuestas-estudiante">
                {pregunta.options.map((opcion, indice) => (
                  <li key={`${indice}-${opcion.option_text}`}>
                    <span className={`importacion-circulo${pregunta.question_type === 'multiple_select' ? ' multiple' : ''}`} aria-hidden="true" />
                    <span>{opcion.option_text}</span>
                  </li>
                ))}
              </ul>
            ) : pregunta.question_type === 'numeric' ? (
              <div className="importacion-campo-ejemplo">La respuesta numérica aparecerá aquí</div>
            ) : (
              <div className="importacion-campo-ejemplo importacion-campo-desarrollo">El estudiante escribirá su respuesta aquí</div>
            )}
          </div>
          <div className="importacion-revision-docente">
            <strong>Revisión docente</strong>
            {observaciones(pregunta).length ? (
              <ul>{observaciones(pregunta).map((mensaje) => <li key={mensaje}>{mensaje}</li>)}</ul>
            ) : pregunta.options?.some((opcion) => opcion.is_correct) ? (
              <p>Respuesta{pregunta.options.filter((opcion) => opcion.is_correct).length === 1 ? '' : 's'} correcta{pregunta.options.filter((opcion) => opcion.is_correct).length === 1 ? '' : 's'}: {pregunta.options.filter((opcion) => opcion.is_correct).map((opcion) => opcion.option_text).join(', ')}</p>
            ) : pregunta.correct_numeric_answer ? (
              <p>Respuesta correcta: {pregunta.correct_numeric_answer}</p>
            ) : pregunta.correct_text_answer ? (
              <p>Respuesta de referencia: {pregunta.correct_text_answer}</p>
            ) : (
              <p>Respuesta abierta; requiere revisión manual.</p>
            )}
          </div>
        </article>
      )}
    </section>
  )
}
