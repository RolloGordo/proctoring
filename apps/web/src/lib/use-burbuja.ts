import { type RefObject, useEffect } from 'react'
import { montarBurbuja } from './burbuja'
import { RESPALDOS } from './fotos-portada'

/**
 * Arranca la burbuja de WebGL sobre las anclas de la página.
 *
 * Con el movimiento reducido arranca quieta: una burbuja de cristal en cada
 * ancla, sin viajar ni respirar, que es lo que esa preferencia pide no ver.
 * Windows la activa al apagar los «efectos de animación», y muchos equipos la
 * tienen así sin saberlo. Sin WebGL se queda la de CSS.
 *
 * Con `seguirCursor` es la del acceso: vacía y detrás del cursor dentro de
 * `raiz`. Lo que tiene que esquivar se marca con `data-burbuja-evita` y el
 * texto que se ve a través de ella con `data-burbuja-refracta`.
 */
export function useBurbuja(
  raiz: RefObject<HTMLDivElement | null>,
  lienzo: RefObject<HTMLCanvasElement | null>,
  { seguirCursor = false }: { seguirCursor?: boolean } = {}
) {
  useEffect(() => {
    const nodo = raiz.current
    const canvas = lienzo.current
    if (!nodo || !canvas) return
    const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const anclas = Array.from(nodo.querySelectorAll<HTMLElement>('[data-burbuja]'))
    const evita = nodo.querySelector<HTMLElement>('[data-burbuja-evita]')
    // Además del texto marcado, la cabecera, el aviso y el pie: la burbuja pasa
    // por encima de ellos, como la de ThoughtLab, y no por detrás, donde su
    // fondo la cortaba en recto.
    const capa = nodo.closest('.publica')
    const bordes = capa
      ? Array.from(
          capa.querySelectorAll<HTMLElement>(
            ':scope > .cabecera, :scope > .aviso-almacenamiento, :scope > .pie-publico'
          )
        )
      : []
    const seguir =
      seguirCursor && evita
        ? {
            evita,
            limite: nodo,
            refracta: [
              ...Array.from(nodo.querySelectorAll<HTMLElement>('[data-burbuja-refracta]')),
              ...bordes
            ]
          }
        : undefined
    const desmontar = montarBurbuja(
      canvas,
      anclas,
      (src) => RESPALDOS.get(src),
      () => nodo.classList.remove('pub-con-burbuja'),
      { sinMovimiento, seguir }
    )
    if (!desmontar) return
    nodo.classList.add('pub-con-burbuja')

    return () => {
      desmontar()
      nodo.classList.remove('pub-con-burbuja')
    }
  }, [raiz, lienzo, seguirCursor])
}
