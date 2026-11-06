import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ImportarPreguntas } from './ImportarPreguntas'
import { api, type QuestionBank } from '../lib/api'
import { useAuth } from '../lib/auth-context'

export function CrearBancoCurso({
  courseId,
  courseName,
  onClose,
  onCreated
}: {
  courseId: string
  courseName: string
  onClose: () => void
  onCreated: (bank: QuestionBank) => void
}) {
  const { token } = useAuth()
  const [nombre, setNombre] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [bancoParcial, setBancoParcial] = useState(false)
  const [trabajando, setTrabajando] = useState(false)

  const cerrar = useCallback((): boolean => {
    if (trabajando) return false
    if (bancoParcial && !confirm('El banco creado puede quedar vacío o conservar las preguntas importadas hasta ahora. ¿Cerrar el panel?')) return false
    onClose()
    return true
  }, [trabajando, bancoParcial, onClose])

  useEffect(() => {
    const overflowAnterior = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    function tecla(evento: KeyboardEvent): void {
      if (evento.key === 'Escape') cerrar()
    }
    window.addEventListener('keydown', tecla)
    return () => {
      document.body.style.overflow = overflowAnterior
      window.removeEventListener('keydown', tecla)
    }
  }, [cerrar])

  async function crearBanco(): Promise<QuestionBank> {
    if (!nombre.trim()) throw new Error('Escribe el nombre del banco antes de importar.')
    return api.createBank(
      {
        name: nombre.trim(),
        course_id: courseId,
        description: descripcion.trim() || null
      },
      token
    )
  }

  function alImportar(bankId: string, cantidad: number, completada: boolean): void {
    if (completada) {
      setBancoParcial(false)
      onCreated({
        id: bankId,
        name: nombre.trim(),
        course_id: courseId,
        description: descripcion.trim() || null,
        created_at: new Date().toISOString(),
        question_count: cantidad,
        attached_to_exam: false
      })
      onClose()
    } else if (cantidad > 0) {
      setBancoParcial(true)
    }
  }

  return (
    <>
      <button
        type="button"
        className="drawer-fondo"
        aria-label="Cerrar importación de preguntas"
        onClick={cerrar}
      />
      <section
        className="drawer-examen drawer-banco-curso"
        role="dialog"
        aria-modal="true"
        aria-labelledby="titulo-drawer-banco"
      >
        <header className="encabezado-pagina">
          <div>
            <h2 id="titulo-drawer-banco">Importar banco de preguntas</h2>
            <p className="subtitulo">El banco nuevo se asociará al curso {courseName}.</p>
          </div>
          <button type="button" className="boton boton-secundario" onClick={cerrar} disabled={trabajando}>
            Cerrar
          </button>
        </header>

        <label className="campo">
          <span>Nombre del banco</span>
          <input
            value={nombre}
            onChange={(evento) => setNombre(evento.target.value)}
            maxLength={120}
            placeholder="Ej. Unidad 1: fundamentos"
            required
          />
        </label>
        <label className="campo">
          <span>Descripción (opcional)</span>
          <textarea
            value={descripcion}
            onChange={(evento) => setDescripcion(evento.target.value)}
            maxLength={1000}
            rows={2}
          />
        </label>

        <ImportarPreguntas
          nombreBanco={nombre}
          crearBanco={crearBanco}
          onImportado={alImportar}
          onTrabajandoChange={setTrabajando}
          onBancoCreado={() => setBancoParcial(true)}
        />
        <p className="ayuda">
          ¿Quieres crear el banco vacío o ver los que ya tienes?{' '}
          <Link
            to={`/bancos?curso=${encodeURIComponent(courseId)}`}
            onClick={(evento) => {
              if (!cerrar()) evento.preventDefault()
            }}
          >
            Abrir Bancos de preguntas
          </Link>.
        </p>
      </section>
    </>
  )
}
