import { describe, expect, it } from 'vitest'
import type { Alert, Participant } from './api'
import { alertasSinVer, esperandoAdmision, textoGlobo } from './avisos-examen'

function participante(parcial: Partial<Participant>): Participant {
  return {
    can_take_exam: false,
    submitted_at: null,
    verification_status: 'pending',
    ...parcial
  } as Participant
}

describe('esperandoAdmision', () => {
  it('cuenta solo a quien espera decisión', () => {
    const lista = [
      participante({ verification_status: 'pending' }),
      participante({ verification_status: 'failed' }),
      participante({ verification_status: 'rejected' }),
      participante({ verification_status: 'manually_approved', can_take_exam: true }),
      participante({ submitted_at: '2026-11-07T00:00:00Z' })
    ]
    expect(esperandoAdmision(lista)).toBe(2)
  })
})

describe('alertasSinVer', () => {
  it('descuenta las ya vistas', () => {
    const alertas = [{ id: 'a' }, { id: 'b' }, { id: 'c' }] as Alert[]
    expect(alertasSinVer(alertas, new Set(['a']))).toBe(2)
    expect(alertasSinVer(alertas, new Set(['a', 'b', 'c']))).toBe(0)
  })
})

describe('textoGlobo', () => {
  it('no muestra cero y topa en 99+', () => {
    expect(textoGlobo(0)).toBeUndefined()
    expect(textoGlobo(3)).toBe('3')
    expect(textoGlobo(150)).toBe('99+')
  })
})
