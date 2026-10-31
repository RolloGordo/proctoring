import { useRef, useState } from 'react'
import { api, type NewQuestion, type QtiImportResult, type QuestionBank } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import {
  dividirEnLotes,
  parsearArchivoPreguntas,
  parsearTextoPdf,
  type FormatoArchivoPreguntas
} from '../lib/importar-preguntas'

type ArchivoImportable = {
  nombre: string
  contenido: string
  formato: 'qti' | 'pdf' | FormatoArchivoPreguntas
}

function observarPregunta(pregunta: NewQuestion): string[] {
  const observaciones: string[] = []
  const requiereOpciones = ['multiple_choice', 'true_false', 'multiple_select'].includes(
    pregunta.question_type
  )
  if (!pregunta.statement.trim()) observaciones.push('Falta el enunciado.')
  if (requiereOpciones && !pregunta.options?.length) {
    observaciones.push('Faltan las alternativas.')
  } else if (requiereOpciones && !pregunta.options?.some((opcion) => opcion.is_correct)) {
    observaciones.push('No se marcó una respuesta correcta.')
  }
  if (pregunta.question_type === 'numeric' && !pregunta.correct_numeric_answer?.trim()) {
    observaciones.push('Falta la respuesta numérica correcta.')
  }
  return observaciones
}

const MAX_PREGUNTAS_POR_IMPORTACION = 50
const MAX_ARCHIVO_BYTES = 1_000_000
const MAX_PDF_BYTES = 5_000_000

export function ImportarPreguntas({
  bancoId,
  nombreBanco,
  crearBanco,
  onImportado
}: {
  bancoId?: string
  nombreBanco?: string
  crearBanco?: () => Promise<QuestionBank>
  onImportado: (bancoId: string, importedCount: number, completed: boolean) => void
}) {
  const { token } = useAuth()
  const entrada = useRef<HTMLInputElement>(null)
  const [archivo, setArchivo] = useState<ArchivoImportable>()
  const [vistaQti, setVistaQti] = useState<QtiImportResult>()
  const [vistaPreguntas, setVistaPreguntas] = useState<NewQuestion[]>()
  const [resultado, setResultado] = useState<string>()
  const [error, setError] = useState<string>()
  const [trabajando, setTrabajando] = useState(false)
  const [importadas, setImportadas] = useState(0)
  const [bancoImportacionId, setBancoImportacionId] = useState<string>()
  const [indicePrevisualizado, setIndicePrevisualizado] = useState(0)
  const destinoTexto = bancoId
    ? `«${nombreBanco || 'este banco'}»`
    : nombreBanco?.trim()
      ? `«${nombreBanco.trim()}»`
      : 'el banco nuevo cuyo nombre indiques arriba'

  function limpiar(): void {
    setArchivo(undefined)
    setVistaQti(undefined)
    setVistaPreguntas(undefined)
    setError(undefined)
    setImportadas(0)
    setBancoImportacionId(undefined)
    setIndicePrevisualizado(0)
    if (entrada.current) entrada.current.value = ''
  }

  async function cancelar(): Promise<void> {
    if (!bancoId && bancoImportacionId && importadas === 0) {
      setTrabajando(true)
      try {
        await api.deleteBank(bancoImportacionId, token)
      } catch (fallo) {
        setError(fallo instanceof Error ? fallo.message : 'No se pudo eliminar el banco vacío.')
        return
      } finally {
        setTrabajando(false)
      }
    } else if (
      importadas > 0 &&
      !confirm(
        `El banco parcial conservará las ${importadas} preguntas ya importadas. Puedes eliminarlo desde «Mis bancos». ¿Cerrar la importación?`
      )
    ) {
      return
    }
    limpiar()
  }

  async function elegir(fichero: File | undefined): Promise<void> {
    if (!fichero) return
    limpiar()
    setResultado(undefined)
    setTrabajando(true)
    try {
      const extension = fichero.name.split('.').pop()?.toLowerCase()
      if (
        extension !== 'xml' &&
        extension !== 'csv' &&
        extension !== 'json' &&
        extension !== 'txt' &&
        extension !== 'pdf'
      ) {
        throw new Error('Elige un archivo XML, CSV, JSON, TXT o PDF.')
      }
      const formato: ArchivoImportable['formato'] =
        extension === 'xml'
          ? 'qti'
          : (extension as Exclude<ArchivoImportable['formato'], 'qti'>)
      const limite = formato === 'pdf' ? MAX_PDF_BYTES : MAX_ARCHIVO_BYTES
      if (fichero.size > limite) {
        throw new Error(`El archivo supera el límite de ${limite / 1_000_000} MB.`)
      }

      if (formato === 'pdf') {
        const { extraerTextoPdf } = await import('../lib/extraer-pdf')
        const texto = await extraerTextoPdf(fichero)
        if (!texto) {
          throw new Error(
            'No se pudo extraer texto del PDF. Comprueba que no sea un documento escaneado.'
          )
        }
        const preguntas = parsearTextoPdf(texto)
        setArchivo({ nombre: fichero.name, contenido: texto, formato })
        setVistaPreguntas(preguntas)
        return
      }

      const contenido = await fichero.text()
      setArchivo({ nombre: fichero.name, contenido, formato })
      if (formato === 'qti') {
        if (bancoId) {
          setVistaQti(await api.importQti(bancoId, contenido, { token, dryRun: true }))
        }
      } else {
        setVistaPreguntas(parsearArchivoPreguntas(contenido, formato as FormatoArchivoPreguntas))
      }
    } catch (fallo) {
      setArchivo(undefined)
      setError(fallo instanceof Error ? fallo.message : 'No se pudo leer el archivo.')
    } finally {
      setTrabajando(false)
    }
  }

  async function confirmar(): Promise<void> {
    if (!archivo || (!bancoId && !crearBanco)) return
    setError(undefined)
    setTrabajando(true)
    let completadas = importadas
    let destinoId = bancoId ?? bancoImportacionId
    try {
      if (!destinoId) {
        if (!crearBanco) throw new Error('No está configurada la creación del banco.')
        const destino = await crearBanco()
        destinoId = destino.id
        setBancoImportacionId(destinoId)
      }

      if (archivo.formato === 'qti') {
        completadas = (await api.importQti(destinoId, archivo.contenido, { token })).imported_count
        if (completadas === 0 && !bancoId) {
          await api.deleteBank(destinoId, token)
          limpiar()
          setResultado('El archivo no contenía preguntas importables; no se creó ningún banco.')
          return
        }
      } else {
        const preguntas = vistaPreguntas ?? []
        const lotes = dividirEnLotes(preguntas, MAX_PREGUNTAS_POR_IMPORTACION)
        while (completadas < preguntas.length) {
          const lote = lotes[Math.floor(completadas / MAX_PREGUNTAS_POR_IMPORTACION)]
          if (!lote) throw new Error('No se pudo determinar el siguiente grupo de preguntas.')
          await api.addBankQuestions(destinoId, lote, token)
          completadas += lote.length
          setImportadas(completadas)
        }
      }
      limpiar()
      onImportado(destinoId, completadas, true)
      setResultado(
        `${completadas} pregunta${completadas === 1 ? '' : 's'} importada${completadas === 1 ? '' : 's'} en «${nombreBanco ?? 'el banco'}».`
      )
    } catch (fallo) {
      setImportadas(completadas)
      const detalle = fallo instanceof Error ? fallo.message : 'Error no identificado'
      setError(
        completadas > 0
          ? `Se importaron ${completadas} de ${vistaPreguntas?.length ?? 0} preguntas. La importación se detuvo: ${detalle} Puedes continuar sin duplicar las que ya entraron.`
          : detalle
      )
      if (completadas > 0 && destinoId) onImportado(destinoId, completadas, false)
    } finally {
      setTrabajando(false)
    }
  }

  return (
    <div className="importador-preguntas">
      <section className="tarjeta importacion-archivo">
        <div className="tarjeta-cuerpo">
          <div className="campo">
      <span>Importar preguntas desde un archivo</span>
      <p className="ayuda">
        Se admite QTI XML, CSV, JSON, TXT y PDF con texto seleccionable (máximo 5 MB; otros
        formatos, 1 MB).{' '}
        {bancoId
          ? `La importación se agrega a «${nombreBanco ?? 'este banco'}».`
          : 'El archivo se agregará al banco cuando confirmes su nombre.'}{' '}
        Primero revisa la vista previa.
      </p>
      <details className="ayuda-formatos">
        <summary>Ver formatos y ejemplos</summary>
        <p>
          <strong>CSV:</strong> encabezados{' '}
          <code>question_type,statement,points,options,correct_answer</code>. En opciones, separa
          alternativas con <code>|</code>; la respuesta correcta debe coincidir con una alternativa.
        </p>
        <pre>{`multiple_choice,"¿Cuánto es 2 + 2?",1,"3|4|5","4"
numeric,"¿Cuánto es 5 × 3?",1,,"15"
essay,"Explica tu procedimiento",2,,`}</pre>
        <p>
          <strong>JSON:</strong> una lista con objetos de pregunta. Las opciones usan
          <code> option_text</code> y <code>is_correct</code>.
        </p>
        <pre>{`[
  {
    "question_type": "multiple_choice",
    "statement": "¿Cuánto es 2 + 2?",
    "points": "1",
    "options": [
      { "option_text": "4", "is_correct": true },
      { "option_text": "5", "is_correct": false }
    ]
  }
]`}</pre>
        <p>
          <strong>TXT/PDF:</strong> para preguntas de opción múltiple, usa bloques{' '}
          <code>PREGUNTA 1:</code>, alternativas <code>A)</code>, <code>B)</code>, etc. y una{' '}
          <code>CLAVE DE RESPUESTAS</code> con líneas como <code>1. Respuesta: B</code>. También
          admite el formato sencillo de una pregunta de desarrollo por línea; esas requieren
          calificación manual. Las justificaciones no se importan. El XML debe ser una exportación
          QTI. Los PDF escaneados y las justificaciones extensas no se extraen como preguntas.
        </p>
      </details>

      <input
        ref={entrada}
        type="file"
        accept=".xml,.csv,.json,.txt,.pdf,application/xml,text/csv,application/json,text/plain,application/pdf"
        disabled={trabajando || bancoImportacionId !== undefined || importadas > 0}
        onChange={(e) => void elegir(e.target.files?.[0])}
        aria-label="Archivo de preguntas"
      />

      {error && (
        <p className="aviso" role="alert">
          {error}
        </p>
      )}
      {resultado && <p className="aviso aviso-exito">{resultado}</p>}
      {trabajando && <p className="ayuda">Leyendo el archivo…</p>}
          </div>
        </div>
      </section>

      {vistaPreguntas && archivo && (
        <div className="tarjeta importacion-vista-previa">
          <div className="tarjeta-cuerpo">
            <h4>Vista previa: {archivo.nombre}</h4>
            <p className="ayuda">
              {vistaPreguntas.length} pregunta{vistaPreguntas.length === 1 ? '' : 's'} lista
              {vistaPreguntas.length === 1 ? '' : 's'} para importar.
              {archivo.formato === 'txt' &&
                ` ${vistaPreguntas.filter((pregunta) => pregunta.question_type === 'multiple_choice').length} de opción múltiple.`}
              {archivo.formato === 'pdf' &&
                ` ${vistaPreguntas.filter((pregunta) => pregunta.question_type === 'multiple_choice').length} de opción múltiple.`}
              {importadas > 0 && ` Ya se importaron ${importadas}.`}
            </p>
            <p className="ayuda">
              Se guardarán en {destinoTexto}.
            </p>
            {(archivo.formato === 'txt' || archivo.formato === 'pdf') && (
              <p className="aviso aviso-neutro">
                Revisa que cada enunciado tenga sus alternativas y que la clave marque la respuesta
                correcta.
              </p>
            )}
            {vistaPreguntas.length > 0 && (
              <>
                <div className="importacion-navegacion">
                  <button
                    type="button"
                    className="boton boton-secundario"
                    disabled={indicePrevisualizado === 0}
                    onClick={() => setIndicePrevisualizado((indice) => Math.max(0, indice - 1))}
                    aria-label="Ver pregunta anterior"
                  >
                    ← Anterior
                  </button>
                  <label className="campo">
                    <span>Revisar pregunta</span>
                    <select
                      value={indicePrevisualizado}
                      onChange={(evento) => setIndicePrevisualizado(Number(evento.target.value))}
                    >
                      {vistaPreguntas.map((pregunta, indice) => (
                        <option key={`${indice}-${pregunta.statement}`} value={indice}>
                          {observarPregunta(pregunta).length > 0 ? 'Revisar · ' : ''}
                          {indice + 1}. {pregunta.statement.slice(0, 80)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    className="boton boton-secundario"
                    disabled={indicePrevisualizado >= vistaPreguntas.length - 1}
                    onClick={() =>
                      setIndicePrevisualizado((indice) => Math.min(vistaPreguntas.length - 1, indice + 1))
                    }
                    aria-label="Ver pregunta siguiente"
                  >
                    Siguiente →
                  </button>
                </div>
                <div className="fila importacion-acciones">
                  <button
                    type="button"
                    className="boton"
                    disabled={trabajando || (!bancoId && !nombreBanco?.trim())}
                    onClick={() => void confirmar()}
                  >
                    {trabajando
                      ? `Importando ${importadas + 1} de ${vistaPreguntas.length}…`
                      : importadas > 0
                        ? 'Continuar importación'
                        : 'Importar al banco'}
                  </button>
                  <button
                    type="button"
                    className="boton boton-secundario"
                    disabled={trabajando}
                    onClick={() => void cancelar()}
                  >
                    {importadas > 0 ? 'Cerrar importación' : 'Cancelar'}
                  </button>
                </div>
              </>
            )}
            {vistaPreguntas.length === 0 && (
              <>
                <p className="aviso aviso-neutro">No se encontraron preguntas importables en este archivo.</p>
                <div className="fila importacion-acciones">
                  <button
                    type="button"
                    className="boton boton-secundario"
                    disabled={trabajando}
                    onClick={() => void cancelar()}
                  >
                    Cerrar vista previa
                  </button>
                </div>
              </>
            )}
            {vistaPreguntas[indicePrevisualizado] && (
              <section className="importacion-simulacion">
                {(() => {
                  const pregunta = vistaPreguntas[indicePrevisualizado]
                  const observaciones = observarPregunta(pregunta)
                  const correctas = pregunta.options?.filter((opcion) => opcion.is_correct) ?? []
                  return (
                    <>
                      <div className="importacion-simulacion-cabecera">
                        <div>
                          <span className="importacion-pregunta-tipo">Vista del estudiante</span>
                          <h4 aria-live="polite">Pregunta {indicePrevisualizado + 1} de {vistaPreguntas.length}</h4>
                        </div>
                        <span className="importacion-simulacion-puntos">{pregunta.points ?? '1'} pts</span>
                      </div>
                      <div className="importacion-simulacion-cuerpo">
                        <p className="importacion-enunciado">{pregunta.statement}</p>
                        {pregunta.options?.length ? (
                          <ul className="importacion-respuestas-estudiante">
                            {pregunta.options.map((opcion, opcionIndice) => (
                              <li key={`${opcionIndice}-${opcion.option_text}`}>
                                <span
                                  className={`importacion-circulo${pregunta.question_type === 'multiple_select' ? ' multiple' : ''}`}
                                  aria-hidden="true"
                                />
                                <span>{opcion.option_text}</span>
                              </li>
                            ))}
                          </ul>
                        ) : pregunta.question_type === 'numeric' ? (
                          <div className="importacion-campo-ejemplo">La respuesta numérica aparecerá aquí</div>
                        ) : (
                          <div className="importacion-campo-ejemplo importacion-campo-desarrollo">
                            El estudiante escribirá su respuesta aquí
                          </div>
                        )}
                      </div>
                      <div className="importacion-revision-docente">
                        <strong>Revisión docente</strong>
                        {observaciones.length > 0 ? (
                          <ul>
                            {observaciones.map((observacion) => <li key={observacion}>{observacion}</li>)}
                          </ul>
                        ) : correctas.length > 0 ? (
                          <p>Respuesta{correctas.length === 1 ? '' : 's'} correcta{correctas.length === 1 ? '' : 's'}: {correctas.map((opcion) => opcion.option_text).join(', ')}</p>
                        ) : pregunta.question_type === 'numeric' && pregunta.correct_numeric_answer ? (
                          <p>Respuesta correcta: {pregunta.correct_numeric_answer}</p>
                        ) : pregunta.correct_text_answer ? (
                          <p>Respuesta de referencia: {pregunta.correct_text_answer}</p>
                        ) : (
                          <p>Respuesta abierta; requiere revisión manual.</p>
                        )}
                      </div>
                    </>
                  )
                })()}
              </section>
            )}
          </div>
        </div>
      )}

      {vistaQti && archivo && (
        <div className="tarjeta importacion-vista-previa">
          <div className="tarjeta-cuerpo">
            <h4>
              {vistaQti.imported_count === 0 && vistaQti.warnings.length === 0
                ? 'Revisa el archivo QTI'
                : 'Vista previa del archivo QTI'}
            </h4>
            <p className="ayuda">
              {archivo.nombre} · Archivo analizado; confirma para guardar las preguntas válidas.
              {vistaQti.skipped.length > 0 &&
                ` · ${vistaQti.skipped.length} preguntas no se pueden importar`}
            </p>
            {vistaQti.warnings.length > 0 && (
              <ul className="lista-modulos">
                {vistaQti.warnings.map((aviso) => (
                  <li key={aviso.item_id}>
                    <strong>{aviso.item_id}</strong> · {aviso.reason}
                  </li>
                ))}
              </ul>
            )}
            {vistaQti.skipped.length > 0 && (
              <ul className="lista-modulos">
                {vistaQti.skipped.map((item) => (
                  <li key={item.item_id}>
                    <strong>{item.item_id}</strong> · {item.reason}
                  </li>
                ))}
              </ul>
            )}
            <div className="fila importacion-acciones">
              <button
                type="button"
                className="boton"
                disabled={trabajando || (!bancoId && !nombreBanco?.trim())}
                onClick={() => void confirmar()}
              >
                {trabajando ? 'Importando…' : 'Importar al banco'}
              </button>
              <button
                type="button"
                className="boton boton-secundario"
                disabled={trabajando}
                onClick={() => void cancelar()}
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      {archivo?.formato === 'qti' && !vistaQti && (
        <div className="tarjeta importacion-vista-previa">
          <div className="tarjeta-cuerpo">
            <h4>Archivo QTI listo</h4>
            <p className="ayuda">
              {archivo.nombre} se validará al importarlo y se agregará a {destinoTexto}.
            </p>
            <div className="fila importacion-acciones">
              <button
                type="button"
                className="boton"
                disabled={trabajando || !nombreBanco?.trim()}
                onClick={() => void confirmar()}
              >
                {trabajando ? 'Importando…' : 'Importar al banco'}
              </button>
              <button
                type="button"
                className="boton boton-secundario"
                disabled={trabajando}
                onClick={() => void cancelar()}
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
