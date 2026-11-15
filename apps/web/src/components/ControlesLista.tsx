/** Buscador por correo y botón «Ver más» de las listas que crecen con el examen. */
import { useState, type ReactNode } from 'react'
import { PASO_LISTA } from '../lib/lista-acotada'

export function FiltroCorreo({
  valor,
  onCambio,
  etiqueta = 'Filtrar por correo o nombre'
}: {
  valor: string
  onCambio: (valor: string) => void
  etiqueta?: string
}) {
  return (
    <input
      type="search"
      className="filtro-lista"
      placeholder="Buscar por correo…"
      aria-label={etiqueta}
      value={valor}
      onChange={(evento) => onCambio(evento.target.value)}
    />
  )
}

export function VerMas({
  restantes,
  onClick,
  paso = PASO_LISTA
}: {
  restantes: number
  onClick: () => void
  paso?: number
}) {
  if (restantes <= 0) return null
  return (
    <button type="button" className="boton boton-secundario ver-mas" onClick={onClick}>
      Ver {Math.min(paso, restantes)} más <span className="tenue">({restantes} ocultas)</span>
    </button>
  )
}

/** «Sin coincidencias» cuando el filtro no encuentra a nadie. */
export function SinCoincidencias({ filtro }: { filtro: string }) {
  return <p className="tenue">Nadie coincide con «{filtro}».</p>
}

/**
 * Muestra seis elementos y un «Ver más» que añade otros seis. Para listas que
 * se pintan después de un `return` temprano, donde no cabe un hook.
 */
export function PorPasos<T>({
  elementos,
  children
}: {
  elementos: readonly T[]
  children: (visibles: readonly T[]) => ReactNode
}) {
  const [limite, setLimite] = useState(PASO_LISTA)
  return (
    <>
      {children(elementos.slice(0, limite))}
      <VerMas
        restantes={elementos.length - limite}
        onClick={() => setLimite((actual) => actual + PASO_LISTA)}
      />
    </>
  )
}
