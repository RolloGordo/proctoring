/**
 * Exportar señales a un archivo que Excel abre bien (reunión del 14/11: si un
 * estudiante reclama, el docente manda el historial a la dirección de escuela).
 *
 * CSV y no .xlsx: no hace falta ninguna librería y Excel lo abre con doble clic.
 * Dos detalles para que no salga roto en un Excel en español:
 * - separador `;`, porque con la configuración regional de Perú la coma es el
 *   separador decimal y Excel pondría todo en una sola columna;
 * - BOM UTF-8 al inicio, o las tildes y la «ñ» salen como «Ã±».
 */
import type { ProctoringEvent } from './api'
import { detalleEvento, nombreEvento, nombreSeveridad } from './formato'

const BOM = '﻿'

function celda(valor: string | number | null | undefined): string {
  const texto = valor === null || valor === undefined ? '' : String(valor)
  // Evita que Excel interprete una celda como fórmula (inyección CSV): el
  // detalle de una señal lo escribe la app del estudiante.
  const seguro = /^[=+\-@\t\r]/.test(texto) ? `'${texto}` : texto
  return /[";\n\r]/.test(seguro) ? `"${seguro.replace(/"/g, '""')}"` : seguro
}

export function aCsv(
  encabezados: string[],
  filas: Array<Array<string | number | null | undefined>>
): string {
  return BOM + [encabezados, ...filas].map((fila) => fila.map(celda).join(';')).join('\r\n')
}

/** Fecha y hora local legible por Excel: «2026-11-14 16:24:50». */
function fechaHora(iso: string): string {
  const d = new Date(iso)
  const dos = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())} ${dos(d.getHours())}:${dos(d.getMinutes())}:${dos(d.getSeconds())}`
}

/** Las señales en filas, con quién las produjo si se sabe. */
export function senalesACsv(
  eventos: readonly ProctoringEvent[],
  quien: (studentId: string) => { nombre?: string | null; correo?: string | null } = () => ({})
): string {
  return aCsv(
    [
      'Fecha y hora',
      'Estudiante',
      'Correo',
      'Señal',
      'Nivel',
      'Duración (s)',
      'Detalle',
      'Evidencia'
    ],
    eventos.map((evento) => {
      const persona = quien(evento.student_id)
      return [
        fechaHora(evento.started_at),
        persona.nombre ?? '',
        persona.correo ?? '',
        nombreEvento(evento.event_type),
        nombreSeveridad(evento.severity),
        (evento.duration_ms / 1000).toFixed(1).replace('.', ','),
        detalleEvento(evento.metadata),
        evento.evidence_path ? 'Sí' : 'No'
      ]
    })
  )
}

/** Descarga un texto como archivo, sin pasar por el servidor. */
export function descargar(
  nombreArchivo: string,
  contenido: string,
  tipo = 'text/csv;charset=utf-8'
): void {
  const url = URL.createObjectURL(new Blob([contenido], { type: tipo }))
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = nombreArchivo
  document.body.appendChild(enlace)
  enlace.click()
  enlace.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** «señales-examen-parcial-2026-11-14.csv»: sin espacios ni caracteres raros. */
export function nombreSeguro(...partes: string[]): string {
  const base = partes
    .join('-')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80)
  return `${base || 'senales'}.csv`
}
