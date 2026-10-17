import { describe, it, expect } from 'vitest'
import { CameraHealthMonitor } from './cameraHealth'

describe('TA-083 camera-health safeguards', () => {
  it('reports a disconnected track immediately', () => {
    expect(new CameraHealthMonitor().check(0, 0, 'ended', null)).toBe('interrupted')
  })
  it('does not treat ordinary brief darkness as interruption', () => {
    const m = new CameraHealthMonitor()
    expect(m.check(0, 1, 'live', 0)).toBe('active')
    expect(m.check(1000, 2, 'live', 0)).toBe('active')
    expect(m.check(5000, 3, 'live', 40)).toBe('active')
  })
  it('flags prolonged black video as possible lack of image, not misconduct', () => {
    const m = new CameraHealthMonitor()
    m.check(0, 1, 'live', 2)
    expect(m.check(4100, 2, 'live', 2)).toBe('no_image')
  })
  it('flags a stalled video clock after four seconds', () => {
    const m = new CameraHealthMonitor()
    m.check(0, 11, 'live', 120)
    m.check(1000, 11, 'live', 120)
    expect(m.check(5100, 11, 'live', 120)).toBe('no_image')
    expect(m.check(5200, 12, 'live', 120)).toBe('active')
  })
})
