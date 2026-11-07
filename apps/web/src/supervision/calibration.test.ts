import { describe, expect, it } from 'vitest'
import { estimateCalibration } from './calibration'

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
