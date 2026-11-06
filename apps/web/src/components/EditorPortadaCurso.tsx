import { useRef, useState, type ChangeEvent } from 'react'
import { api, type Course } from '../lib/api'
import { FORMATOS_PORTADA, prepararPortada, subirPortada } from '../lib/portada'
import { PortadaCurso } from './TarjetaCurso'

/**
 * La portada grande del curso, con lo necesario para cambiarla o quitarla.
 *
 * Elegir la imagen la sube en el acto: no hay un «Guardar» aparte que olvidar.
 * Mientras se prepara y se sube, los botones dicen qué está pasando.
 */
export function EditorPortadaCurso({
  curso,
  token,
  onCambio
}: {
  curso: Course
  token?: string
  onCambio: (curso: Course) => void
}) {
  const entrada = useRef<HTMLInputElement>(null)
  const [estado, setEstado] = useState<'quieto' | 'subiendo' | 'quitando'>('quieto')
  const [error, setError] = useState<string>()
  const ocupado = estado !== 'quieto'

  async function elegir(evento: ChangeEvent<HTMLInputElement>): Promise<void> {
    const archivo = evento.target.files?.[0]
    // Vaciar el campo deja volver a elegir el mismo archivo tras un error.
    evento.target.value = ''
    if (!archivo) return
    setError(undefined)
    setEstado('subiendo')
    try {
      const imagen = await prepararPortada(archivo)
      onCambio(await subirPortada(curso.id, imagen, token))
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo cambiar la portada.')
    } finally {
      setEstado('quieto')
    }
  }

  async function quitar(): Promise<void> {
    setError(undefined)
    setEstado('quitando')
    try {
      onCambio(await api.removeCourseCover(curso.id, token))
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo quitar la portada.')
    } finally {
      setEstado('quieto')
    }
  }

  return (
    <div className="portada-editor">
      <div className="portada-editor-marco">
        <PortadaCurso curso={curso} className="portada-curso-grande" />
        <div className="portada-editor-acciones">
          <input
            ref={entrada}
            type="file"
            accept={FORMATOS_PORTADA.join(',')}
            onChange={(evento) => void elegir(evento)}
            hidden
          />
          <button
            type="button"
            className="boton boton-secundario boton-chico"
            disabled={ocupado}
            onClick={() => entrada.current?.click()}
          >
            {estado === 'subiendo'
              ? 'Subiendo portada…'
              : curso.cover_url
                ? 'Cambiar portada'
                : 'Añadir portada'}
          </button>
          {curso.cover_url && (
            <button
              type="button"
              className="boton boton-secundario boton-chico"
              disabled={ocupado}
              onClick={() => void quitar()}
            >
              {estado === 'quitando' ? 'Quitando…' : 'Quitar'}
            </button>
          )}
        </div>
      </div>
      {error && (
        <p className="aviso portada-editor-error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
