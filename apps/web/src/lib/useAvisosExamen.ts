import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Alert, type Participant } from './api'
import { alertasSinVer, esperandoAdmision, guardarVistas, leerVistas } from './avisos-examen'
import { supabase } from './supabase'

/** Si Realtime se cae, se pregunta igual cada tanto para que el número no se congele. */
const SONDEO_MS = 30_000

/**
 * Las dos cuentas de las pestañas del examen, vivas desde cualquier pestaña.
 *
 * Escucha `session_participants` y `alerts` por Realtime, como la sala de
 * espera y la actividad, pero por su propio canal: esas pantallas abren y
 * cierran el suyo al cambiar de pestaña, y esta cuenta tiene que seguir.
 *
 * `mirandoActividad`: mientras el docente está en la pestaña de actividad,
 * lo que hay y lo que va llegando queda visto. Se marca en los callbacks (al
 * cargar, al llegar una alerta, al abrir la pestaña), no en un efecto.
 */
export function useAvisosExamen(
  sessionId: string,
  token: string | undefined,
  mirandoActividad: boolean
): { esperando: number; alertasNuevas: number; marcarVistas: () => void } {
  const [participantes, setParticipantes] = useState<Participant[]>([])
  const [alertas, setAlertas] = useState<Alert[]>([])
  const [vistas, setVistas] = useState<{ sessionId: string; ids: Set<string> }>(() => ({
    sessionId,
    ids: leerVistas(sessionId)
  }))
  const idsVistos = vistas.sessionId === sessionId ? vistas.ids : leerVistas(sessionId)

  const mirando = useRef(mirandoActividad)
  useEffect(() => {
    mirando.current = mirandoActividad
  }, [mirandoActividad])

  const marcar = useCallback(
    (nuevas: readonly Alert[]) => {
      setVistas((previo) => {
        const base = previo.sessionId === sessionId ? previo.ids : leerVistas(sessionId)
        if (nuevas.every((a) => base.has(a.id))) return previo
        const ids = new Set([...base, ...nuevas.map((a) => a.id)])
        guardarVistas(sessionId, ids)
        return { sessionId, ids }
      })
    },
    [sessionId]
  )

  const cargarParticipantes = useCallback(() => {
    api.listParticipants(sessionId, token).then(setParticipantes).catch(() => undefined)
  }, [sessionId, token])

  const cargarAlertas = useCallback(() => {
    api
      .listAlerts(sessionId, token)
      .then((datos) => {
        setAlertas(datos)
        if (mirando.current) marcar(datos)
      })
      .catch(() => undefined)
  }, [sessionId, token, marcar])

  useEffect(() => {
    if (!sessionId) return
    cargarParticipantes()
    cargarAlertas()
    const sondeo = setInterval(() => {
      cargarParticipantes()
      cargarAlertas()
    }, SONDEO_MS)
    return () => clearInterval(sondeo)
  }, [sessionId, cargarParticipantes, cargarAlertas])

  useEffect(() => {
    if (!supabase || !sessionId) return
    const cliente = supabase
    const canal = cliente
      .channel(`avisos-${sessionId}`)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'session_participants', filter: `session_id=eq.${sessionId}` },
        cargarParticipantes
      )
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'alerts', filter: `session_id=eq.${sessionId}` },
        (mensaje) => {
          const nueva = mensaje.new as Alert
          setAlertas((previas) =>
            previas.some((a) => a.id === nueva.id) ? previas : [...previas, nueva]
          )
          if (mirando.current) marcar([nueva])
        }
      )
      .subscribe()
    return () => {
      void cliente.removeChannel(canal)
    }
  }, [sessionId, cargarParticipantes, marcar])

  const marcarVistas = useCallback(() => marcar(alertas), [marcar, alertas])

  return {
    esperando: esperandoAdmision(participantes),
    alertasNuevas: mirandoActividad ? 0 : alertasSinVer(alertas, idsVistos),
    marcarVistas
  }
}
