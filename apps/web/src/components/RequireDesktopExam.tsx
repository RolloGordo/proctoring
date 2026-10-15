import { CapaPublica } from './Capas'
import type { ReactNode } from 'react'

const RELEASES_URL = 'https://github.com/RolloGordo/proctoring/releases'

export function RequireDesktopExam({ children }: { children: ReactNode }) {
  if (window.api) return children

  return (
    <CapaPublica>
      <section className="centrado-estrecho">
        <div className="tarjeta">
          <div className="tarjeta-cuerpo">
            <h1>Para rendir necesitas la aplicación de escritorio</h1>
            <p>
              Las páginas de espera y del examen solo están disponibles dentro de Proctoring
              Desktop. La aplicación permite aplicar la supervisión acordada, como la detección de
              cambios de ventana y monitores adicionales.
            </p>
            <p className="ayuda">
              Descarga la versión disponible para tu equipo. Se solicitarán permisos de cámara y
              micrófono solo para el examen.
            </p>
            <a
              className="boton"
              href={RELEASES_URL}
              target="_blank"
              rel="noreferrer"
            >
              Consultar descargas de Proctoring
            </a>
          </div>
        </div>
      </section>
    </CapaPublica>
  )
}
