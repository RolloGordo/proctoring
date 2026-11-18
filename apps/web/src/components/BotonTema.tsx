import { useEffect, useState } from 'react'
import { elegirTema, EVENTO_TEMA, temaVigente, type Tema } from '../lib/tema'

/**
 * Cambia entre modo claro y oscuro. Dice a qué modo lleva, no en cuál está:
 * «Modo claro» en oscuro y al revés, que es lo que la persona busca.
 */
export function BotonTema({ className = 'boton-tema' }: { className?: string }) {
  const [tema, setTema] = useState<Tema>(() => temaVigente())

  useEffect(() => {
    const alCambiar = (e: Event) => setTema((e as CustomEvent<Tema>).detail)
    window.addEventListener(EVENTO_TEMA, alCambiar)
    return () => window.removeEventListener(EVENTO_TEMA, alCambiar)
  }, [])

  const destino: Tema = tema === 'oscuro' ? 'claro' : 'oscuro'
  return (
    <button
      type="button"
      className={className}
      aria-label={destino === 'claro' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
      onClick={() => elegirTema(destino)}
    >
      <svg className="boton-tema-icono" viewBox="0 0 20 20" width="16" height="16" aria-hidden="true">
        {destino === 'claro' ? (
          <g fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
            <circle cx="10" cy="10" r="3.6" />
            <path d="M10 1.8v2M10 16.2v2M1.8 10h2M16.2 10h2M4.2 4.2l1.4 1.4M14.4 14.4l1.4 1.4M4.2 15.8l1.4-1.4M14.4 5.6l1.4-1.4" />
          </g>
        ) : (
          <path fill="currentColor" d="M15.8 12.6A7 7 0 0 1 7.4 4.2a6.6 6.6 0 1 0 8.4 8.4Z" />
        )}
      </svg>
      <span>{destino === 'claro' ? 'Modo claro' : 'Modo oscuro'}</span>
    </button>
  )
}
