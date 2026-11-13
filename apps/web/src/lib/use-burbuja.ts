import { type RefObject, useEffect } from 'react'
import { montarBurbuja } from './burbuja'
import { RESPALDOS } from './fotos-portada'

/**
 * Arranca la burbuja de WebGL sobre las anclas de `raiz` (`data-burbuja`).
 *
 * Con el movimiento reducido arranca quieta: una burbuja de cristal en cada
 * ancla, sin viajar ni respirar, que es lo que esa preferencia pide no ver.
 * Windows la activa al apagar los «efectos de animación», y muchos equipos la
 * tienen así sin saberlo. Sin WebGL se queda la de CSS.
 *
 * Un ancla con `data-burbuja-sigue` va vacía y sigue al cursor, si hay ratón.
 * Entonces importan dos marcas más dentro de `raiz`: `data-burbuja-evita` (lo
 * que no pisa; con el valor `lado`, tampoco pasa de su borde izquierdo) y
 * `data-burbuja-refracta` (el texto que se ve a través de ella). A ese texto
 * se suman el aviso y el pie, y por encima de ellos pasa cualquier burbuja.
 * La cabecera no: es el techo, la burbuja no sube a ella y sus botones se
 * quedan como son.
 */
export function useBurbuja(
  raiz: RefObject<HTMLDivElement | null>,
  lienzo: RefObject<HTMLCanvasElement | null>
) {
  useEffect(() => {
    const nodo = raiz.current
    const canvas = lienzo.current
    if (!nodo || !canvas) return
    const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const conCursor = window.matchMedia('(hover: hover) and (pointer: fine)').matches
    const anclas = Array.from(nodo.querySelectorAll<HTMLElement>('[data-burbuja]'))
    const evita = Array.from(nodo.querySelectorAll<HTMLElement>('[data-burbuja-evita]')).map(
      (el) => ({ nodo: el, lado: el.dataset.burbujaEvita === 'lado' })
    )
    const capa = nodo.closest('.publica')
    const bordes = capa
      ? Array.from(
          capa.querySelectorAll<HTMLElement>(
            ':scope > .aviso-almacenamiento, :scope > .pie-publico'
          )
        )
      : []
    const refracta = [
      ...Array.from(nodo.querySelectorAll<HTMLElement>('[data-burbuja-refracta]')),
      ...bordes
    ]

    const desmontar = montarBurbuja(
      canvas,
      anclas,
      (src) => RESPALDOS.get(src),
      () => nodo.classList.remove('pub-con-burbuja'),
      {
        sinMovimiento,
        conCursor,
        evita,
        refracta,
        bordes,
        techo: capa?.querySelector<HTMLElement>(':scope > .cabecera') ?? null
      }
    )
    if (!desmontar) return
    nodo.classList.add('pub-con-burbuja')
    // La que sigue al cursor cambia de sitio en la portada (sobre el titular):
    // sin ratón, se queda donde estaba, con sus fotos.
    if (conCursor) nodo.classList.add('pub-con-cursor')

    return () => {
      desmontar()
      nodo.classList.remove('pub-con-burbuja', 'pub-con-cursor')
    }
  }, [raiz, lienzo])
}
