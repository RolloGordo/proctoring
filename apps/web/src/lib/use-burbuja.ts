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
    const anclas = Array.from(nodo.querySelectorAll<HTMLElement>('[data-burbuja]'))
    const desmontar = montarBurbuja(
      canvas,
      anclas,
      (src) => RESPALDOS.get(src),
      () => nodo.classList.remove('pub-con-burbuja'),
      sinMovimiento
    )
    if (!desmontar) return
    nodo.classList.add('pub-con-burbuja')

    return () => {
      desmontar()
      nodo.classList.remove('pub-con-burbuja')
    }
  }, [raiz, lienzo])
}
