import { FormularioCodigo } from '../components/FormularioCodigo'

/**
 * "Entrar a un examen": la misma entrada que el panel, a pantalla completa.
 *
 * El aviso sobre la aplicación de escritorio solo se muestra en el navegador.
 * Dentro de la propia aplicación sería decirle a alguien que ya la está usando
 * que la necesita.
 */
export function AccesoExamen() {
  const enEscritorio = window.api !== undefined

  return (
    <div className="centrado-estrecho">
      <h1>Entrar a un examen</h1>
      <p className="subtitulo">Escribe el código que te dio tu docente</p>

      <div className="tarjeta" style={{ marginTop: 'var(--e6)' }}>
        <div className="tarjeta-cuerpo">
          <FormularioCodigo />
        </div>
      </div>

      {!enEscritorio && (
        <p className="ayuda" style={{ marginTop: 'var(--e5)' }}>
          Para rendir el examen necesitas la aplicación de escritorio. Esta pantalla sirve para
          comprobar que tu código es correcto y ver cuándo empieza.
        </p>
      )}
    </div>
  )
}
