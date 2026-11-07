import { describe, expect, it, vi } from 'vitest'
import {
  EstabilidadEncuadre,
  evaluarEncuadre,
  nivelDe,
  PUNTOS,
  type PuntoPose
} from './encuadre-core'
import { detectoresDe } from './index'

/** Una pose de 33 puntos, todos invisibles salvo los que se pidan. */
function pose(
  visibles: Partial<Record<keyof typeof PUNTOS, readonly [number, number]>>
): PuntoPose[] {
  const puntos: PuntoPose[] = Array.from({ length: 33 }, () => ({ x: 0.5, y: 0.5, visibility: 0 }))
  for (const [nombre, [x, y]] of Object.entries(visibles)) {
    puntos[PUNTOS[nombre as keyof typeof PUNTOS]] = { x, y, visibility: 0.95 }
  }
  return puntos
}

const cara = { nariz: [0.5, 0.3], orejaIzq: [0.58, 0.28], orejaDer: [0.42, 0.28] } as const
const hombros = { hombroIzq: [0.68, 0.6], hombroDer: [0.32, 0.6] } as const
const codos = { codoIzq: [0.78, 0.88], codoDer: [0.22, 0.88] } as const
const munecas = { munecaIzq: [0.6, 0.95], munecaDer: [0.4, 0.95] } as const

describe('evaluarEncuadre', () => {
  it('solo la cara: pide alejar la cámara', () => {
    const r = evaluarEncuadre([pose({ ...cara })])
    expect(r.ok).toBe(false)
    expect(r.motivo).toBe('no_shoulders')
    expect(r.mensaje).toMatch(/Solo se ve tu cara/)
  })
  it('cara y hombros sin codos: con el nivel por defecto no alcanza', () => {
    expect(evaluarEncuadre([pose({ ...cara, ...hombros })]).motivo).toBe('no_elbows')
  })
  it('cara, hombros y codos: encuadre correcto', () => {
    expect(evaluarEncuadre([pose({ ...cara, ...hombros, ...codos })]).ok).toBe(true)
  })
  it('el docente puede pedir menos o más', () => {
    expect(evaluarEncuadre([pose({ ...cara, ...hombros })], 'shoulders').ok).toBe(true)
    expect(evaluarEncuadre([pose({ ...cara, ...hombros, ...codos })], 'hands').motivo).toBe(
      'no_hands'
    )
    expect(evaluarEncuadre([pose({ ...cara, ...hombros, ...codos, ...munecas })], 'hands').ok).toBe(
      true
    )
    expect(evaluarEncuadre([pose({ ...cara })], 'off').ok).toBe(true)
  })
  it('demasiado cerca: hombros que ocupan casi todo el ancho', () => {
    const r = evaluarEncuadre([pose({ ...cara, hombroIzq: [0.97, 0.8], hombroDer: [0.03, 0.8] })])
    expect(r.motivo).toBe('too_close')
  })
  it('sin nadie', () => {
    expect(evaluarEncuadre([]).motivo).toBe('no_person')
    expect(evaluarEncuadre([pose({})]).motivo).toBe('no_person')
  })
  it('un punto "estirado" fuera del borde inferior no cuenta como visible', () => {
    const r = evaluarEncuadre([
      pose({ ...cara, ...hombros, codoIzq: [0.8, 1.1], codoDer: [0.2, 1.05] })
    ])
    expect(r.motivo).toBe('no_elbows')
  })
  it('un punto con poca confianza no cuenta', () => {
    const p = pose({ ...cara, ...hombros, ...codos })
    p[PUNTOS.codoIzq].visibility = 0.3
    expect(evaluarEncuadre([p]).motivo).toBe('no_elbows')
  })
  it('un nivel desconocido usa el por defecto', () => {
    expect(nivelDe('todo')).toBe('elbows')
    expect(nivelDe('hands')).toBe('hands')
  })
})

describe('EstabilidadEncuadre', () => {
  it('pide 2 s seguidos de buen encuadre', () => {
    const e = new EstabilidadEncuadre(2000)
    expect(e.registrar(true, 0)).toBe(false)
    expect(e.registrar(true, 1500)).toBe(false)
    expect(e.progreso(1500)).toBeCloseTo(0.75)
    expect(e.registrar(true, 2000)).toBe(true)
  })
  it('un mal fotograma reinicia la cuenta', () => {
    const e = new EstabilidadEncuadre(2000)
    e.registrar(true, 0)
    e.registrar(false, 1900)
    expect(e.registrar(true, 2100)).toBe(false)
    expect(e.registrar(true, 4100)).toBe(true)
  })
})

describe('registro del detector de encuadre', () => {
  it('va con mirada u objetos', () => {
    expect(detectoresDe({ gaze: {} }).map((d) => d.nombre)).toContain('encuadre')
    expect(detectoresDe({ objects: {} }).map((d) => d.nombre)).toContain('encuadre')
  })
  it('no va sin módulos de cámara', () => {
    expect(detectoresDe({ ai_voice: {} }).map((d) => d.nombre)).not.toContain('encuadre')
  })
  it('el docente lo apaga con framing_required: off', () => {
    expect(
      detectoresDe({ objects: { framing_required: 'off' } }).map((d) => d.nombre)
    ).not.toContain('encuadre')
  })
})

// --- El detector real, con MediaPipe simulado ---------------------------------
const mediapipe = vi.hoisted(() => ({ infer: vi.fn(), create: vi.fn() }))
vi.mock('@mediapipe/tasks-vision', () => ({
  FilesetResolver: { forVisionTasks: vi.fn().mockResolvedValue({}) },
  PoseLandmarker: { createFromOptions: mediapipe.create }
}))

describe('DetectorEncuadre', () => {
  const video = { readyState: 4, videoWidth: 640 } as HTMLVideoElement

  it('carga el modelo local, sin servicios externos', async () => {
    mediapipe.create.mockResolvedValue({ detectForVideo: mediapipe.infer })
    const { DetectorEncuadre } = await import('./encuadre')
    await new DetectorEncuadre().preparar()
    expect(mediapipe.create).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        baseOptions: { modelAssetPath: '/mediapipe/pose_landmarker_lite.task' },
        numPoses: 1
      })
    )
  })

  it('cámara apuntando solo a la cara: activa con motivo', async () => {
    const { DetectorEncuadre } = await import('./encuadre')
    const d = new DetectorEncuadre()
    await d.preparar()
    mediapipe.infer.mockReturnValue({ landmarks: [pose({ ...cara })] })
    const v = d.observar({ video, ahoraMs: 1000 })
    expect(v.activa).toBe(true)
    expect(v.metadata).toMatchObject({ reason: 'no_shoulders', framing_required: 'elbows' })
    expect(d.evento).toBe('framing_lost')
  })

  it('sin nadie no se cuenta: eso ya es face_absent', async () => {
    const { DetectorEncuadre } = await import('./encuadre')
    const d = new DetectorEncuadre()
    await d.preparar()
    mediapipe.infer.mockReturnValue({ landmarks: [] })
    expect(d.observar({ video, ahoraMs: 5000 }).activa).toBe(false)
  })

  it('mide como mucho cada 500 ms', async () => {
    const { DetectorEncuadre } = await import('./encuadre')
    const d = new DetectorEncuadre()
    await d.preparar()
    mediapipe.infer.mockClear()
    mediapipe.infer.mockReturnValue({ landmarks: [pose({ ...cara, ...hombros, ...codos })] })
    d.observar({ video, ahoraMs: 10_000 })
    d.observar({ video, ahoraMs: 10_200 })
    d.observar({ video, ahoraMs: 10_600 })
    expect(mediapipe.infer).toHaveBeenCalledTimes(2)
  })
})
