/**
 * Motor de visión en un hilo aparte (Jesús Limay — rendimiento de cámara).
 *
 * Los tres modelos de MediaPipe (rostro, objetos y pose) corrían en el hilo
 * principal del navegador, el mismo que dibuja la página. Medido en Chromium
 * con los modelos reales, ese hilo pasaba el 86 % del tiempo ocupado y la
 * interfaz bajaba a 18 fotogramas por segundo durante el examen.
 *
 * Aquí corren los mismos modelos, con los mismos archivos locales de
 * `/mediapipe/`, pero en un Web Worker: la página sigue respondiendo mientras
 * se calcula. Lo que vuelve es solo lo que usan los detectores, en un formato
 * compacto (`ResultadoCuadro`), nunca la imagen.
 *
 * Es un worker **clásico**, no de módulo: MediaPipe carga su WASM con
 * `importScripts`, que los workers de módulo no tienen (comprobado: falla con
 * «self.import is not a function»). Vite genera los workers clásicos por
 * defecto, así que basta con `new Worker(new URL(...))` sin `type: 'module'`.
 */
// Importación estática a propósito: un worker clásico se empaqueta en un solo
// archivo (IIFE) y no admite import() dinámico.
import {
  FaceLandmarker,
  FilesetResolver,
  ObjectDetector,
  PoseLandmarker
} from '@mediapipe/tasks-vision'
import type { MensajeAlMotor, MensajeDelMotor, ResultadoCuadro } from './motorProtocolo'
import { compactarRostro } from './vision-core'

const WASM = '/mediapipe/wasm'
let cargaWasm: ReturnType<typeof cargarWasm> | undefined
let rostro: FaceLandmarker | undefined
let objetos: ObjectDetector | undefined
let pose: PoseLandmarker | undefined
let capacidadRostros = 0

async function cargarWasm() {
  const archivos = await FilesetResolver.forVisionTasks(WASM)
  return { archivos }
}

function wasm() {
  cargaWasm ??= cargarWasm()
  return cargaWasm
}

function responder(mensaje: MensajeDelMotor): void {
  ;(self as unknown as Worker).postMessage(mensaje)
}

async function cargar(mensaje: Extract<MensajeAlMotor, { tipo: 'cargar' }>): Promise<void> {
  const { archivos } = await wasm()
  if (mensaje.modelo === 'rostro') {
    const requeridos = Math.max(1, mensaje.numFaces ?? 2)
    if (rostro && capacidadRostros >= requeridos) return
    if (rostro) {
      await rostro.setOptions({ numFaces: requeridos })
    } else {
      rostro = await FaceLandmarker.createFromOptions(archivos, {
        baseOptions: { modelAssetPath: '/mediapipe/face_landmarker.task' },
        numFaces: requeridos,
        outputFacialTransformationMatrixes: true,
        outputFaceBlendshapes: true,
        runningMode: 'VIDEO'
      })
    }
    capacidadRostros = requeridos
  } else if (mensaje.modelo === 'objetos') {
    objetos ??= await ObjectDetector.createFromOptions(archivos, {
      baseOptions: { modelAssetPath: '/mediapipe/efficientdet_lite0.tflite' },
      runningMode: 'VIDEO',
      scoreThreshold: mensaje.umbral ?? 0.55,
      maxResults: 10
    })
  } else {
    pose ??= await PoseLandmarker.createFromOptions(archivos, {
      baseOptions: { modelAssetPath: '/mediapipe/pose_landmarker_lite.task' },
      runningMode: 'VIDEO',
      numPoses: 1
    })
  }
}

function procesar(mensaje: Extract<MensajeAlMotor, { tipo: 'cuadro' }>): ResultadoCuadro {
  const { imagen, tareas, id } = mensaje
  const salida: ResultadoCuadro = { id, ms: {} }
  try {
    if (tareas.rostro && rostro) {
      const t = performance.now()
      const r = rostro.detectForVideo(imagen, t)
      salida.ms.rostro = performance.now() - t
      // La misma función que usa el hilo principal: mismas reglas, mismo resultado.
      const compacto = compactarRostro(r)
      salida.rostro = { ...compacto, matriz: compacto.matriz ? Array.from(compacto.matriz) : null }
    }
    if (tareas.objetos && objetos) {
      const t = performance.now()
      const r = objetos.detectForVideo(imagen, t)
      salida.ms.objetos = performance.now() - t
      salida.objetos = r.detections.flatMap((d) =>
        d.categories.map((c) => ({ nombre: c.categoryName || c.displayName || '', score: c.score }))
      )
    }
    if (tareas.pose && pose) {
      const t = performance.now()
      const r = pose.detectForVideo(imagen, t)
      salida.ms.pose = performance.now() - t
      salida.pose = r.landmarks.map((puntos) =>
        puntos.map((p) => ({ x: p.x, y: p.y, visibility: p.visibility }))
      )
    }
  } finally {
    // El ImageBitmap llegó transferido: liberarlo ya, o se acumulan en memoria.
    imagen.close()
  }
  return salida
}

self.onmessage = async (evento: MessageEvent<MensajeAlMotor>) => {
  const mensaje = evento.data
  try {
    if (mensaje.tipo === 'cargar') {
      await cargar(mensaje)
      responder({ tipo: 'cargado', modelo: mensaje.modelo, id: mensaje.id })
    } else {
      responder({ tipo: 'resultado', resultado: procesar(mensaje) })
    }
  } catch (fallo) {
    responder({
      tipo: 'error',
      id: mensaje.id,
      detalle: fallo instanceof Error ? fallo.message.slice(0, 200) : String(fallo).slice(0, 200)
    })
  }
}
