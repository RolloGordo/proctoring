/** La identidad visual de un curso sin portada: su tono y su sigla. */

/**
 * Tonos de la portada de reserva. Apagados a propósito: sobre el lienzo casi
 * negro se distinguen entre sí sin competir con el ámbar, que se guarda para
 * la acción principal. Por eso no hay ningún amarillo.
 */
const TONOS = [212, 168, 268, 18, 336, 96] as const

/** El mismo tono para el mismo curso en cada visita: sale de su id, no del azar. */
export function tonoDeCurso(id: string): number {
  let suma = 0
  for (const letra of id) suma = (suma * 31 + letra.charCodeAt(0)) >>> 0
  return TONOS[suma % TONOS.length]
}

/** «Taller Integrador 1» → «TI1». Sin artículos ni preposiciones, como una sigla. */
export function siglaDeCurso(nombre: string): string {
  const vacias = new Set(['de', 'del', 'la', 'las', 'el', 'los', 'y', 'e', 'en', 'a', 'para'])
  const palabras = nombre.split(/\s+/).filter((p) => p && !vacias.has(p.toLowerCase()))
  const sigla = palabras
    .map((p) => (/^\d+$/.test(p) ? p : p[0]))
    .join('')
    .toUpperCase()
  return sigla.slice(0, 4) || '·'
}
