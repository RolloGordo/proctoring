import { useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import type { Course } from '../lib/api'
import { siglaDeCurso, tonoDeCurso } from '../lib/curso'

type Tono = CSSProperties & Record<'--tono', number>

/**
 * La portada de un curso: su imagen, o la de reserva si no tiene o si la URL
 * firmada ya caducó. La imagen es decorativa: el nombre del curso va siempre
 * en texto al lado, así que no se anuncia al lector de pantalla.
 */
export function PortadaCurso({ curso, className = '' }: { curso: Course; className?: string }) {
  // Guarda la URL que falló, no un sí/no: si llega otra (una portada nueva o
  // una firma renovada) se vuelve a intentar sin un efecto que lo resetee.
  const [urlRota, setUrlRota] = useState<string | null>(null)
  const url = curso.cover_url && curso.cover_url !== urlRota ? curso.cover_url : null

  return (
    <div
      className={`portada-curso ${url ? '' : 'portada-curso-reserva'} ${className}`}
      style={{ '--tono': tonoDeCurso(curso.id) } as Tono}
      aria-hidden
    >
      {url ? (
        <img src={url} alt="" loading="lazy" decoding="async" onError={() => setUrlRota(url)} />
      ) : (
        <span className="portada-curso-sigla">{siglaDeCurso(curso.name)}</span>
      )}
    </div>
  )
}

/** Un curso en la rejilla: portada, nombre y quiénes están. Toda la tarjeta lleva al curso. */
export function TarjetaCurso({ curso }: { curso: Course }) {
  const estudiantes = `${curso.student_count} ${curso.student_count === 1 ? 'estudiante' : 'estudiantes'}`
  return (
    <article className="tarjeta-curso">
      <PortadaCurso curso={curso} />
      <div className="tarjeta-curso-cuerpo">
        <h3 className="tarjeta-curso-nombre">
          {/* El enlace se estira sobre toda la tarjeta (::after): un solo destino
           * de tabulación por curso, no tres. */}
          <Link to={`/cursos/${curso.id}`} className="tarjeta-curso-enlace" title={curso.name}>
            {curso.name}
          </Link>
        </h3>
        <p className="tarjeta-curso-datos">
          {curso.section ? `Sección ${curso.section} · ` : ''}
          {estudiantes}
        </p>
      </div>
    </article>
  )
}

/** La rejilla de cursos: tantas columnas como quepan, de 240 px como mínimo. */
export function RejillaCursos({ cursos }: { cursos: Course[] }) {
  return (
    <ul className="rejilla-cursos">
      {cursos.map((curso) => (
        <li key={curso.id}>
          <TarjetaCurso curso={curso} />
        </li>
      ))}
    </ul>
  )
}
