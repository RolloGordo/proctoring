import { describe, expect, it } from 'vitest'
import { angulosDesdeMatriz, capacidadParaUmbralRostros, reglasVision } from './vision-core'

const identidad = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]

describe('geometría de cabeza', () => {
  it('identidad son cero grados', () => {
    const r = angulosDesdeMatriz({ data: identidad })
    expect(r?.yaw).toBeCloseTo(0)
    expect(r?.pitch).toBeCloseTo(0)
  })
  it('detecta giro horizontal de 30 grados y pitch', () => {
    const a = Math.PI / 6
    const matriz = [Math.cos(a),0,Math.sin(a),0, 0,1,0,0, -Math.sin(a),0,Math.cos(a),0, 0,0,0,1]
    expect(angulosDesdeMatriz({ data: matriz })?.yaw).toBeCloseTo(30)
  })
  it('rechaza matrices inválidas', () => {
    expect(angulosDesdeMatriz({ data: [1, 2] })).toBeNull()
  })
})

describe('reglas instantáneas', () => {
  it('sin rostro: ausencia y no mirada', () => {
    expect(reglasVision(0, null, 25, 2)).toEqual({
      gaze_away: false, face_absent: true, extra_person: false
    })
  })
  it('dos caras: persona adicional y no mirada', () => {
    expect(reglasVision(2, 45, 25, 2).extra_person).toBe(true)
    expect(reglasVision(2, 45, 25, 2).gaze_away).toBe(false)
  })
  it('un rostro y giro mayor al umbral', () => {
    expect(reglasVision(1, -30, 25, 2).gaze_away).toBe(true)
    expect(reglasVision(1, 10, 25, 2).gaze_away).toBe(false)
  })
})

describe('configuración de múltiples rostros', () => {
  it('permite que min_faces=3 tenga capacidad real de 3 rostros', () => {
    expect(capacidadParaUmbralRostros(3)).toBe(3)
    expect(reglasVision(3, null, 25, 3).extra_person).toBe(true)
    expect(reglasVision(2, null, 25, 3).extra_person).toBe(false)
  })
  it('rechaza límites imposibles en vez de generar alertas inalcanzables', () => {
    expect(() => capacidadParaUmbralRostros(11)).toThrow(RangeError)
    expect(() => capacidadParaUmbralRostros(1)).toThrow(RangeError)
    expect(() => capacidadParaUmbralRostros(Number.NaN)).toThrow(RangeError)
  })
})
