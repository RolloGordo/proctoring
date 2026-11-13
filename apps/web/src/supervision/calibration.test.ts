import { describe, expect, it } from 'vitest'
import {
  estimateCalibration,
  combinarMuestras,
  validarPaso,
  EYE_DOWN_PLAUSIBLE,
  EYE_DOWN_MAX,
  EYE_SIDE_DEFAULT
} from './calibration'

describe('TA-073 gaze calibration', () => {
  const sample = (yaw: number) => ({ faceCount: 1, yaw, pitch: 0 })
  it('accounts for center orientation and uses session minimum as floor', () => {
    const result = estimateCalibration([sample(10), sample(36), sample(-15), sample(28), sample(-18)], 25)
    expect(result.baselineYawDeg).toBe(10)
    expect(result.thresholdDeg).toBe(25)
  })
  it('does not accept a second face or missing measurement', () => {
    expect(() => estimateCalibration([sample(0), sample(1), sample(2), { faceCount: 2, yaw: null, pitch: null }, sample(3)])).toThrow()
  })
  it('caps the adjustment to avoid an implausibly permissive threshold', () => {
    expect(estimateCalibration([sample(0), sample(80), sample(-80), sample(70), sample(-70)]).thresholdDeg).toBe(45)
  })
})

describe('calibración de los ojos (Jesús)', () => {
  const s = (eyeDown: number) => ({ faceCount: 1, yaw: 0, pitch: 0, eyeDown, eyeBlink: 0.1 })
  it('el umbral queda por encima de lo que baja la vista para leer el borde inferior', () => {
    const r = estimateCalibration([s(0.1), s(0.1), s(0.1), s(0.55), s(0.5)], 25)
    expect(r.baselineEyeDown).toBe(0.1)
    expect(r.eyeDownThreshold).toBeCloseTo(0.6)
  })
  it('nunca más estricto que el valor por defecto', () => {
    expect(estimateCalibration([s(0.1), s(0.1), s(0.1), s(0.15), s(0.12)]).eyeDownThreshold).toBe(0.45)
  })
  it('con tope, para que mirar las piernas siga contando', () => {
    expect(estimateCalibration([s(0), s(0), s(0), s(0.9), s(0.9)]).eyeDownThreshold).toBe(0.7)
  })
  it('una calibración sin datos de ojos sigue valiendo', () => {
    const r = estimateCalibration([0, 1, 2, 3, 4].map((y) => ({ faceCount: 1, yaw: y, pitch: 0 })))
    expect(r.eyeDownThreshold).toBeUndefined()
  })
})

describe('calibración con varios fotogramas por paso (Jesús)', () => {
  const m = (eyeDown: number, eyeBlink = 0.1, faceCount = 1, eyeSide = 0.1) => ({
    faceCount,
    yaw: 0,
    pitch: 0,
    eyeDown,
    eyeBlink,
    eyeSide
  })

  it('un parpadeo en medio del paso no falsea la medición', () => {
    // Seis fotogramas; en uno el estudiante parpadea (párpado 0,95, vista 0,6).
    const r = combinarMuestras([m(0.12), m(0.11), m(0.6, 0.95), m(0.13), m(0.12), m(0.12)])
    expect(r?.eyeDown).toBeCloseTo(0.12)
    expect(r?.eyeBlink).toBeCloseTo(0.1)
  })

  it('si en menos de cuatro fotogramas se ve un solo rostro, el paso no vale', () => {
    expect(
      combinarMuestras([m(0.1), m(0.1), m(0.1, 0.1, 0), m(0.1, 0.1, 2), m(0.1, 0.1, 0), m(0.1)])
    ).toBeNull()
  })

  it('rechaza una esquina inferior que en realidad mira por debajo de la pantalla', () => {
    const centro = m(0.1)
    expect(validarPaso(3, m(0.8), centro)).toMatch(/por debajo de la pantalla/)
    expect(validarPaso(3, m(0.45), centro)).toBeNull()
    expect(validarPaso(0, m(0.9))).toBeNull()
  })

  it('un paso aceptado nunca deja el umbral de ojos sobre el tope', () => {
    expect(EYE_DOWN_PLAUSIBLE + 0.15).toBeCloseTo(EYE_DOWN_MAX)
  })

  it('calibra también la mirada lateral con las cuatro esquinas', () => {
    const pasos = [
      m(0.1, 0.1, 1, 0.05),
      m(0.1, 0.1, 1, 0.5),
      m(0.1, 0.1, 1, 0.55),
      m(0.3, 0.1, 1, 0.5),
      m(0.3, 0.1, 1, 0.6)
    ]
    expect(estimateCalibration(pasos).eyeSideThreshold).toBeCloseTo(0.75)
  })

  it('la mirada lateral nunca queda más estricta que el valor por defecto', () => {
    const pasos = [0, 1, 2, 3, 4].map(() => m(0.1, 0.1, 1, 0.1))
    expect(estimateCalibration(pasos).eyeSideThreshold).toBe(EYE_SIDE_DEFAULT)
  })
})
