import type { AvisoVisible as Aviso } from '../supervision/avisos'

/** Componente compartido por cámara y audio; flotante, sin bloquear la pregunta. */
export function AvisoSupervision({ aviso, onCerrar }: { aviso: Aviso | null; onCerrar: () => void }) {
  if (!aviso) return null
  return (
    <aside
      aria-live="polite"
      aria-label="Aviso de supervisión"
      className="aviso-supervision-flotante"
    >
      <div className="aviso-supervision-icono" aria-hidden="true">!</div>
      <div className="aviso-supervision-contenido">
        <strong>{aviso.titulo}</strong>
        <p>{aviso.detalle}</p>
        <button type="button" className="boton" onClick={onCerrar}>
          Entendido, continuar
        </button>
      </div>
    </aside>
  )
}
