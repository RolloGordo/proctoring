import { expect, it } from 'vitest'
import { avisoParaEvento } from './avisos'

it('avisos concretos sin acusación para rostro, giro, persona y voz', () => {
  for (const tipo of ['gaze_away', 'face_absent', 'extra_person', 'speech_detected'] as const) {
    const aviso = avisoParaEvento(tipo)
    expect(aviso?.titulo.length).toBeGreaterThan(6)
    expect(aviso?.detalle).not.toMatch(/estás copiando|es una trampa/i)
  }
})
