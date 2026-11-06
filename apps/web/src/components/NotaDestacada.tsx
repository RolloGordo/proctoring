import { fechaLarga, formatearNota } from '../lib/formato'

/**
 * La nota de un examen, en grande: lo primero que se busca al terminar.
 *
 * El docente nos dijo que le costaba encontrarla: estaba en una columna más de
 * la tabla y no aparecía en la revisión del caso. Aquí va con la cifra a
 * tamaño de titular y, debajo, lo que hace falta para leerla bien: sobre
 * cuánto es, cuándo se entregó y si todavía es **parcial**.
 *
 * Nunca un cero inventado: sin entrega o sin calificación lo dice con palabras.
 * La nota y el riesgo van por separado a propósito: el sistema audita, no
 * castiga, y una no se calcula con el otro.
 */
export function NotaDestacada({
  score,
  maxScore,
  submittedAt,
  parcial
}: {
  score: number | null
  maxScore: number | null
  submittedAt: string | null
  parcial: boolean
}) {
  if (!submittedAt) {
    return (
      <div className="nota-destacada">
        <p className="nota-destacada-estado">Sin entregar</p>
        <p className="nota-destacada-pie">Todavía no hay nota: el examen no se entregó.</p>
      </div>
    )
  }

  if (score === null) {
    return (
      <div className="nota-destacada">
        <p className="nota-destacada-estado">Pendiente de calificación</p>
        <p className="nota-destacada-pie">Entregado el {fechaLarga(submittedAt)}</p>
      </div>
    )
  }

  const total = maxScore !== null && Number.isFinite(maxScore) ? maxScore : null
  return (
    <div className="nota-destacada">
      <p
        className="nota-destacada-cifra"
        aria-label={`Nota: ${formatearNota(score)}${total !== null ? ` de ${formatearNota(total)}` : ''}${parcial ? ', parcial' : ''}`}
      >
        <strong>{formatearNota(score)}</strong>
        {total !== null && <span className="nota-destacada-total">/ {formatearNota(total)}</span>}
      </p>
      <p className="nota-destacada-pie">Nota del examen · entregado el {fechaLarga(submittedAt)}</p>
      {parcial && (
        <p className="chip chip-programado nota-destacada-parcial">
          Parcial: faltan desarrollos por calificar
        </p>
      )}
    </div>
  )
}
