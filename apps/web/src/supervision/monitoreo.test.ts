import { beforeEach, describe, expect, it, vi } from 'vitest'

// `capturarFotogramaBase64` necesita `document`, y estas pruebas corren en node.
// Lo que se prueba aquí no es la captura, es **cuándo** se captura.
vi.mock('./camara', () => ({
  capturarFotogramaBase64: vi.fn(() => 'JPEG')
}))

import type { RealtimeChannel, SupabaseClient } from '@supabase/supabase-js'
import {
  EVENTO_FOTOGRAMA,
  nombreCanal,
  periodoMs,
  publicarFotogramas,
  verFotogramas
} from './monitoreo'

const SESION = '11111111-1111-1111-1111-111111111111'
const ESTUDIANTE = '22222222-2222-2222-2222-222222222222'
const DOCENTE = '33333333-3333-3333-3333-333333333333'

type Escucha = (carga: unknown) => void

/** Un canal de Realtime de mentira, con lo justo para observar el contrato. */
class CanalFalso {
  readonly enviados: Array<Record<string, unknown>> = []
  readonly seguimientos: unknown[] = []
  readonly escuchas = new Map<string, Escucha[]>()
  presencia: Record<string, unknown[]> = {}
  private aviso?: (estado: string) => void

  on(tipo: string, filtro: { event: string }, escucha: Escucha): this {
    const clave = `${tipo}:${filtro.event}`
    const lista = this.escuchas.get(clave) ?? []
    lista.push(escucha)
    this.escuchas.set(clave, lista)
    return this
  }

  subscribe(aviso: (estado: string) => void): this {
    this.aviso = aviso
    return this
  }

  presenceState(): Record<string, unknown[]> {
    return this.presencia
  }

  async track(datos: unknown): Promise<'ok'> {
    this.seguimientos.push(datos)
    return 'ok'
  }

  async send(mensaje: Record<string, unknown>): Promise<'ok'> {
    this.enviados.push(mensaje)
    return 'ok'
  }

  // --- lo que usa la prueba para simular al servidor ---

  conectar(estado = 'SUBSCRIBED'): void {
    this.aviso?.(estado)
  }

  /** Simula que alguien entra o sale del canal. */
  presentes(claves: string[]): void {
    this.presencia = Object.fromEntries(claves.map((c) => [c, [{}]]))
    for (const escucha of this.escuchas.get('presence:sync') ?? []) escucha({})
  }

  recibir(evento: string, payload: unknown): void {
    for (const escucha of this.escuchas.get(`broadcast:${evento}`) ?? []) escucha({ payload })
  }
}

function clienteFalso(): { cliente: SupabaseClient; canal: CanalFalso; opciones: unknown[] } {
  const canal = new CanalFalso()
  const opciones: unknown[] = []
  const cliente = {
    channel: (_nombre: string, config: unknown) => {
      opciones.push(config)
      return canal as unknown as RealtimeChannel
    },
    removeChannel: vi.fn(async () => 'ok' as const)
  }
  return { cliente: cliente as unknown as SupabaseClient, canal, opciones }
}

beforeEach(() => {
  vi.useFakeTimers()
})

describe('el nombre del canal', () => {
  // La misma expresión que comprueba `private.monitoring_topic_session()` en
  // `20261009180000_live_monitoring_channel.sql`. Si alguien cambia el formato
  // del canal, RLS lo rechazaría y el docente vería «no se pudo abrir el
  // canal» sin más explicación. Esta prueba es lo que lo convierte en un fallo
  // con nombre.
  const COMO_EN_LA_MIGRACION = /^monitoreo:[0-9a-fA-F-]{36}:[0-9a-fA-F-]{36}$/

  it('tiene la forma que la política acepta', () => {
    expect(nombreCanal(SESION, ESTUDIANTE)).toMatch(COMO_EN_LA_MIGRACION)
  })

  it('lleva el examen y el estudiante, en ese orden', () => {
    expect(nombreCanal(SESION, ESTUDIANTE)).toBe(`monitoreo:${SESION}:${ESTUDIANTE}`)
  })
})

describe('el canal es privado', () => {
  // Sin `private: true` Realtime no consulta RLS, y entonces cualquiera que
  // adivine el nombre del canal ve la cámara. Es una sola línea y no falla de
  // forma visible: el monitoreo seguiría funcionando igual de bien.
  it('al publicar', () => {
    const { cliente, opciones } = clienteFalso()
    publicarFotogramas({ cliente, sessionId: SESION, studentId: ESTUDIANTE, video: video() })

    expect(opciones[0]).toMatchObject({ config: { private: true } })
  })

  it('al mirar', () => {
    const { cliente, opciones } = clienteFalso()
    verFotogramas({
      cliente,
      sessionId: SESION,
      studentId: ESTUDIANTE,
      teacherId: DOCENTE,
      onFotograma: () => undefined
    })

    expect(opciones[0]).toMatchObject({ config: { private: true } })
  })
})

describe('si nadie mira, no se envía', () => {
  it('estar conectado no basta para empezar a enviar', () => {
    const { cliente, canal } = clienteFalso()
    publicarFotogramas({ cliente, sessionId: SESION, studentId: ESTUDIANTE, video: video() })

    canal.conectar()
    canal.presentes([ESTUDIANTE])
    vi.advanceTimersByTime(10_000)

    expect(canal.enviados).toEqual([])
  })

  it('empieza cuando el docente entra al canal', () => {
    const { cliente, canal } = clienteFalso()
    publicarFotogramas({ cliente, sessionId: SESION, studentId: ESTUDIANTE, video: video() })

    canal.conectar()
    canal.presentes([ESTUDIANTE, DOCENTE])
    vi.advanceTimersByTime(3000)

    expect(canal.enviados).toHaveLength(3)
    expect(canal.enviados[0]).toMatchObject({
      type: 'broadcast',
      event: EVENTO_FOTOGRAMA,
      payload: { jpeg: 'JPEG' }
    })
  })

  it('deja de enviar cuando el docente se va', () => {
    const { cliente, canal } = clienteFalso()
    publicarFotogramas({ cliente, sessionId: SESION, studentId: ESTUDIANTE, video: video() })

    canal.conectar()
    canal.presentes([ESTUDIANTE, DOCENTE])
    vi.advanceTimersByTime(2000)
    const mientrasMiraba = canal.enviados.length

    canal.presentes([ESTUDIANTE])
    vi.advanceTimersByTime(10_000)

    expect(mientrasMiraba).toBeGreaterThan(0)
    expect(canal.enviados).toHaveLength(mientrasMiraba)
  })

  it('avisa al estudiante de que lo están mirando, y de que dejaron', () => {
    const { cliente, canal } = clienteFalso()
    const avisos: boolean[] = []
    publicarFotogramas({
      cliente,
      sessionId: SESION,
      studentId: ESTUDIANTE,
      video: video(),
      onObservado: (o) => avisos.push(o)
    })

    canal.conectar()
    canal.presentes([ESTUDIANTE])
    canal.presentes([ESTUDIANTE, DOCENTE])
    canal.presentes([ESTUDIANTE, DOCENTE])
    canal.presentes([ESTUDIANTE])

    // Solo los cambios: la pantalla no tiene por qué repintarse en cada sync.
    expect(avisos).toEqual([true, false])
  })

  it('al detener no queda el temporizador corriendo', async () => {
    const { cliente, canal } = clienteFalso()
    const envio = publicarFotogramas({
      cliente,
      sessionId: SESION,
      studentId: ESTUDIANTE,
      video: video()
    })

    canal.conectar()
    canal.presentes([ESTUDIANTE, DOCENTE])
    vi.advanceTimersByTime(1000)
    await envio.detener()
    const alDetener = canal.enviados.length

    vi.advanceTimersByTime(10_000)

    expect(canal.enviados).toHaveLength(alDetener)
  })
})

describe('mirar', () => {
  it('entrega el fotograma que llega', () => {
    const { cliente, canal } = clienteFalso()
    const recibidos: unknown[] = []
    verFotogramas({
      cliente,
      sessionId: SESION,
      studentId: ESTUDIANTE,
      teacherId: DOCENTE,
      onFotograma: (f) => recibidos.push(f)
    })

    canal.conectar()
    canal.recibir(EVENTO_FOTOGRAMA, { jpeg: 'JPEG', capturadoEn: 1700000000000 })

    expect(recibidos).toEqual([{ jpeg: 'JPEG', capturadoEn: 1700000000000 }])
  })

  it.each([
    ['sin jpeg', { capturadoEn: 1 }],
    ['con jpeg vacío', { jpeg: '', capturadoEn: 1 }],
    ['con jpeg que no es texto', { jpeg: 42 }],
    ['sin carga', undefined]
  ])('descarta un mensaje %s', (_caso, payload) => {
    const { cliente, canal } = clienteFalso()
    const recibidos: unknown[] = []
    verFotogramas({
      cliente,
      sessionId: SESION,
      studentId: ESTUDIANTE,
      teacherId: DOCENTE,
      onFotograma: (f) => recibidos.push(f)
    })

    canal.conectar()
    canal.recibir(EVENTO_FOTOGRAMA, payload)

    // El mensaje viene de otro cliente y acaba en el `src` de una imagen.
    expect(recibidos).toEqual([])
  })

  it('el docente se anuncia, para que el estudiante empiece a enviar', () => {
    const { cliente, canal } = clienteFalso()
    verFotogramas({
      cliente,
      sessionId: SESION,
      studentId: ESTUDIANTE,
      teacherId: DOCENTE,
      onFotograma: () => undefined
    })

    canal.conectar()

    expect(canal.seguimientos).toEqual([{ rol: 'docente' }])
  })

  it('distingue que el estudiante esté en el canal', () => {
    const { cliente, canal } = clienteFalso()
    const conexiones: boolean[] = []
    verFotogramas({
      cliente,
      sessionId: SESION,
      studentId: ESTUDIANTE,
      teacherId: DOCENTE,
      onFotograma: () => undefined,
      onConectado: (c) => conexiones.push(c)
    })

    canal.conectar()
    // Solo el docente: nadie más en el canal.
    canal.presentes([DOCENTE])
    canal.presentes([DOCENTE, ESTUDIANTE])

    expect(conexiones).toEqual([true])
  })

  it('un canal que no abre se reporta como error', () => {
    const { cliente, canal } = clienteFalso()
    const estados: string[] = []
    verFotogramas({
      cliente,
      sessionId: SESION,
      studentId: ESTUDIANTE,
      teacherId: DOCENTE,
      onFotograma: () => undefined,
      onEstado: (e) => estados.push(e)
    })

    canal.conectar('CHANNEL_ERROR')

    expect(estados).toEqual(['conectando', 'error'])
  })
})

describe('el ritmo', () => {
  it('un fotograma por segundo por defecto', () => {
    expect(periodoMs(undefined)).toBe(1000)
  })

  it.each([0, -1, 60, Number.NaN])('un fps de %s cae al valor por defecto', (fps) => {
    // Los ajustes vienen de `session_modules.settings`, que es jsonb: nada
    // impide que ahí haya un cero. Con `1000 / 0` el intervalo sería infinito y
    // el monitoreo quedaría apagado sin decir nada.
    expect(periodoMs(fps)).toBe(1000)
  })

  it('respeta un fps razonable', () => {
    expect(periodoMs(2)).toBe(500)
  })
})

function video(): HTMLVideoElement {
  return {} as HTMLVideoElement
}
