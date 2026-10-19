import type { ObjectDetector } from '@mediapipe/tasks-vision'
import type { Detector, Observacion, Veredicto } from '../tipos'

export interface AjustesObjeto {
  min_duration_ms?: number
  score_threshold?: number
}

const MODELO = '/mediapipe/efficientdet_lite0.tflite'
// La vision general corre cada 125 ms, pero el modelo de objetos es mas caro.
// 250 ms reduce la demora sin ejecutar una inferencia pesada en cada fotograma.
const INTERVALO_INFERENCIA_MS = 250
const NOMBRES_CELULAR = new Set(['cell phone', 'mobile phone', 'phone', 'celular', 'telefono'])

function esCelular(nombre: string): boolean {
  const normalizado = nombre.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim()
  return NOMBRES_CELULAR.has(normalizado) || normalizado === 'cellphone' || normalizado === 'mobilephone'
}

let detector: ObjectDetector | undefined
let preparando: Promise<void> | undefined

/** Busca celulares; solo informa cuando la detección se mantiene durante el mínimo configurado. */
export class DetectorObjetoProhibido implements Detector {
  readonly nombre = 'objeto-prohibido'
  readonly evento = 'prohibited_object' as const
  readonly minimoMs: number
  private readonly umbral: number
  private ultimaInferencia = 0
  private ultimoResultado: { activa: boolean; metadata: Record<string, unknown> } = {
    activa: false,
    metadata: { source: 'mediapipe', available: false }
  }

  constructor(ajustes: AjustesObjeto = {}) {
    this.minimoMs = ajustes.min_duration_ms ?? 500
    this.umbral = ajustes.score_threshold ?? 0.55
  }

  async preparar(): Promise<void> {
    if (detector) return
    if (preparando) return preparando
    preparando = (async () => {
      const { FilesetResolver, ObjectDetector } = await import('@mediapipe/tasks-vision')
      const wasm = await FilesetResolver.forVisionTasks('/mediapipe/wasm')
      detector = await ObjectDetector.createFromOptions(wasm, {
        baseOptions: { modelAssetPath: MODELO },
        runningMode: 'VIDEO',
        scoreThreshold: this.umbral,
        maxResults: 10,
        // No restringir por allowlist: distintas versiones del modelo usan
        // "cell phone" o "mobile phone". Filtramos las etiquetas al observar.
      })
    })()
    try {
      await preparando
    } finally {
      preparando = undefined
    }
  }

  observar({ video, ahoraMs }: Observacion): Veredicto {
    if (!video || !detector || video.readyState < 2 || !video.videoWidth) {
      return { activa: false, metadata: { source: 'mediapipe', available: false } }
    }
    if (ahoraMs - this.ultimaInferencia >= INTERVALO_INFERENCIA_MS) {
      const resultado = detector.detectForVideo(video, performance.now())
      const coincidencia = resultado.detections
        .flatMap((deteccion) => deteccion.categories)
        .filter((categoria) => esCelular(categoria.categoryName || categoria.displayName || ''))
        .sort((a, b) => b.score - a.score)[0]
      this.ultimoResultado = coincidencia
        ? {
            activa: coincidencia.score >= this.umbral,
            metadata: {
              source: 'mediapipe',
              object_name: coincidencia.displayName || coincidencia.categoryName,
              score: coincidencia.score,
              score_threshold: this.umbral
            }
          }
        : { activa: false, metadata: { source: 'mediapipe', available: true } }
      this.ultimaInferencia = ahoraMs
    }
    return this.ultimoResultado
  }

  detener(): void {
    // La instancia se comparte entre sesiones y se mantiene caliente para que
    // no vuelva a descargar ni inicializar el modelo en el siguiente examen.
  }
}
