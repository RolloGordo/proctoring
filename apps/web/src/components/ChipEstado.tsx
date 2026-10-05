import { nombreEstadoExamen, type EstadoExamen } from '../lib/formato'

export function ChipEstado({ estado }: { estado: EstadoExamen }) {
  return <span className={`chip chip-${estado}`}>{nombreEstadoExamen(estado)}</span>
}
