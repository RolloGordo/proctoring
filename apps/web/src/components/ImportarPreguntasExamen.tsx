import { useState } from 'react'
import { api, type NewQuestion } from '../lib/api'
import { dividirEnLotes, parsearArchivoPreguntas, parsearTextoPdf } from '../lib/importar-preguntas'
import { VistaPreviaImportacion } from './VistaPreviaImportacion'

const MAX_PREGUNTAS = 50
const MAX_ARCHIVO = 1_000_000
const MAX_PDF = 5_000_000
const MAX_ARCHIVOS = 10
const MAX_BYTES_TOTAL = 10_000_000

interface ArchivoPreparado {
  nombre: string
  tamano: number
  ultimaModificacion: number
  preguntas: NewQuestion[]
}

export function ImportarPreguntasExamen({
  sessionId,
  courseId,
  hayBancosAsociados = false,
  token,
  onClose,
  onImportadas
}: {
  sessionId: string
  courseId: string | null
  hayBancosAsociados?: boolean
  token?: string
  onClose: () => void
  onImportadas: (cantidad: number, guardadasEnBanco: boolean) => void | Promise<void>
}) {
  const [archivos, setArchivos] = useState<ArchivoPreparado[]>([])
  const [preguntas, setPreguntas] = useState<NewQuestion[]>([])
  const [importadas, setImportadas] = useState(0)
  const [destino, setDestino] = useState<'examen' | 'banco'>(hayBancosAsociados ? 'banco' : 'examen')
  const [nombreBanco, setNombreBanco] = useState('')
  const [bancoCreado, setBancoCreado] = useState<string>()
  const [preguntasGuardadasEnBanco, setPreguntasGuardadasEnBanco] = useState(false)
  const [trabajando, setTrabajando] = useState(false)
  const [error, setError] = useState<string>()

  async function seleccionar(lista?: FileList | null): Promise<void> {
    if (!lista?.length) return
    const yaAgregados = new Set(archivos.map((archivo) => `${archivo.nombre}:${archivo.tamano}:${archivo.ultimaModificacion}`))
    const seleccionados = [...lista].filter(
      (file) => !yaAgregados.has(`${file.name}:${file.size}:${file.lastModified}`)
    )
    if (seleccionados.length === 0) {
      setError('Esos archivos ya estan en la lista.')
      return
    }
    setError(undefined)
    setTrabajando(true)
    try {
      if (archivos.length + seleccionados.length > MAX_ARCHIVOS) {
        throw new Error(`Selecciona como maximo ${MAX_ARCHIVOS} archivos por importacion.`)
      }
      const bytes = archivos.reduce((suma, archivo) => suma + archivo.tamano, 0) +
        seleccionados.reduce((suma, file) => suma + file.size, 0)
      if (bytes > MAX_BYTES_TOTAL) throw new Error('Los archivos seleccionados superan los 10 MB en total.')

      const nuevos: ArchivoPreparado[] = []
      const erroresArchivo: string[] = []
      let totalPreguntas = preguntas.length
      for (const file of seleccionados) {
        try {
          const extension = file.name.split('.').pop()?.toLowerCase()
          if (!['csv', 'json', 'txt', 'pdf'].includes(extension ?? '')) {
            throw new Error('usa CSV, JSON, TXT o PDF. Para QTI XML, abre Bancos de preguntas.')
          }
          const limite = extension === 'pdf' ? MAX_PDF : MAX_ARCHIVO
          if (file.size > limite) throw new Error(`supera el limite de ${limite / 1_000_000} MB.`)

          let detectadas: NewQuestion[]
          if (extension === 'pdf') {
            const { extraerTextoPdf } = await import('../lib/extraer-pdf')
            const texto = await extraerTextoPdf(file)
            if (!texto) throw new Error('no se pudo extraer texto del PDF.')
            detectadas = parsearTextoPdf(texto)
          } else {
            detectadas = parsearArchivoPreguntas(await file.text(), extension as 'csv' | 'json' | 'txt')
          }
          if (detectadas.length === 0) throw new Error('no se encontraron preguntas importables.')
          if (totalPreguntas + detectadas.length > MAX_PREGUNTAS) {
            throw new Error(`supera el limite de ${MAX_PREGUNTAS} preguntas por importacion.`)
          }
          totalPreguntas += detectadas.length
          nuevos.push({
            nombre: file.name,
            tamano: file.size,
            ultimaModificacion: file.lastModified,
            preguntas: detectadas
          })
        } catch (fallo) {
          const detalle = fallo instanceof Error ? fallo.message : 'no se pudo leer el archivo.'
          erroresArchivo.push(`${file.name}: ${detalle}`)
        }
      }

      const combinados = [...archivos, ...nuevos]
      setArchivos(combinados)
      setPreguntas(combinados.flatMap((archivo) => archivo.preguntas))
      setError(erroresArchivo.length > 0 ? erroresArchivo.join(' | ') : undefined)
      setNombreBanco(
        combinados.length === 1
          ? combinados[0].nombre.replace(/\.[^.]+$/, '').slice(0, 120)
          : `Importacion de ${combinados.length} archivos`
      )
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudieron leer los archivos.')
    } finally {
      setTrabajando(false)
    }
  }

  async function importar(): Promise<void> {
    setError(undefined)
    setTrabajando(true)
    let guardadas = importadas
    let bancoId = bancoCreado
    try {
      const lotes = dividirEnLotes(preguntas, MAX_PREGUNTAS)
      if (destino === 'banco') {
        if (!nombreBanco.trim()) throw new Error('Escribe el nombre del banco que guardara estas preguntas.')
        if (!bancoId) {
          const banco = await api.createBank(
            { name: nombreBanco.trim(), course_id: courseId, description: `Importado desde ${archivos.length} archivo(s)` },
            token
          )
          bancoId = banco.id
          setBancoCreado(banco.id)
        }
        if (!preguntasGuardadasEnBanco) {
          for (const lote of lotes) {
            await api.addBankQuestions(bancoId, lote, token)
            guardadas += lote.length
            setImportadas(guardadas)
          }
          setPreguntasGuardadasEnBanco(true)
        }
        await api.attachBank(sessionId, bancoId, token)
      } else {
        while (guardadas < preguntas.length) {
          const lote = lotes[Math.floor(guardadas / MAX_PREGUNTAS)]
          if (!lote) throw new Error('No se pudo preparar el siguiente grupo de preguntas.')
          await api.addQuestions(sessionId, lote, token)
          guardadas += lote.length
          setImportadas(guardadas)
        }
      }
      await onImportadas(guardadas, destino === 'banco')
      onClose()
    } catch (fallo) {
      setImportadas(guardadas)
      setError(
        guardadas > 0
          ? `Se agregaron ${guardadas} de ${preguntas.length}. Puedes continuar sin duplicar las ya guardadas. ${fallo instanceof Error ? fallo.message : ''}`
          : fallo instanceof Error
            ? fallo.message
            : 'No se pudieron agregar las preguntas.'
      )
    } finally {
      setTrabajando(false)
    }
  }

  function cerrar(): void {
    if (importadas > 0 && importadas < preguntas.length) {
      if (!confirm(`Ya se agregaron ${importadas} preguntas. Si cierras, las demás no se importarán. ¿Cerrar?`)) return
    }
    onClose()
  }

  return (
    <div className="importacion-examen-modal-contenido">
      <p className="ayuda">Agrega preguntas desde CSV, JSON, TXT o PDF con texto seleccionable. Para importar QTI XML, usa primero un banco.</p>
      <label className="campo">
        <span>{archivos.length > 0 ? `Agregar mas archivos (ya hay ${archivos.length})` : 'Seleccionar archivos de preguntas'}</span>
        <input
          type="file"
          accept=".csv,.json,.txt,.pdf,text/csv,application/json,text/plain,application/pdf"
          disabled={trabajando || importadas > 0}
          multiple
          onChange={(evento) => {
            void seleccionar(evento.currentTarget.files)
            evento.currentTarget.value = ''
          }}
        />
        <small className="ayuda">
          Puedes seleccionar varios a la vez o volver a abrir el selector para agregarlos a la lista.
        </small>
      </label>
      {error && <p className="aviso" role="alert">{error}</p>}
      {trabajando && <p className="ayuda" role="status">Procesando…</p>}
      {archivos.length > 0 && preguntas.length > 0 && (
        <div className="importacion-archivos-resumen">
          <strong>{archivos.length} archivo(s) · {preguntas.length} preguntas listas</strong>
          <VistaPreviaImportacion
            grupos={archivos.map((archivoPreparado) => ({
              id: `${archivoPreparado.nombre}:${archivoPreparado.tamano}:${archivoPreparado.ultimaModificacion}`,
              nombre: archivoPreparado.nombre,
              preguntas: archivoPreparado.preguntas
            }))}
          />
        </div>
      )}
      {preguntas.length > 0 && (
        <fieldset className="importacion-destino" disabled={trabajando || importadas > 0}>
          <legend>Guardar preguntas en</legend>
          <label>
            <input type="radio" name="destino-importacion-examen" checked={destino === 'examen'} disabled={hayBancosAsociados} onChange={() => setDestino('examen')} />
            <span><strong>Solo este examen</strong><small>{hayBancosAsociados ? 'No disponible mientras se usan bancos asociados.' : 'No apareceran en Mis bancos.'}</small></span>
          </label>
          <label>
            <input type="radio" name="destino-importacion-examen" checked={destino === 'banco'} onChange={() => setDestino('banco')} />
            <span><strong>Guardar tambien en un banco</strong><small>Se asociara a este examen y quedara disponible para reutilizar.</small></span>
          </label>
          {destino === 'banco' && (
            <label className="campo">
              <span>Nombre del banco reutilizable</span>
              <input value={nombreBanco} onChange={(evento) => setNombreBanco(evento.target.value)} maxLength={120} required />
            </label>
          )}
        </fieldset>
      )}
      <div className="fila importacion-acciones">
        <button
          type="button"
          className="boton"
          disabled={trabajando || preguntas.length === 0}
          onClick={() => void importar()}
        >
          {trabajando
            ? `Importando ${importadas + 1} de ${preguntas.length}…`
            : importadas > 0
              ? 'Continuar importación'
              : destino === 'banco'
                ? `Guardar en banco y añadir ${preguntas.length} al examen`
                : `Agregar ${preguntas.length || ''} preguntas al examen`}
        </button>
        <button type="button" className="boton boton-secundario" disabled={trabajando} onClick={cerrar}>
          Cancelar
        </button>
      </div>
    </div>
  )
}
