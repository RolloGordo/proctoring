/**
 * La API que la app de escritorio expone a la web (`apps/desktop/src/preload`).
 *
 * Solo existe cuando la web corre dentro de la ventana de Electron; en un
 * navegador normal `window.api` es `undefined`, y por eso todo es opcional.
 * Aqui se declara unicamente lo que la web usa.
 */
interface Window {
  api?: {
    /** Entrega la sesion de Supabase al proceso principal, o `null` al cerrarla. */
    setAuthSession?: (
      session: { accessToken: string; refreshToken: string } | null
    ) => Promise<void>
  }
}
