import { useMemo, useState } from 'react'

/** Cuántos elementos se ven al principio y cuántos más añade cada «Ver más». */
export const PASO_LISTA = 6

/** Normaliza un correo o nombre para compararlo sin mayúsculas ni tildes. */
function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim()
}

/**
 * Filtra por lo que el docente escribió (correo o nombre) y corta a los
 * `limite` primeros. Pura, para probarla sin React.
 */
export function acotarLista<T>(
  elementos: readonly T[],
  textoDe: (elemento: T) => string | null | undefined,
  filtro: string,
  limite: number
): { visibles: T[]; coincidencias: number } {
  const buscado = normalizar(filtro)
  const filtrados = buscado
    ? elementos.filter((elemento) => normalizar(textoDe(elemento) ?? '').includes(buscado))
    : [...elementos]
  return { visibles: filtrados.slice(0, limite), coincidencias: filtrados.length }
}

/**
 * Una lista que crece con el examen (alertas, señales, entregas): muestra las
 * primeras seis, «Ver más» añade otras seis y un filtro busca por correo.
 * Cambiar el filtro vuelve a las seis primeras.
 */
export function useListaAcotada<T>(
  elementos: readonly T[],
  textoDe: (elemento: T) => string | null | undefined,
  paso = PASO_LISTA
) {
  const [filtro, setFiltro] = useState('')
  const [limite, setLimite] = useState(paso)
  const { visibles, coincidencias } = useMemo(
    () => acotarLista(elementos, textoDe, filtro, limite),
    // textoDe suele ser una función en línea: el resultado depende de los datos.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [elementos, filtro, limite]
  )
  return {
    visibles,
    coincidencias,
    total: elementos.length,
    restantes: Math.max(0, coincidencias - visibles.length),
    filtro,
    setFiltro: (valor: string) => {
      setFiltro(valor)
      setLimite(paso)
    },
    verMas: () => setLimite((actual) => actual + paso)
  }
}
