import { useEffect, useRef, useState } from 'react'
import { api, type NewQuestion, type QtiImportResult, type QuestionBank } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import {
  dividirEnLotes,
  parsearArchivoPreguntas,
  parsearTextoPdf,
  type FormatoArchivoPreguntas
} from '../lib/importar-preguntas'
import { VistaPreviaImportacion } from './VistaPreviaImportacion'

type ArchivoImportable = {
  id: string
  nombre: string
  contenido: string
  formato: 'qti' | 'pdf' | FormatoArchivoPreguntas
  tamano: number
  ultimaModificacion: number
}

const MAX_PREGUNTAS_POR_IMPORTACION = 50
const MAX_ARCHIVO_BYTES = 1_000_000
const MAX_PDF_BYTES = 5_000_000
const MAX_ARCHIVOS = 10
const MAX_TOTAL_BYTES = 10_000_000
const MAX_TOTAL_PREGUNTAS = 1000

export function ImportarPreguntas({
  bancoId,
  nombreBanco,
  crearBanco,
  onImportado,
  onTrabajandoChange,
  onBancoCreado
}: {
  bancoId?: string
  nombreBanco?: string
  crearBanco?: () => Promise<QuestionBank>
  onImportado: (bancoId: string, importedCount: number, completed: boolean) => void
  onTrabajandoChange?: (trabajando: boolean) => void
  onBancoCreado?: (bancoId: string) => void
}) {
  const { token } = useAuth()
  const entrada = useRef<HTMLInputElement>(null)
  const [archivo, setArchivo] = useState<ArchivoImportable>()
  const [archivos, setArchivos] = useState<ArchivoImportable[]>([])
  const [origenesPreguntas, setOrigenesPreguntas] = useState<string[]>([])
  const [vistaQti, setVistaQti] = useState<QtiImportResult>()
  const [vistaPreguntas, setVistaPreguntas] = useState<NewQuestion[]>()
  const [preguntasSeleccionadas, setPreguntasSeleccionadas] = useState<NewQuestion[]>([])
  const [resultado, setResultado] = useState<string>()
  const [error, setError] = useState<string>()
  const [trabajando, setTrabajando] = useState(false)
  const [importadas, setImportadas] = useState(0)
  const [bancoImportacionId, setBancoImportacionId] = useState<string>()
  useEffect(() => onTrabajandoChange?.(trabajando), [onTrabajandoChange, trabajando])
  const destinoTexto = bancoId
    ? `«${nombreBanco || 'este banco'}»`
    : nombreBanco?.trim()
      ? `«${nombreBanco.trim()}»`
      : 'el banco nuevo cuyo nombre indiques arriba'

  function limpiar(): void {
    setArchivo(undefined)
    setArchivos([])
    setOrigenesPreguntas([])
    setVistaQti(undefined)
    setVistaPreguntas(undefined)
    setPreguntasSeleccionadas([])
    setError(undefined)
    setImportadas(0)
    setBancoImportacionId(undefined)
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

  async function elegir(lista?: FileList | null): Promise<void> {
    if (!lista?.length) return
    const seleccionados = [...lista]
    const yaAgregados = new Set(archivos.map((item) => `${item.nombre}:${item.tamano}:${item.ultimaModificacion}`))
    const nuevosSeleccionados = seleccionados.filter(
      (file) => !yaAgregados.has(`${file.name}:${file.size}:${file.lastModified}`)
    )
    if (nuevosSeleccionados.length === 0) {
      setError('Esos archivos ya estan en la lista.')
      return
    }
    const extensionQti = nuevosSeleccionados.some((file) => file.name.split('.').pop()?.toLowerCase() === 'xml')
    if (extensionQti && (nuevosSeleccionados.length > 1 || archivos.length > 0)) {
      setError('Los archivos QTI XML se importan por separado. Primero confirma o cancela la lista actual.')
      return
    }
    if (archivos.some((item) => item.formato === 'qti')) {
      setError('Confirma o cancela el archivo QTI antes de agregar otros formatos.')
      return
    }

    setError(undefined)
    setResultado(undefined)
    setTrabajando(true)
    try {
      if (archivos.length + nuevosSeleccionados.length > MAX_ARCHIVOS) {
        throw new Error(`Puedes agregar hasta ${MAX_ARCHIVOS} archivos por importacion.`)
      }
      const bytes = archivos.reduce((suma, item) => suma + item.tamano, 0) +
        nuevosSeleccionados.reduce((suma, file) => suma + file.size, 0)
      if (bytes > MAX_TOTAL_BYTES) throw new Error('Los archivos seleccionados superan los 10 MB en total.')

      const nuevos: ArchivoImportable[] = []
      const preguntasNuevas: NewQuestion[] = []
      const origenesNuevos: string[] = []
      const erroresArchivo: string[] = []
      let totalPreguntas = vistaPreguntas?.length ?? 0

      for (const file of nuevosSeleccionados) {
        try {
          const extension = file.name.split('.').pop()?.toLowerCase()
          if (!['xml', 'csv', 'json', 'txt', 'pdf'].includes(extension ?? '')) {
            throw new Error('Elige un archivo XML, CSV, JSON, TXT o PDF.')
          }
          const formato: ArchivoImportable['formato'] = extension === 'xml'
            ? 'qti'
            : extension as Exclude<ArchivoImportable['formato'], 'qti'>
          const limite = formato === 'pdf' ? MAX_PDF_BYTES : MAX_ARCHIVO_BYTES
          if (file.size > limite) throw new Error(`supera el limite de ${limite / 1_000_000} MB.`)

          if (formato === 'qti') {
            const contenido = await file.text()
            const qti = { id: `${file.name}:${file.size}:${file.lastModified}`, nombre: file.name, contenido, formato, tamano: file.size, ultimaModificacion: file.lastModified }
            setArchivo(qti)
            setArchivos([qti])
            setVistaPreguntas(undefined)
            setPreguntasSeleccionadas([])
            setOrigenesPreguntas([])
            setVistaQti(bancoId ? await api.importQti(bancoId, contenido, { token, dryRun: true }) : undefined)
            return
          }

          let contenido: string
          let detectadas: NewQuestion[]
          if (formato === 'pdf') {
            const { extraerTextoPdf } = await import('../lib/extraer-pdf')
            contenido = await extraerTextoPdf(file)
            if (!contenido) throw new Error('No se pudo extraer texto del PDF.')
            detectadas = parsearTextoPdf(contenido)
          } else {
            contenido = await file.text()
            detectadas = parsearArchivoPreguntas(contenido, formato)
          }
          if (totalPreguntas + detectadas.length > MAX_TOTAL_PREGUNTAS) {
            throw new Error(`El total supera el limite de ${MAX_TOTAL_PREGUNTAS} preguntas por importacion.`)
          }
          totalPreguntas += detectadas.length
          const id = `${file.name}:${file.size}:${file.lastModified}`
          nuevos.push({ id, nombre: file.name, contenido, formato, tamano: file.size, ultimaModificacion: file.lastModified })
          preguntasNuevas.push(...detectadas)
          origenesNuevos.push(...detectadas.map(() => id))
        } catch (fallo) {
          erroresArchivo.push(`${file.name}: ${fallo instanceof Error ? fallo.message : 'no se pudo leer.'}`)
        }
      }

      if (nuevos.length > 0) {
        const combinados = [...archivos, ...nuevos]
        setArchivos(combinados)
        setVistaQti(undefined)
        setVistaPreguntas([...(vistaPreguntas ?? []), ...preguntasNuevas])
        setPreguntasSeleccionadas((actuales) => [...actuales, ...preguntasNuevas])
        setOrigenesPreguntas([...origenesPreguntas, ...origenesNuevos])
        setArchivo({
          id: `lote:${Date.now()}`,
          nombre: `${combinados.length} archivos`,
          contenido: '',
          formato: combinados[0].formato,
          tamano: bytes,
          ultimaModificacion: Date.now()
        })
      }
      setError(erroresArchivo.length > 0 ? erroresArchivo.join(' | ') : undefined)
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudieron leer los archivos.')
    } finally {
      setTrabajando(false)
    }
  }

  async function confirmar(): Promise<void> {
    if (!archivo || preguntasSeleccionadas.length === 0 || (!bancoId && !crearBanco)) return
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
        onBancoCreado?.(destinoId)
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
        const preguntas = preguntasSeleccionadas
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
          ? `Se importaron ${completadas} de ${preguntasSeleccionadas.length} preguntas seleccionadas. La importación se detuvo: ${detalle} Puedes continuar sin duplicar las que ya entraron.`
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
          <span>{archivos.length > 0 ? 'Agregar otro archivo al banco' : 'Importar preguntas desde archivos'}</span>
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
        disabled={trabajando || bancoImportacionId !== undefined || importadas > 0 || archivos[0]?.formato === 'qti'}
        multiple
        onChange={(e) => {
          void elegir(e.currentTarget.files)
          e.currentTarget.value = ''
        }}
        aria-label="Archivo de preguntas"
      />
      {archivos.length > 0 && archivos[0].formato !== 'qti' && (
        <p className="ayuda">Puedes volver a seleccionar archivos; se acumularan en esta importacion.</p>
      )}

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
            <h4>Vista previa: {archivos.length > 1 ? `${archivos.length} archivos` : archivo.nombre}</h4>
            <p className="ayuda">
              {vistaPreguntas.length} pregunta{vistaPreguntas.length === 1 ? '' : 's'} detectada
              {vistaPreguntas.length === 1 ? '' : 's'} · {preguntasSeleccionadas.length} seleccionada
              {preguntasSeleccionadas.length === 1 ? '' : 's'} para importar.
              {archivos.some((item) => item.formato === 'txt') &&
                ` ${vistaPreguntas.filter((pregunta) => pregunta.question_type === 'multiple_choice').length} de opción múltiple.`}
              {archivos.some((item) => item.formato === 'pdf') &&
                ` ${vistaPreguntas.filter((pregunta) => pregunta.question_type === 'multiple_choice').length} de opción múltiple.`}
              {importadas > 0 && ` Ya se importaron ${importadas}.`}
            </p>
            <p className="ayuda">
              Se guardarán en {destinoTexto}.
            </p>
            {archivos.some((item) => item.formato === 'txt' || item.formato === 'pdf') && (
              <p className="aviso aviso-neutro">
                Revisa que cada enunciado tenga sus alternativas y que la clave marque la respuesta
                correcta.
              </p>
            )}
            {vistaPreguntas.length > 0 && (
              <>
                <div className="fila importacion-acciones">
                  <button
                    type="button"
                    className="boton"
                    disabled={trabajando || preguntasSeleccionadas.length === 0 || (!bancoId && !nombreBanco?.trim())}
                    onClick={() => void confirmar()}
                  >
                    {trabajando
                      ? `Importando ${importadas + 1} de ${preguntasSeleccionadas.length}…`
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
            {vistaPreguntas.length > 0 && (
              <VistaPreviaImportacion
                seleccionable
                seleccionDeshabilitada={trabajando || importadas > 0}
                onSeleccionadasChange={setPreguntasSeleccionadas}
                grupos={archivos.filter((item) => item.formato !== 'qti').map((item) => ({
                  id: item.id,
                  nombre: item.nombre,
                  preguntas: vistaPreguntas.filter((_, indice) => origenesPreguntas[indice] === item.id)
                }))}
              />
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
