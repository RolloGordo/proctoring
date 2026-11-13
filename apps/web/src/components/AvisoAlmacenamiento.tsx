import { useState } from 'react'
import { Link } from 'react-router-dom'

/**
 * El aviso sobre lo que la web guarda en el navegador.
 *
 * **Informa, no pide permiso.** La web no usa cookies y lo que guarda es
 * imprescindible: la sesión, y durante un examen una copia de las respuestas.
 * Un botón de «Rechazar» haría creer que hay algo opcional, y rechazarlo de
 * verdad rompería el acceso. Por eso hay un solo botón, y dice lo que hace.
 *
 * No se monta en la pantalla del examen: ahí no se interrumpe a nadie. Va en
 * la portada, el acceso y las páginas públicas, que es donde se llega antes.
 */

const CLAVE = 'proctoring:aviso-almacenamiento'

function yaVisto(): boolean {
  // El navegador puede negar el almacenamiento (ventana privada, datos de
  // sitio bloqueados). Entonces el aviso sale cada vez, que es lo seguro.
  try {
    return localStorage.getItem(CLAVE) === '1'
  } catch {
    return false
  }
}

export function AvisoAlmacenamiento() {
  const [visible, setVisible] = useState(() => !yaVisto())
  if (!visible) return null

  function cerrar(): void {
    try {
      localStorage.setItem(CLAVE, '1')
    } catch {
      // Sin almacenamiento no se puede recordar; se cierra igual por ahora.
    }
    setVisible(false)
  }

  return (
    <section className="aviso-almacenamiento" aria-label="Aviso sobre el almacenamiento">
      <p>
        <strong>No usamos cookies.</strong> Solo guardamos en tu navegador tu sesión y, durante un
        examen, una copia temporal de las respuestas que aún no llegaron al servidor. Nada de publicidad ni de seguimiento.{' '}
        <Link to="/privacidad#cookies">Más detalles</Link>
      </p>
      <button type="button" onClick={cerrar}>
        Entendido
      </button>
    </section>
  )
}
