import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ColaDeGuardado } from './cola-de-guardado'
import type { NewAnswer } from './api'

const respuesta = (id: string, texto = 'a'): NewAnswer => ({
  question_id: id,
  text_answer: texto
})

/** Un envío que se puede resolver o rechazar desde la prueba. */
function enviosControlados() {
  const lotes: NewAnswer[][] = []
  let resolver: (() => void) | undefined
  let rechazar: ((fallo: unknown) => void) | undefined

  const enviar = (lote: NewAnswer[]): Promise<void> => {
    lotes.push(lote)
    return new Promise<void>((ok, mal) => {
      resolver = ok
      rechazar = mal
    })
  }

  return {
    lotes,
    enviar,
    completar: () => resolver?.(),
    fallar: (fallo: unknown = new Error('sin red')) => rechazar?.(fallo)
  }
}

describe('la cola que guarda las respuestas', () => {
  let estados: string[]
  let fallos: unknown[]

  beforeEach(() => {
    vi.useFakeTimers()
    estados = []
    fallos = []
  })

  function cola(enviar: (lote: NewAnswer[]) => Promise<void>, esperaMs = 500): ColaDeGuardado {
    return new ColaDeGuardado(
      enviar,
      (estado) => estados.push(estado),
      (fallo) => fallos.push(fallo),
      esperaMs
    )
  }

  it('agrupa lo escrito en un solo envío', async () => {
    // Sin esto, cada campo que pierde el foco es una petición, y el orden de
    // llegada no está garantizado.
    const lotes: NewAnswer[][] = []
    const c = cola(async (lote) => {
      lotes.push(lote)
    })

    c.encolar(respuesta('p1'))
    c.encolar(respuesta('p2'))
    await vi.advanceTimersByTimeAsync(600)

    expect(lotes).toHaveLength(1)
    expect(lotes[0]).toHaveLength(2)
  })

  it('de una misma pregunta vale la última respuesta', async () => {
    const lotes: NewAnswer[][] = []
    const c = cola(async (lote) => {
      lotes.push(lote)
    })

    c.encolar(respuesta('p1', 'primera'))
    c.encolar(respuesta('p1', 'definitiva'))
    await vi.advanceTimersByTimeAsync(600)

    expect(lotes[0]).toEqual([respuesta('p1', 'definitiva')])
  })

  it('vaciar espera al envío que ya está en vuelo', async () => {
    // **El fallo que perdía la última respuesta en cada examen.** Al entregar,
    // la cola veía un envío en curso, se rendía y decía que no se había
    // guardado, justo cuando sí se estaba guardando.
    const envios = enviosControlados()
    const c = cola(envios.enviar)

    c.encolar(respuesta('p1'))
    await vi.advanceTimersByTimeAsync(600) // arranca el envío, queda en vuelo

    const vaciado = c.vaciar()
    envios.completar()

    await expect(vaciado).resolves.toBe(true)
    expect(c.sinGuardar).toBe(0)
  })

  it('vaciar manda lo que se escribió mientras otro envío estaba en vuelo', async () => {
    const envios = enviosControlados()
    const c = cola(envios.enviar)

    c.encolar(respuesta('p1'))
    await vi.advanceTimersByTimeAsync(600)
    c.encolar(respuesta('p2')) // llega con el primero todavía en vuelo

    const vaciado = c.vaciar()
    envios.completar() // termina el primero
    await vi.advanceTimersByTimeAsync(0)
    envios.completar() // termina el segundo

    await expect(vaciado).resolves.toBe(true)
    expect(envios.lotes).toHaveLength(2)
    expect(envios.lotes[1]).toEqual([respuesta('p2')])
  })

  it('si el envío falla, la respuesta vuelve a la cola y no se pierde', async () => {
    const envios = enviosControlados()
    const c = cola(envios.enviar)

    c.encolar(respuesta('p1'))
    const enviado = c.enviar()
    envios.fallar()
    await enviado

    expect(c.sinGuardar).toBe(1)
    expect(estados).toContain('error')
    expect(fallos).toHaveLength(1)
  })

  it('un fallo no pisa lo que el estudiante escribió después', async () => {
    // Si cambió de opinión mientras se enviaba, vale lo nuevo, no lo que
    // rebotó.
    const envios = enviosControlados()
    const c = cola(envios.enviar)

    c.encolar(respuesta('p1', 'vieja'))
    const enviado = c.enviar()
    c.encolar(respuesta('p1', 'nueva'))
    envios.fallar()
    await enviado

    const siguiente: NewAnswer[][] = []
    const c2 = cola(async (lote) => {
      siguiente.push(lote)
    })
    void c2
    expect(c.sinGuardar).toBe(1)
  })

  it('vaciar sin nada pendiente dice que sí, sin enviar', async () => {
    const lotes: NewAnswer[][] = []
    const c = cola(async (lote) => {
      lotes.push(lote)
    })

    await expect(c.vaciar()).resolves.toBe(true)
    expect(lotes).toHaveLength(0)
  })

  it('con la red caída, vaciar termina y dice que no', async () => {
    // Entregar no puede quedarse esperando para siempre: se le pregunta al
    // estudiante y él decide.
    const c = cola(async () => {
      throw new Error('sin red')
    })

    c.encolar(respuesta('p1'))

    await expect(c.vaciar()).resolves.toBe(false)
    expect(c.sinGuardar).toBe(1)
  })

  it('destruirlo no deja temporizadores sueltos', () => {
    const c = cola(async () => {})
    const antes = vi.getTimerCount()
    c.encolar(respuesta('p1'))

    // Primero se comprueba la premisa: encolar deja un temporizador. Sin esto,
    // la prueba pasaria aunque `encolar` no programara nada.
    expect(vi.getTimerCount()).toBe(antes + 1)

    c.destruir()

    expect(vi.getTimerCount()).toBe(antes)
  })
})
