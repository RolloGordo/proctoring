/**
 * Cliente del motor de visión en un hilo aparte (Jesús Limay).
 *
 * Los detectores siguen siendo síncronos (`observar()` devuelve al momento),
 * pero ya no ejecutan los modelos: piden un fotograma al worker y leen el
 * último resultado que este devolvió. Tres reglas:
 *
 * 1. **Nunca se encola.** Si el worker sigue con el fotograma anterior, el
 *    actual se salta. En un equipo lento se mide menos veces por segundo, pero
 *    la página no se congela ni acumula retraso.
 * 2. **Objetos y pose se turnan**, igual que en el hilo principal (`fotograma.ts`).
 * 3. **Si el worker falla, se vuelve al hilo principal.** Si no arranca, se
 *    cae, o tarda más de `LIMITE_RESPUESTA_MS` en contestar, se termina y los
 *    detectores usan otra vez el motor local. Peor rendimiento, pero sigue
 *    supervisando: es la táctica de disponibilidad de siempre.
 */
import { ANCHO_ROSTRO } from './fotograma'
import type {
  MensajeAlMotor,
  MensajeDelMotor,
  ModeloVision,
  ResultadoCuadro,
  RostroCompacto,
  TareasCuadro
} from './motorProtocolo'
import type { PuntoPose } from './encuadre-core'

/** Mismos ritmos que tenían los detectores en el hilo principal. */
export const INTERVALO_OBJETOS_MS = 250
export const INTERVALO_POSE_MS = 500
/** Un resultado más viejo que esto ya no describe la escena. */
export const VIGENCIA_MS = 2000
/** Sin respuesta en este tiempo, el worker se da por caído. */
export const LIMITE_RESPUESTA_MS = 5000
/** Lo que espera la carga de un modelo antes de rendirse y usar el hilo principal. */
export const LIMITE_CARGA_MS = 30_000

interface Fechado<T> {
  datos: T
  /** `ahoraMs` del ciclo en que se pidió el fotograma. */
  enMs: number
  ms?: number
}

type FabricaWorker = () => Worker

let fabrica: FabricaWorker = () =>
  new Worker(new URL('./motor.worker.ts', import.meta.url), { name: 'motor-vision' })

let worker: Worker | undefined
let caido = false
let siguienteId = 1
const pendientes = new Map<number, { ok: () => void; fallo: (e: Error) => void }>()
const cargados = new Set<ModeloVision>()
let ocupado: { id: number; ahoraMs: number; reloj: ReturnType<typeof setTimeout> } | undefined
let ultimoPedido = Number.NaN
let ultimoObjetos = -Infinity
let ultimaPose = -Infinity
const pedidos = new Map<number, { ahoraMs: number; tareas: TareasCuadro }>()
let rostro: Fechado<RostroCompacto> | undefined
let objetos: Fechado<Array<{ nombre: string; score: number }>> | undefined
let pose: Fechado<PuntoPose[][]> | undefined
const alCaer = new Set<(motivo: string) => void>()

/** Si los detectores deben leer del worker. */
export function remotoActivo(): boolean {
  return worker !== undefined && !caido
}

/** Avisa cuando el worker se cae, para que cada detector cargue su motor local. */
export function siCaeElRemoto(fn: (motivo: string) => void): () => void {
  alCaer.add(fn)
  return () => alCaer.delete(fn)
}

function caer(motivo: string): void {
  if (caido) return
  caido = true
  console.warn('[visión] el motor en segundo plano se detuvo; sigue en el hilo principal:', motivo)
  if (ocupado) clearTimeout(ocupado.reloj)
  ocupado = undefined
  try {
    worker?.terminate()
  } catch {
    // Ya no importa.
  }
  for (const p of pendientes.values()) p.fallo(new Error(motivo))
  pendientes.clear()
  for (const fn of alCaer) fn(motivo)
}

function arrancar(): Worker | undefined {
  if (caido) return undefined
  if (worker) return worker
  if (typeof Worker === 'undefined' || typeof createImageBitmap === 'undefined') {
    caido = true
    return undefined
  }
  try {
    worker = fabrica()
  } catch (fallo) {
    caido = true
    console.warn('[visión] no se pudo crear el motor en segundo plano:', fallo)
    return undefined
  }
  worker.onmessage = (evento: MessageEvent<MensajeDelMotor>) => recibir(evento.data)
  worker.onerror = (evento) => caer(evento.message || 'error del worker')
  return worker
}

function recibir(mensaje: MensajeDelMotor): void {
  if (mensaje.tipo === 'cargado') {
    cargados.add(mensaje.modelo)
    pendientes.get(mensaje.id)?.ok()
    pendientes.delete(mensaje.id)
    return
  }
  if (mensaje.tipo === 'error') {
    const pendiente = pendientes.get(mensaje.id)
    if (pendiente) {
      pendiente.fallo(new Error(mensaje.detalle))
      pendientes.delete(mensaje.id)
      return
    }
    // Un fotograma que falla suelto no tumba el motor: el siguiente se pide igual.
    if (ocupado?.id === mensaje.id) liberar()
    return
  }
  guardar(mensaje.resultado)
}

function liberar(): void {
  if (ocupado) clearTimeout(ocupado.reloj)
  ocupado = undefined
}

function guardar(resultado: ResultadoCuadro): void {
  const pedido = pedidos.get(resultado.id)
  pedidos.delete(resultado.id)
  if (ocupado?.id === resultado.id) liberar()
  if (!pedido) return
  const enMs = pedido.ahoraMs
  if (resultado.rostro) rostro = { datos: resultado.rostro, enMs, ms: resultado.ms.rostro }
  if (resultado.objetos) objetos = { datos: resultado.objetos, enMs, ms: resultado.ms.objetos }
  if (resultado.pose) pose = { datos: resultado.pose, enMs, ms: resultado.ms.pose }
}

/**
 * Carga un modelo en el worker. `true` si quedó listo; `false` si el worker no
 * está disponible, y entonces el detector usa su motor local.
 */
export async function cargarRemoto(
  modelo: ModeloVision,
  opciones: { numFaces?: number; umbral?: number } = {}
): Promise<boolean> {
  const w = arrancar()
  if (!w) return false
  if (cargados.has(modelo) && modelo !== 'rostro') return true
  const id = siguienteId++
  const listo = new Promise<void>((ok, fallo) => pendientes.set(id, { ok, fallo }))
  const reloj = new Promise<never>((_, fallo) =>
    setTimeout(() => fallo(new Error(`el modelo ${modelo} no cargó a tiempo`)), LIMITE_CARGA_MS)
  )
  const mensaje: MensajeAlMotor = { tipo: 'cargar', id, modelo, ...opciones }
  w.postMessage(mensaje)
  try {
    await Promise.race([listo, reloj])
    return true
  } catch (fallo) {
    caer(fallo instanceof Error ? fallo.message : 'carga fallida')
    return false
  }
}

/**
 * Pide al worker el fotograma de este ciclo. Varios detectores lo llaman con
 * el mismo `ahoraMs`: solo el primero cuenta. Si el worker está ocupado, se salta.
 */
export function solicitarCuadro(video: HTMLVideoElement, ahoraMs: number): void {
  if (!remotoActivo() || !worker) return
  if (ultimoPedido === ahoraMs || ocupado) return
  if (video.readyState < 2 || !video.videoWidth || !video.videoHeight) return
  ultimoPedido = ahoraMs
  const tareas = tareasDelCiclo(ahoraMs)
  if (!tareas.rostro && !tareas.objetos && !tareas.pose) return
  if (tareas.objetos) ultimoObjetos = ahoraMs
  if (tareas.pose) ultimaPose = ahoraMs

  const id = siguienteId++
  const reloj = setTimeout(() => caer('el motor no respondió a tiempo'), LIMITE_RESPUESTA_MS)
  ocupado = { id, ahoraMs, reloj }
  pedidos.set(id, { ahoraMs, tareas })
  const ancho = Math.min(ANCHO_ROSTRO, video.videoWidth)
  const alto = Math.round((ancho * video.videoHeight) / video.videoWidth)
  // createImageBitmap reduce el fotograma fuera del hilo de JavaScript, y el
  // bitmap se transfiere (no se copia) al worker.
  createImageBitmap(video, { resizeWidth: ancho, resizeHeight: alto, resizeQuality: 'low' })
    .then((imagen) => {
      if (!worker || caido || ocupado?.id !== id) {
        imagen.close()
        return
      }
      const mensaje: MensajeAlMotor = { tipo: 'cuadro', id, imagen, tareas }
      worker.postMessage(mensaje, [imagen])
    })
    .catch(() => {
      // Un fotograma que no se pudo capturar (la cámara cambió de tamaño, la
      // pestaña se ocultó): se suelta y se pide el siguiente.
      pedidos.delete(id)
      if (ocupado?.id === id) liberar()
    })
}

/**
 * Qué modelos tocan en este ciclo. Objetos y pose nunca van juntos (turno
 * pesado). Si la pose lleva el doble de su intervalo sin turno, va antes que
 * objetos: en un equipo lento el worker siempre llega con objetos «vencido» y,
 * sin esta regla, la pose casi no se medía (comprobado: 1 vez por segundo).
 */
export function tareasDelCiclo(ahoraMs: number): TareasCuadro {
  const poseVencida = cargados.has('pose') && ahoraMs - ultimaPose >= INTERVALO_POSE_MS
  const poseAtrasada = cargados.has('pose') && ahoraMs - ultimaPose >= 2 * INTERVALO_POSE_MS
  const objetosVencido = cargados.has('objetos') && ahoraMs - ultimoObjetos >= INTERVALO_OBJETOS_MS
  const pose = poseAtrasada || (poseVencida && !objetosVencido)
  return { rostro: cargados.has('rostro'), objetos: objetosVencido && !pose, pose }
}

function vigente<T>(valor: Fechado<T> | undefined, ahoraMs: number): Fechado<T> | undefined {
  return valor && ahoraMs - valor.enMs <= VIGENCIA_MS ? valor : undefined
}

export const ultimoRostro = (ahoraMs: number) => vigente(rostro, ahoraMs)
export const ultimosObjetos = (ahoraMs: number) => vigente(objetos, ahoraMs)
export const ultimaPoseRemota = (ahoraMs: number) => vigente(pose, ahoraMs)

/** Para pruebas: otro constructor de worker y estado limpio. */
export function reiniciarMotorRemoto(nuevaFabrica?: FabricaWorker): void {
  try {
    worker?.terminate()
  } catch {
    // nada
  }
  worker = undefined
  caido = false
  cargados.clear()
  pendientes.clear()
  pedidos.clear()
  if (ocupado) clearTimeout(ocupado.reloj)
  ocupado = undefined
  ultimoPedido = Number.NaN
  ultimoObjetos = -Infinity
  ultimaPose = -Infinity
  rostro = objetos = pose = undefined
  alCaer.clear()
  if (nuevaFabrica) fabrica = nuevaFabrica
}
