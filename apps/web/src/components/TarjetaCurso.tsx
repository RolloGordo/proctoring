import { useState, type CSSProperties, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { Course } from '../lib/api'
import { siglaDeCurso, tonoDeCurso } from '../lib/curso'

type Tono = CSSProperties & Record<'--tono', number>

/** Lo que necesita una portada: la ve igual el docente que el estudiante. */
export interface CursoConPortada {
  id: string
  name: string
  cover_url: string | null
}

/**
 * La portada de un curso: su imagen, o la de reserva si no tiene o si la URL
 * firmada ya caducó. La imagen es decorativa: el nombre del curso va siempre
 * en texto al lado, así que no se anuncia al lector de pantalla.
 */
export function PortadaCurso({
  curso,
  className = ''
}: {
  curso: CursoConPortada
  className?: string
}) {
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

/**
 * Un curso en la rejilla: portada, nombre y una línea de datos. Toda la tarjeta
 * lleva a `destino`. Cada rol decide qué dice esa línea: al docente le sirve
 * cuántos estudiantes tiene; al estudiante, cuándo es su próximo examen.
 */
export function TarjetaCurso({
  curso,
  destino,
  datos
}: {
  curso: CursoConPortada
  destino: string
  datos: ReactNode
}) {
  return (
    <article className="tarjeta-curso">
      <PortadaCurso curso={curso} />
      <div className="tarjeta-curso-cuerpo">
        <h3 className="tarjeta-curso-nombre">
          {/* El enlace se estira sobre toda la tarjeta (::after): un solo destino
           * de tabulación por curso, no tres. */}
          <Link to={destino} className="tarjeta-curso-enlace" title={curso.name}>
            {curso.name}
          </Link>
        </h3>
        <p className="tarjeta-curso-datos">{datos}</p>
      </div>
    </article>
  )
}

/** La rejilla: tantas columnas como quepan, de 240 px como mínimo. */
export function RejillaTarjetas({ children }: { children: ReactNode }) {
  return <ul className="rejilla-cursos">{children}</ul>
}

/** Los cursos del docente: cada uno con su sección y cuántos estudiantes tiene. */
export function RejillaCursos({ cursos }: { cursos: Course[] }) {
  return (
    <RejillaTarjetas>
      {cursos.map((curso) => (
        <li key={curso.id}>
          <TarjetaCurso
            curso={curso}
            destino={`/cursos/${curso.id}`}
            datos={
              <>
                {curso.section ? `Sección ${curso.section} · ` : ''}
                {curso.student_count} {curso.student_count === 1 ? 'estudiante' : 'estudiantes'}
              </>
            }
          />
        </li>
      ))}
    </RejillaTarjetas>
  )
}
