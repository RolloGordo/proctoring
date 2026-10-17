import { describe, expect, it, vi } from 'vitest'
import { DetectorPersonaExtra, DetectorRostroAusente } from './vision'

// Este test no requiere cámara, modelo, WASM ni datos biométricos.
const mediapipe = vi.hoisted(() => ({
  create: vi.fn(),
  configure: vi.fn(),
  infer: vi.fn(),
  resolveWasm: vi.fn()
}))

vi.mock('@mediapipe/tasks-vision', () => ({
  FaceLandmarker: { createFromOptions: mediapipe.create },
  FilesetResolver: { forVisionTasks: mediapipe.resolveWasm }
}))

describe('motor MediaPipe compartido de SPEC-007', () => {
  it('amplía de dos a tres rostros cuando min_faces es 3', async () => {
    mediapipe.resolveWasm.mockResolvedValue({})
    mediapipe.configure.mockResolvedValue(undefined)
    mediapipe.infer.mockReturnValue({
      faceLandmarks: [[], [], []],
      facialTransformationMatrixes: []
    })
    mediapipe.create.mockResolvedValue({
      setOptions: mediapipe.configure,
      detectForVideo: mediapipe.infer
    })

    const ausente = new DetectorRostroAusente()
    const adicional = new DetectorPersonaExtra({ min_faces: 3 })

    // No cargar el modelo simplemente por instanciar detectores.
    expect(mediapipe.create).not.toHaveBeenCalled()
    await ausente.preparar()
    expect(mediapipe.create).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ numFaces: 2 })
    )
    await adicional.preparar()
    expect(mediapipe.configure).toHaveBeenCalledWith({ numFaces: 3 })
    expect(mediapipe.create).toHaveBeenCalledTimes(1)

    const video = { readyState: 4, videoWidth: 640 } as HTMLVideoElement
    const observacion = { video, ahoraMs: 111 }
    const extra = adicional.observar(observacion)
    expect(extra.activa).toBe(true)
    expect(extra.metadata).toMatchObject({ min_faces: 3, model_num_faces: 3 })
    expect(ausente.observar(observacion).activa).toBe(false)
    expect(mediapipe.infer).toHaveBeenCalledTimes(1)
  })
})
