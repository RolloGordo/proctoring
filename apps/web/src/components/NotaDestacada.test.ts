import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { NotaDestacada } from './NotaDestacada'

const ENTREGADO = '2026-11-06T15:30:00Z'

type Props = Parameters<typeof NotaDestacada>[0]
const nota = (props: Props): string => renderToStaticMarkup(createElement(NotaDestacada, props))

function texto(html: string): string {
  return html
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

describe('NotaDestacada', () => {
  it('muestra la cifra y sobre cuánto es', () => {
    const html = nota({ score: 15, maxScore: 20, submittedAt: ENTREGADO, parcial: false })
    expect(texto(html)).toMatch(/^15 \/ 20 Nota del examen · entregado el/)
    expect(html).toContain('aria-label="Nota: 15 de 20"')
    expect(html).not.toContain('Parcial')
  })

  it('usa el punto decimal de es-PE, como el resto de la app', () => {
    const html = nota({ score: 12.5, maxScore: 20, submittedAt: ENTREGADO, parcial: false })
    expect(texto(html)).toContain('12.5 / 20')
  })

  it('avisa cuando la nota es parcial', () => {
    const html = nota({ score: 8, maxScore: 20, submittedAt: ENTREGADO, parcial: true })
    expect(texto(html)).toContain('Parcial: faltan desarrollos por calificar')
    expect(html).toContain('aria-label="Nota: 8 de 20, parcial"')
  })

  it('sin entrega no inventa un cero', () => {
    const html = nota({ score: null, maxScore: 20, submittedAt: null, parcial: false })
    expect(texto(html)).toContain('Sin entregar')
    expect(texto(html)).not.toMatch(/\b0\b/)
  })

  it('entregado sin calificar lo dice con palabras', () => {
    const html = nota({ score: null, maxScore: 20, submittedAt: ENTREGADO, parcial: false })
    expect(texto(html)).toContain('Pendiente de calificación')
  })

  it('sin el total todavía, muestra solo la cifra', () => {
    const html = nota({ score: 15, maxScore: null, submittedAt: ENTREGADO, parcial: false })
    expect(texto(html)).toMatch(/^15 Nota del examen/)
  })
})
