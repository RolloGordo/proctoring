/**
 * Modo claro u oscuro (pedido del profesor, 18/11/2026).
 *
 * El tema vive en `data-tema` de <html> y las hojas de estilo solo cambian los
 * valores de sus variables (`panel-oscuro.css` y `publica.css`): ninguna
 * pantalla sabe de temas.
 *
 * Mientras la persona no elija, se sigue el tema del sistema operativo, y si
 * lo cambia con la página abierta, la página lo sigue. Cuando elige, se
 * recuerda en este navegador. Se guarda solo esa palabra: es una preferencia
 * de pantalla, no un dato personal.
 */

export type Tema = 'claro' | 'oscuro'

export const CLAVE_TEMA = 'proctoring:tema'
/** Lo emite `elegirTema` para que todos los botones de la página se enteren. */
export const EVENTO_TEMA = 'proctoring:tema'

const CONSULTA_CLARO = '(prefers-color-scheme: light)'

type Almacen = Pick<Storage, 'getItem' | 'setItem'>

function almacen(): Almacen | null {
  try {
    return globalThis.localStorage ?? null
  } catch {
    // Bloqueado (modo privado estricto, cookies de terceros apagadas).
    return null
  }
}

/** Lo que la persona eligió, o `null` si nunca eligió (o no se puede leer). */
export function temaElegido(guardado: Almacen | null = almacen()): Tema | null {
  try {
    const valor = guardado?.getItem(CLAVE_TEMA)
    return valor === 'claro' || valor === 'oscuro' ? valor : null
  } catch {
    return null
  }
}

/** El del sistema. Sin `matchMedia` (pruebas, navegadores raros), oscuro: el de siempre. */
export function temaDelSistema(media: ((q: string) => MediaQueryList) | undefined = globalThis.matchMedia): Tema {
  try {
    return media?.(CONSULTA_CLARO).matches ? 'claro' : 'oscuro'
  } catch {
    return 'oscuro'
  }
}

export function temaVigente(guardado: Almacen | null = almacen(), media = globalThis.matchMedia): Tema {
  return temaElegido(guardado) ?? temaDelSistema(media)
}

export function aplicarTema(tema: Tema, raiz: HTMLElement | undefined = globalThis.document?.documentElement): void {
  if (raiz) raiz.dataset['tema'] = tema
}

export function elegirTema(tema: Tema, guardado: Almacen | null = almacen()): void {
  try {
    guardado?.setItem(CLAVE_TEMA, tema)
  } catch {
    // Sin almacenamiento se aplica igual; solo no se recordará.
  }
  aplicarTema(tema)
  globalThis.dispatchEvent?.(new CustomEvent<Tema>(EVENTO_TEMA, { detail: tema }))
}

/**
 * Se llama una vez, antes de pintar React, para que la primera pantalla ya
 * salga en su tema. Sigue al sistema y a otras pestañas del mismo navegador.
 */
export function iniciarTema(): void {
  aplicarTema(temaVigente())
  try {
    globalThis.matchMedia?.(CONSULTA_CLARO).addEventListener('change', () => {
      if (temaElegido() === null) {
        aplicarTema(temaDelSistema())
        globalThis.dispatchEvent(new CustomEvent<Tema>(EVENTO_TEMA, { detail: temaDelSistema() }))
      }
    })
  } catch {
    // Navegadores viejos sin addEventListener en MediaQueryList: sin seguimiento en vivo.
  }
  globalThis.addEventListener?.('storage', (e) => {
    if (e.key !== CLAVE_TEMA) return
    const tema = temaVigente()
    aplicarTema(tema)
    globalThis.dispatchEvent(new CustomEvent<Tema>(EVENTO_TEMA, { detail: tema }))
  })
}
