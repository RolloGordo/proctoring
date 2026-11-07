import { describe, expect, it, vi } from 'vitest'
import { LIMITES_OJOS_POR_DEFECTO, ojosDesdeBlendshapes, reglaOjos } from './vision-core'
import { DetectorMirada } from './vision'

/** Blendshapes con los nombres reales de MediaPipe. */
function ojos({ abajo = 0, afueraIzq = 0, adentroDer = 0, parpado = 0 }) {
  return [
    { categoryName: 'eyeLookDownLeft', score: abajo },
    { categoryName: 'eyeLookDownRight', score: abajo },
    { categoryName: 'eyeLookOutLeft', score: afueraIzq },
    { categoryName: 'eyeLookInRight', score: adentroDer },
    { categoryName: 'eyeLookInLeft', score: 0 },
    { categoryName: 'eyeLookOutRight', score: 0 },
    { categoryName: 'eyeBlinkLeft', score: parpado },
    { categoryName: 'eyeBlinkRight', score: parpado }
  ]
}

describe('ojos desde blendshapes', () => {
  it('promedia los dos ojos', () => {
    expect(ojosDesdeBlendshapes(ojos({ abajo: 0.6, parpado: 0.2 }))).toEqual({
      abajo: 0.6,
      lado: 0,
      parpado: 0.2
    })
  })
  it('sin blendshapes no inventa nada', () => {
    expect(ojosDesdeBlendshapes(undefined)).toBeNull()
    expect(ojosDesdeBlendshapes([{ categoryName: 'jawOpen', score: 1 }])).toBeNull()
  })
})

describe('regla de ojos: cabeza quieta, vista abajo', () => {
  const limites = { ...LIMITES_OJOS_POR_DEFECTO }
  it('mirando la pantalla no marca', () => {
    expect(reglaOjos({ abajo: 0.2, lado: 0.1, parpado: 0.1 }, limites)).toBeNull()
  })
  it('bajar la vista al celular marca, aunque la cabeza no gire', () => {
    expect(reglaOjos({ abajo: 0.7, lado: 0, parpado: 0.2 }, limites)).toBe('eyes_down')
  })
  it('párpado caído sobre el iris (con lentes) también cuenta como abajo', () => {
    expect(reglaOjos({ abajo: 0.3, lado: 0, parpado: 0.6 }, limites)).toBe('eyes_down')
  })
  it('un párpado cerrado sin bajar la vista no basta', () => {
    expect(reglaOjos({ abajo: 0.05, lado: 0, parpado: 0.9 }, limites)).toBeNull()
  })
  it('mirar a un lado solo con los ojos', () => {
    expect(reglaOjos({ abajo: 0, lado: 0.7, parpado: 0 }, limites)).toBe('eyes_side')
  })
  it('respeta la línea base calibrada de cada estudiante', () => {
    // Alguien que, mirando al centro, ya marca 0.3 de eyeLookDown.
    const calibrado = { ...limites, baseAbajo: 0.3 }
    expect(reglaOjos({ abajo: 0.6, lado: 0, parpado: 0 }, calibrado)).toBeNull()
    expect(reglaOjos({ abajo: 0.8, lado: 0, parpado: 0 }, calibrado)).toBe('eyes_down')
  })
})

// --- El detector real, con MediaPipe simulado ---------------------------------
const mediapipe = vi.hoisted(() => ({ infer: vi.fn() }))
vi.mock('@mediapipe/tasks-vision', () => ({
  FilesetResolver: { forVisionTasks: vi.fn().mockResolvedValue({}) },
  FaceLandmarker: {
    createFromOptions: vi.fn().mockResolvedValue({
      setOptions: vi.fn().mockResolvedValue(undefined),
      detectForVideo: mediapipe.infer
    })
  }
}))

const identidad = { data: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1] }
const video = { readyState: 4, videoWidth: 640 } as HTMLVideoElement

describe('DetectorMirada con los ojos', () => {
  it('cabeza al frente y ojos abajo: activa con motivo eyes_down', async () => {
    const detector = new DetectorMirada()
    await detector.preparar()
    mediapipe.infer.mockReturnValue({
      faceLandmarks: [[]],
      facialTransformationMatrixes: [identidad],
      faceBlendshapes: [{ categories: ojos({ abajo: 0.75 }) }]
    })
    const v = detector.observar({ video, ahoraMs: 1 })
    expect(v.activa).toBe(true)
    expect(v.metadata).toMatchObject({ reason: 'eyes_down', yaw_deg: 0, eye_down: 0.75 })
  })

  it('el docente puede apagar la regla de ojos', async () => {
    const detector = new DetectorMirada({ eye_gaze: false })
    await detector.preparar()
    mediapipe.infer.mockReturnValue({
      faceLandmarks: [[]],
      facialTransformationMatrixes: [identidad],
      faceBlendshapes: [{ categories: ojos({ abajo: 0.75 }) }]
    })
    expect(detector.observar({ video, ahoraMs: 2 }).activa).toBe(false)
  })

  it('el giro de cabeza sigue funcionando igual', async () => {
    const detector = new DetectorMirada()
    await detector.preparar()
    const a = Math.PI / 4
    mediapipe.infer.mockReturnValue({
      faceLandmarks: [[]],
      facialTransformationMatrixes: [
        {
          data: [
            Math.cos(a),
            0,
            Math.sin(a),
            0,
            0,
            1,
            0,
            0,
            -Math.sin(a),
            0,
            Math.cos(a),
            0,
            0,
            0,
            0,
            1
          ]
        }
      ],
      faceBlendshapes: [{ categories: ojos({}) }]
    })
    const v = detector.observar({ video, ahoraMs: 3 })
    expect(v.activa).toBe(true)
    expect(v.metadata).toMatchObject({ reason: 'head_yaw' })
  })
})
