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
