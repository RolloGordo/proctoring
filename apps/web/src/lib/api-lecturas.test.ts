import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'

afterEach(() => vi.unstubAllGlobals())

describe('lecturas compartidas', () => {
  it('dos lecturas iguales a la vez hacen una sola petición, y cada una recibe su copia', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify([{ id: 'p1' }]), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const [a, b] = await Promise.all([api.listParticipants('s1', 't'), api.listParticipants('s1', 't')])

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(a).toEqual(b)
    expect(a).not.toBe(b)
  })

  it('con otro token no se comparte', async () => {
    const fetchMock = vi.fn(async () => new Response('[]', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await Promise.all([api.listParticipants('s1', 't1'), api.listParticipants('s1', 't2')])

    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('una vez terminada, la siguiente lectura vuelve a preguntar', async () => {
    const fetchMock = vi.fn(async () => new Response('[]', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await api.listParticipants('s1', 't')
    await api.listParticipants('s1', 't')

    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
