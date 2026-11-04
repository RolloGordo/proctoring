import type { SupervisionModule } from '../lib/api'
import {
  GRUPOS,
  MODULOS,
  MODULOS_DE_PRESET,
  alternarModulo,
  dispositivosQueUsa
} from '../lib/modulos'

interface Props {
  elegidos: ReadonlySet<SupervisionModule>
  onChange: (elegidos: Set<SupervisionModule>) => void
  /** Con estudiantes dentro ya no se cambia lo que se vigila. */
  deshabilitado?: boolean
}

const PARTIR_DE = [
  { preset: 'basic', nombre: 'Básica' },
  { preset: 'standard', nombre: 'Estándar' },
  { preset: 'strict', nombre: 'Estricta' }
] as const

/**
 * El docente elige qué vigilar, módulo a módulo (preset «Personalizada»).
 *
 * Agrupado por **con qué** se observa —identidad, cámara, micrófono, equipo—
 * porque es lo que le cambia la experiencia al estudiante: apagar los dos
 * módulos de voz es no pedirle el micrófono. Debajo se dice qué tendrá que
 * encender, para que el docente lo vea antes de compartir el código.
 *
 * Es un componente aparte para que el flujo nuevo de creación de exámenes lo
 * pueda usar tal cual.
 */
export function SelectorModulos({ elegidos, onChange, deshabilitado = false }: Props) {
  const { camara, microfono } = dispositivosQueUsa(elegidos)
  const usa = [camara && 'la cámara', microfono && 'el micrófono'].filter(Boolean)

  return (
    <fieldset className="selector-modulos" disabled={deshabilitado}>
      <legend className="sr-only">Módulos de supervisión</legend>

      <div className="selector-modulos-partir">
        <span className="ayuda">Partir de</span>
        {PARTIR_DE.map(({ preset, nombre }) => (
          <button
            key={preset}
            type="button"
            className="boton boton-secundario"
            onClick={() => onChange(new Set(MODULOS_DE_PRESET[preset]))}
          >
            {nombre}
          </button>
        ))}
      </div>

      <div className="selector-modulos-grupos">
        {GRUPOS.map((grupo) => (
          <div key={grupo.id} className="selector-modulos-grupo">
            <h3>{grupo.docente}</h3>
            <ul>
              {MODULOS.filter((m) => m.grupo === grupo.id).map((m) => {
                return (
                  <li key={m.id}>
                    <label>
                      <input
                        type="checkbox"
                        checked={elegidos.has(m.id)}
                        onChange={(e) => onChange(alternarModulo(elegidos, m.id, e.target.checked))}
                        aria-describedby={`modulo-${m.id}`}
                      />
                      <span className="selector-modulos-texto">
                        <strong>{m.nombre}</strong>
                        <span id={`modulo-${m.id}`} className="ayuda">
                          {m.detalle}
                        </span>
                      </span>
                    </label>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </div>

      <p className="selector-modulos-resumen" role="status">
        {elegidos.size === 0 ? (
          <>Elige al menos un módulo.</>
        ) : (
          <>
            <strong>
              {elegidos.size} de {MODULOS.length}
            </strong>{' '}
            ·{' '}
            {usa.length > 0
              ? `El estudiante tendrá que encender ${usa.join(' y ')}.`
              : 'No se le pedirá cámara ni micrófono al estudiante.'}
          </>
        )}
      </p>
    </fieldset>
  )
}
