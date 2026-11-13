import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { MensajeAlMotor, MensajeDelMotor } from './motorProtocolo'
import {
  cargarRemoto,
  LIMITE_RESPUESTA_MS,
  reiniciarMotorRemoto,
  remotoActivo,
  siCaeElRemoto,
  solicitarCuadro,
  tareasDelCiclo,
  ultimaPoseRemota,
  ultimoRostro,
  VIGENCIA_MS
} from './motorRemoto'

/** Un worker de mentira: guarda lo que recibe y contesta cuando se le pide. */
class WorkerFalso {
  onmessage: ((e: MessageEvent<MensajeDelMotor>) => void) | null = null
  onerror: ((e: ErrorEvent) => void) | null = null
  recibidos: MensajeAlMotor[] = []
  terminado = false
  postMessage(m: MensajeAlMotor) {
    this.recibidos.push(m)
    if (m.tipo === 'cargar')
      queueMicrotask(() => this.contestar({ tipo: 'cargado', id: m.id, modelo: m.modelo }))
  }
  terminate() {
    this.terminado = true
  }
  contestar(m: MensajeDelMotor) {
    this.onmessage?.({ data: m } as MessageEvent<MensajeDelMotor>)
  }
  cuadros() {
    return this.recibidos.filter(
      (m): m is Extract<MensajeAlMotor, { tipo: 'cuadro' }> => m.tipo === 'cuadro'
    )
  }
}

const video = { readyState: 4, videoWidth: 960, videoHeight: 540 } as HTMLVideoElement
const bitmap = { close: vi.fn() } as unknown as ImageBitmap
let w: WorkerFalso

beforeEach(() => {
  w = new WorkerFalso()
  reiniciarMotorRemoto(() => w as unknown as Worker)
  vi.stubGlobal('Worker', class {})
  vi.stubGlobal(
    'createImageBitmap',
    vi.fn(async () => bitmap)
  )
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

const esperar = () => new Promise((r) => setTimeout(r, 0))

describe('motor de visión en segundo plano', () => {
  it('carga los modelos en el worker y queda activo', async () => {
    expect(await cargarRemoto('rostro', { numFaces: 2 })).toBe(true)
    expect(await cargarRemoto('objetos', { umbral: 0.55 })).toBe(true)
    expect(remotoActivo()).toBe(true)
    expect(w.recibidos.map((m) => m.tipo === 'cargar' && m.modelo)).toEqual(['rostro', 'objetos'])
  })

  it('sin Worker en el navegador, avisa y se usa el hilo principal', async () => {
    vi.stubGlobal('Worker', undefined)
    reiniciarMotorRemoto(() => w as unknown as Worker)
    expect(await cargarRemoto('rostro')).toBe(false)
    expect(remotoActivo()).toBe(false)
  })

  it('pide un fotograma reducido a 640 px y lo transfiere, no lo copia', async () => {
    await cargarRemoto('rostro')
    solicitarCuadro(video, 1000)
    await esperar()
    expect(createImageBitmap).toHaveBeenCalledWith(
      video,
      expect.objectContaining({ resizeWidth: 640, resizeHeight: 360 })
    )
    expect(w.cuadros()).toHaveLength(1)
  })

  it('varios detectores en el mismo ciclo piden un solo fotograma', async () => {
    await cargarRemoto('rostro')
    solicitarCuadro(video, 1000)
    solicitarCuadro(video, 1000)
    solicitarCuadro(video, 1000)
    await esperar()
    expect(w.cuadros()).toHaveLength(1)
  })

  it('si el worker sigue ocupado, el fotograma siguiente se salta (no se encola)', async () => {
    await cargarRemoto('rostro')
    solicitarCuadro(video, 1000)
    await esperar()
    solicitarCuadro(video, 1125)
    solicitarCuadro(video, 1250)
    await esperar()
    expect(w.cuadros()).toHaveLength(1)
    const id = w.cuadros()[0].id
    w.contestar({
      tipo: 'resultado',
      resultado: {
        id,
        ms: { rostro: 30 },
        rostro: { caras: 1, matriz: null, boca: null, blendshapes: null }
      }
    })
    solicitarCuadro(video, 1375)
    await esperar()
    expect(w.cuadros()).toHaveLength(2)
  })

  it('guarda el resultado con la hora en que se pidió y lo descarta si es viejo', async () => {
    await cargarRemoto('rostro')
    solicitarCuadro(video, 1000)
    await esperar()
    w.contestar({
      tipo: 'resultado',
      resultado: {
        id: w.cuadros()[0].id,
        ms: { rostro: 30 },
        rostro: { caras: 1, matriz: null, boca: null, blendshapes: null }
      }
    })
    expect(ultimoRostro(1500)?.datos.caras).toBe(1)
    expect(ultimoRostro(1000 + VIGENCIA_MS + 1)).toBeUndefined()
  })

  it('si el worker no contesta a tiempo, se termina y los detectores vuelven al hilo principal', async () => {
    vi.useFakeTimers()
    const caida = vi.fn()
    siCaeElRemoto(caida)
    const carga = cargarRemoto('rostro')
    await vi.advanceTimersByTimeAsync(0)
    expect(await carga).toBe(true)
    solicitarCuadro(video, 1000)
    await vi.advanceTimersByTimeAsync(LIMITE_RESPUESTA_MS + 1)
    expect(remotoActivo()).toBe(false)
    expect(w.terminado).toBe(true)
    expect(caida).toHaveBeenCalledWith('el motor no respondió a tiempo')
  })

  it('si el worker lanza un error, también se vuelve al hilo principal', async () => {
    await cargarRemoto('rostro')
    w.onerror?.({ message: 'wasm roto' } as ErrorEvent)
    expect(remotoActivo()).toBe(false)
  })

  it('un modelo que no carga hace caer el worker y el detector usa su motor local', async () => {
    w.postMessage = function (m: MensajeAlMotor) {
      this.recibidos.push(m)
      if (m.tipo === 'cargar')
        queueMicrotask(() => this.contestar({ tipo: 'error', id: m.id, detalle: 'sin modelo' }))
    }
    expect(await cargarRemoto('pose')).toBe(false)
    expect(remotoActivo()).toBe(false)
  })
})

describe('turnos de los modelos pesados', () => {
  it('objetos y pose nunca van en el mismo fotograma', async () => {
    await cargarRemoto('rostro')
    await cargarRemoto('objetos')
    await cargarRemoto('pose')
    for (let t = 0; t < 5000; t += 125) {
      const tareas = tareasDelCiclo(t)
      expect(tareas.objetos && tareas.pose).toBe(false)
    }
  })

  it('la pose atrasada pasa delante de objetos', async () => {
    await cargarRemoto('objetos')
    await cargarRemoto('pose')
    // La pose nunca se midió: lleva más del doble de su intervalo esperando.
    expect(tareasDelCiclo(10_000)).toMatchObject({ pose: true, objetos: false })
  })

  it('la pose medida en el worker se lee por el detector de encuadre', async () => {
    await cargarRemoto('pose')
    solicitarCuadro(video, 2000)
    await esperar()
    const cuadro = w.cuadros()[0]
    expect(cuadro.tareas.pose).toBe(true)
    w.contestar({
      tipo: 'resultado',
      resultado: { id: cuadro.id, ms: { pose: 40 }, pose: [[{ x: 0.5, y: 0.5, visibility: 0.9 }]] }
    })
    expect(ultimaPoseRemota(2100)?.datos[0]).toHaveLength(1)
  })
})
