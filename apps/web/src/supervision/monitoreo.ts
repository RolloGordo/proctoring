/**
 * Monitoreo en vivo: la cámara del estudiante en la pantalla del docente.
 *
 * **Este archivo es el contrato.** Las dos puntas —quien publica y quien mira—
 * salen de aquí, para que el nombre del canal, el nombre del evento y la forma
 * del mensaje no puedan desfasarse entre el examen y el panel.
 *
 * Tres reglas que lo definen, y que no son adorno:
 *
 * 1. **No se graba.** El fotograma viaja por Realtime y se pierde. No pasa por
 *    la API, no entra en Storage y no queda en ninguna tabla. Lo que sí se
 *    conserva al terminar el examen son las capturas de los eventos que fueron
 *    alerta y los fragmentos de audio marcados, que tienen su propio camino.
 * 2. **Si nadie mira, no se envía.** El estudiante se entera por presencia de
 *    que el docente entró al canal, y solo entonces empieza a capturar.
 *    Mientras nadie mira, el fotograma no sale de su equipo. Eso es más honesto
 *    que «sale siempre pero no se guarda», y de paso no gasta la cuota de
 *    Realtime.
 * 3. **Un canal por estudiante.** Con un canal por sesión, para publicar su
 *    fotograma el estudiante tendría que poder unirse al canal común, y unirse
 *    implica poder recibir: vería la cámara de sus compañeros.
 *
 * La autorización no está aquí, está en RLS sobre `realtime.messages`
 * (`supabase/migrations/20261009180000_live_monitoring_channel.sql`). Este
 * módulo **tiene** que abrir el canal con `private: true`: sin eso Realtime no
 * comprueba nada y cualquiera que adivine el nombre del canal vería la cámara.
 */

import type { RealtimeChannel, SupabaseClient } from '@supabase/supabase-js'
import { capturarFotogramaBase64 } from './camara'

/** Prefijo del canal. La migración comprueba esta misma forma. */
export const PREFIJO_CANAL = 'monitoreo'

/** El evento de broadcast que lleva el fotograma. */
export const EVENTO_FOTOGRAMA = 'fotograma'

/** `monitoreo:<session_id>:<student_id>` */
export function nombreCanal(sessionId: string, studentId: string): string {
  return `${PREFIJO_CANAL}:${sessionId}:${studentId}`
}

/** Lo que viaja en cada mensaje. */
export interface Fotograma {
  /** JPEG en base64, sin el prefijo `data:`. */
  jpeg: string
  /** Hora de captura en el equipo del estudiante (epoch ms). */
  capturadoEn: number
}

/** `session_modules.settings` del módulo `live_monitoring`. */
export interface AjustesMonitoreo {
  /** Fotogramas por segundo. Uno basta para ver quién está y qué hace. */
  fps?: number
  /** Ancho en píxeles del fotograma enviado. */
  width?: number
  /** Calidad JPEG, de 0 a 1. */
  quality?: number
}

export const AJUSTES_POR_DEFECTO: Required<AjustesMonitoreo> = {
  fps: 1,
  width: 320,
  quality: 0.5
}

/** Un fotograma cada tanto. Un `fps` fuera de rango cae al valor por defecto. */
export function periodoMs(fps: number | undefined): number {
  const valor = typeof fps === 'number' && fps > 0 && fps <= 10 ? fps : AJUSTES_POR_DEFECTO.fps
  return Math.round(1000 / valor)
}

/** El rol con el que cada uno se anuncia en el canal. */
type Rol = 'estudiante' | 'docente'

function canalPrivado(
  cliente: SupabaseClient,
  sessionId: string,
  studentId: string,
  clave: string
): RealtimeChannel {
  return cliente.channel(nombreCanal(sessionId, studentId), {
    config: {
      // Sin esto RLS no se aplica. Es la línea que sostiene toda la migración.
      private: true,
      // `self: false` para no recibir de vuelta el propio fotograma.
      broadcast: { self: false },
      presence: { key: clave, enabled: true }
    }
  })
}

/** Si en el canal hay alguien que no sea uno mismo. */
function hayOtros(canal: RealtimeChannel, propia: string): boolean {
  return Object.keys(canal.presenceState()).some((clave) => clave !== propia)
}

export interface Publicacion {
  detener: () => Promise<void>
}

export interface OpcionesPublicar {
  cliente: SupabaseClient
  sessionId: string
  studentId: string
  /** El mismo `<video>` que ya usan los detectores: una sola cámara abierta. */
  video: HTMLVideoElement
  ajustes?: AjustesMonitoreo
  /**
   * Avisa cuando el docente entra o sale del canal.
   *
   * El examen lo muestra: el estudiante tiene derecho a saber cuándo lo están
   * mirando, y es la otra mitad del consentimiento.
   */
  onObservado?: (observado: boolean) => void
}

/**
 * El lado del estudiante: publica fotogramas mientras alguien mire.
 *
 * No abre la cámara ni pide permisos: recibe el `<video>` que la supervisión ya
 * tiene encendido. Si el módulo está activo pero no hay cámara, no hay nada que
 * publicar y esto no se llama.
 */
export function publicarFotogramas({
  cliente,
  sessionId,
  studentId,
  video,
  ajustes = {},
  onObservado
}: OpcionesPublicar): Publicacion {
  const canal = canalPrivado(cliente, sessionId, studentId, studentId)
  const ancho = ajustes.width ?? AJUSTES_POR_DEFECTO.width
  const calidad = ajustes.quality ?? AJUSTES_POR_DEFECTO.quality

  let observado = false
  let temporizador: ReturnType<typeof setInterval> | undefined

  function revisarPresencia(): void {
    const ahora = hayOtros(canal, studentId)
    if (ahora === observado) return
    observado = ahora
    onObservado?.(ahora)
  }

  function enviar(): void {
    // La condición se mira en cada tic y no solo al cambiar la presencia: si el
    // docente cierra la pestaña de golpe, el `leave` puede tardar, y este
    // guardia es lo que impide seguir mandando a nadie.
    if (!observado) return
    const jpeg = capturarFotogramaBase64(video, { ancho, calidad })
    if (!jpeg) return
    // Sin esperar la respuesta: un envío que no llega se descarta. Un fotograma
    // viejo no vale nada, y reintentarlo solo retrasaría el siguiente.
    void canal.send({
      type: 'broadcast',
      event: EVENTO_FOTOGRAMA,
      payload: { jpeg, capturadoEn: Date.now() } satisfies Fotograma
    })
  }

  canal
    .on('presence', { event: 'sync' }, revisarPresencia)
    .on('presence', { event: 'join' }, revisarPresencia)
    .on('presence', { event: 'leave' }, revisarPresencia)
    .subscribe((estado) => {
      if (estado !== 'SUBSCRIBED') return
      // Anunciarse es lo que le permite al docente distinguir «no está
      // conectado» de «está conectado pero la cámara falló».
      void canal.track({ rol: 'estudiante' satisfies Rol })
      revisarPresencia()
      temporizador ??= setInterval(enviar, periodoMs(ajustes.fps))
    })

  return {
    detener: async () => {
      clearInterval(temporizador)
      temporizador = undefined
      await cliente.removeChannel(canal)
    }
  }
}

export type EstadoVista = 'conectando' | 'mirando' | 'error'

export interface OpcionesVer {
  cliente: SupabaseClient
  sessionId: string
  studentId: string
  /** Quién mira. Es su clave de presencia, y hace falta para no contarse. */
  teacherId: string
  onFotograma: (fotograma: Fotograma) => void
  /** Si el estudiante está en el canal. Distinto de que llegue imagen. */
  onConectado?: (conectado: boolean) => void
  onEstado?: (estado: EstadoVista) => void
}

/**
 * El lado del docente: entra al canal y recibe los fotogramas.
 *
 * Entrar es lo que hace que el estudiante empiece a enviar, así que esto no se
 * monta en segundo plano: se monta cuando el docente abre la vista y se
 * desmonta cuando la cierra.
 */
export function verFotogramas({
  cliente,
  sessionId,
  studentId,
  teacherId,
  onFotograma,
  onConectado,
  onEstado
}: OpcionesVer): Publicacion {
  const canal = canalPrivado(cliente, sessionId, studentId, teacherId)
  let conectado = false

  function revisarPresencia(): void {
    const ahora = hayOtros(canal, teacherId)
    if (ahora === conectado) return
    conectado = ahora
    onConectado?.(ahora)
  }

  onEstado?.('conectando')

  canal
    .on('broadcast', { event: EVENTO_FOTOGRAMA }, (mensaje) => {
      const datos = mensaje.payload as Partial<Fotograma> | undefined
      // Llega de otro cliente: se comprueba antes de ponerlo en un `src`.
      if (typeof datos?.jpeg !== 'string' || !datos.jpeg) return
      onFotograma({
        jpeg: datos.jpeg,
        capturadoEn: typeof datos.capturadoEn === 'number' ? datos.capturadoEn : Date.now()
      })
    })
    .on('presence', { event: 'sync' }, revisarPresencia)
    .on('presence', { event: 'join' }, revisarPresencia)
    .on('presence', { event: 'leave' }, revisarPresencia)
    .subscribe((estado) => {
      if (estado === 'SUBSCRIBED') {
        void canal.track({ rol: 'docente' satisfies Rol })
        revisarPresencia()
        onEstado?.('mirando')
        return
      }
      // Un canal privado que RLS rechaza cierra con `CHANNEL_ERROR`, igual que
      // una caída de red. Desde aquí no se distinguen, así que lo que se le
      // dice al docente no afirma cuál de las dos fue.
      if (estado !== 'CLOSED') onEstado?.('error')
    })

  return {
    detener: async () => {
      await cliente.removeChannel(canal)
    }
  }
}
