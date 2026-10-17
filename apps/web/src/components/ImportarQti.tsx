import { useRef, useState } from 'react'
import { api, type QtiImportResult } from '../lib/api'
import { useAuth } from '../lib/auth-context'

/**
 * Subir un archivo QTI a un banco.
 *
 * Primero se prueba sin guardar y se enseña lo que entraría; solo después, con
 * el resultado a la vista, se confirma. Importar cuarenta preguntas a ciegas y
 * descubrir el problema en el banco es peor que mirarlo antes.
 */
export function ImportarQti({ bancoId, onImportado }: { bancoId: string; onImportado: () => void }) {
  const { token } = useAuth()
  const entrada = useRef<HTMLInputElement>(null)
  const [archivo, setArchivo] = useState<{ nombre: string; xml: string }>()
  const [vistaPrevia, setVistaPrevia] = useState<QtiImportResult>()
  const [error, setError] = useState<string>()
  const [trabajando, setTrabajando] = useState(false)

  function limpiar(): void {
    setArchivo(undefined)
    setVistaPrevia(undefined)
    setError(undefined)
    if (entrada.current) entrada.current.value = ''
  }

  async function elegir(fichero: File | undefined): Promise<void> {
    if (!fichero) return
    setError(undefined)
    setVistaPrevia(undefined)
    setTrabajando(true)
    try {
      const xml = await fichero.text()
      setArchivo({ nombre: fichero.name, xml })
      setVistaPrevia(await api.importQti(bancoId, xml, { token, dryRun: true }))
    } catch (fallo) {
      setArchivo(undefined)
      setError(fallo instanceof Error ? fallo.message : 'No se pudo leer el archivo')
    } finally {
      setTrabajando(false)
    }
  }

  async function confirmar(): Promise<void> {
    if (!archivo) return
    setError(undefined)
    setTrabajando(true)
    try {
      const hecho = await api.importQti(bancoId, archivo.xml, { token })
      limpiar()
      onImportado()
      setVistaPrevia(hecho)
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo importar')
    } finally {
      setTrabajando(false)
    }
  }

  const cuantas = vistaPrevia?.imported_count ?? 0
  const porEntrar = vistaPrevia?.dry_run ? (vistaPrevia.warnings.length || cuantas ? 1 : 0) : 0

  return (
    <div className="campo">
      <span>Importar de un archivo QTI</span>
      <p className="ayuda" style={{ marginBottom: 'var(--e2)' }}>
        Sube el <code>.xml</code> que exportó tu plataforma. Te enseño lo que entraría antes de
        guardarlo.
      </p>

      <input
        ref={entrada}
        type="file"
        accept=".xml,application/xml,text/xml"
        disabled={trabajando}
        onChange={(e) => void elegir(e.target.files?.[0])}
        aria-label="Archivo QTI"
      />

      {error && <p className="aviso">{error}</p>}

      {vistaPrevia && (
        <div className="tarjeta" style={{ marginTop: 'var(--e3)' }}>
          <div className="tarjeta-cuerpo">
            {vistaPrevia.dry_run ? (
              <>
                <h4>
                  {porEntrar === 0 && vistaPrevia.warnings.length === 0
                    ? 'Nada que importar'
                    : 'Esto es lo que entraría'}
                </h4>
                <p className="ayuda">
                  {archivo?.nombre}
                  {vistaPrevia.skipped.length > 0 &&
                    ` · ${vistaPrevia.skipped.length} se quedan fuera`}
                </p>
              </>
            ) : (
              <h4>
                {cuantas} pregunta{cuantas === 1 ? '' : 's'} importada
                {cuantas === 1 ? '' : 's'}
              </h4>
            )}

            {vistaPrevia.warnings.length > 0 && (
              <>
                <p className="ayuda" style={{ marginTop: 'var(--e3)' }}>
                  <strong>Revisa esto antes de usarlas:</strong>
                </p>
                <ul className="lista-modulos">
                  {vistaPrevia.warnings.map((aviso) => (
                    <li key={aviso.item_id}>
                      <strong>{aviso.item_id}</strong> · {aviso.reason}
                    </li>
                  ))}
                </ul>
              </>
            )}

            {vistaPrevia.skipped.length > 0 && (
              <>
                <p className="ayuda" style={{ marginTop: 'var(--e3)' }}>
                  <strong>No se pueden importar</strong> sin cambiar cómo se califican, así que se
                  quedan fuera. Las demás sí entran:
                </p>
                <ul className="lista-modulos">
                  {vistaPrevia.skipped.map((descarte) => (
                    <li key={descarte.item_id}>
                      <strong>{descarte.item_id}</strong> · {descarte.reason}
                    </li>
                  ))}
                </ul>
              </>
            )}

            {vistaPrevia.dry_run && (
              <div className="fila" style={{ marginTop: 'var(--e3)' }}>
                <button
                  type="button"
                  className="boton"
                  disabled={trabajando}
                  onClick={() => void confirmar()}
                >
                  {trabajando ? 'Importando…' : 'Importar al banco'}
                </button>
                <button type="button" className="boton boton-secundario" onClick={limpiar}>
                  Cancelar
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
