/**
 * Los módulos de supervisión, contados para personas.
 *
 * Un solo catálogo para las dos pantallas que los nombran: la del docente, que
 * los elige en un examen personalizado, y la sala de espera, donde el
 * estudiante lee qué se le va a vigilar antes de aceptar. Si cada pantalla
 * tuviera su lista, la del estudiante acabaría diciendo menos de lo que hace el
 * examen, y eso es justo lo que el consentimiento no puede permitirse.
 *
 * Los conjuntos de cada preset copian `PRESET_MODULES` y `DESKTOP_MODULES` de
 * `services/api/src/proctoring_api/domain/exam_session.py`. Si allí cambian,
 * aquí también.
 */

import type { ChosenModules, SupervisionModule, SupervisionPreset } from './api'

/** Con qué se observa cada módulo. Es lo que el estudiante necesita saber. */
export type GrupoModulo = 'identidad' | 'camara' | 'microfono' | 'equipo'

export interface Modulo {
  id: SupervisionModule
  grupo: GrupoModulo
  /** Cómo lo lee el docente al elegirlo. */
  nombre: string
  /** Qué hace, en una línea, para el docente. */
  detalle: string
  /** Cómo lo lee el estudiante en la sala de espera. */
  paraEstudiante: string
  /** Un módulo que no funciona sin este otro. */
  necesita?: SupervisionModule
}

export const GRUPOS: Array<{ id: GrupoModulo; docente: string; estudiante: string }> = [
  { id: 'identidad', docente: 'Identidad', estudiante: 'Tu identidad' },
  { id: 'camara', docente: 'Cámara', estudiante: 'Con tu cámara' },
  { id: 'microfono', docente: 'Micrófono', estudiante: 'Con tu micrófono' },
  { id: 'equipo', docente: 'Pantalla y equipo', estudiante: 'En tu equipo' }
]

export const MODULOS: Modulo[] = [
  {
    id: 'face_verification',
    grupo: 'identidad',
    nombre: 'Verificación al entrar',
    detalle: 'Compara su rostro con su foto de referencia antes de empezar.',
    paraEstudiante: 'Verificación de tu rostro antes de empezar'
  },
  {
    id: 'face_reverification',
    grupo: 'identidad',
    nombre: 'Reverificación durante el examen',
    detalle: 'Vuelve a comprobar el rostro cada 10 minutos. Necesita la verificación al entrar.',
    paraEstudiante: 'Nuevas verificaciones de tu rostro durante el examen',
    necesita: 'face_verification'
  },
  {
    id: 'gaze',
    grupo: 'camara',
    nombre: 'Mirada fuera de la pantalla',
    detalle: 'También avisa si el rostro desaparece de la cámara.',
    paraEstudiante: 'Si miras fuera de la pantalla o sales de la cámara'
  },
  {
    id: 'extra_person',
    grupo: 'camara',
    nombre: 'Otra persona en cámara',
    detalle: 'Avisa cuando aparece un segundo rostro.',
    paraEstudiante: 'Si aparece otra persona en la cámara'
  },
  {
    id: 'objects',
    grupo: 'camara',
    nombre: 'Celulares y objetos no permitidos',
    detalle: 'Busca un celular en la imagen de la cámara.',
    paraEstudiante: 'Si aparece un celular u otro objeto no permitido'
  },
  {
    id: 'live_monitoring',
    grupo: 'camara',
    nombre: 'Supervisión en vivo',
    detalle: 'Ves su cámara en tu panel, sin grabar. Es el módulo que más red consume.',
    paraEstudiante: 'Tu docente puede ver tu cámara en vivo, sin grabación'
  },
  {
    id: 'external_voices',
    grupo: 'microfono',
    nombre: 'Voces durante el examen',
    detalle: 'Avisa cuando se habla. Te llega el fragmento de audio para que decidas.',
    paraEstudiante: 'Si se habla durante el examen'
  },
  {
    id: 'ai_voice',
    grupo: 'microfono',
    nombre: 'Consulta a una IA por voz',
    detalle: 'Compara lo que se dice con el enunciado y busca una voz sintética que responda.',
    paraEstudiante: 'Si se consulta a un asistente de IA por voz'
  },
  {
    id: 'focus_loss',
    grupo: 'equipo',
    nombre: 'Salidas de la ventana del examen',
    detalle: 'Registra cuándo deja la ventana y cuánto tarda en volver.',
    paraEstudiante: 'Si sales de la ventana del examen'
  },
  {
    id: 'copy_paste_block',
    grupo: 'equipo',
    nombre: 'Copiar y pegar',
    detalle: 'Bloquea los atajos y avisa de cada intento.',
    paraEstudiante: 'Los intentos de copiar o pegar'
  },
  {
    id: 'multi_monitor',
    grupo: 'equipo',
    nombre: 'Monitores adicionales',
    detalle: 'Avisa si hay más de una pantalla conectada.',
    paraEstudiante: 'Si conectas más de un monitor'
  },
  {
    id: 'screen_capture',
    grupo: 'equipo',
    nombre: 'Programas de captura o control remoto',
    detalle: 'Zoom, AnyDesk, TeamViewer, OBS o una máquina virtual abiertos.',
    paraEstudiante: 'Si hay abiertos programas para compartir o controlar la pantalla'
  }
]

const POR_ID = new Map(MODULOS.map((m) => [m.id, m]))

export function modulo(id: string): Modulo | undefined {
  return POR_ID.get(id as SupervisionModule)
}

/** `PRESET_MODULES` del dominio. */
export const MODULOS_DE_PRESET: Record<
  Exclude<SupervisionPreset, 'custom'>,
  SupervisionModule[]
> = {
  basic: ['face_verification', 'focus_loss'],
  standard: [
    'face_verification',
    'focus_loss',
    'copy_paste_block',
    'multi_monitor',
    'gaze',
    'extra_person',
    'objects'
  ],
  strict: MODULOS.map((m) => m.id)
}

/**
 * `DESKTOP_MODULES` del dominio: lo que la app de escritorio vigila por su
 * cuenta en los presets, aunque el preset no lo active.
 */
export const MODULOS_DE_ESCRITORIO: SupervisionModule[] = [
  'focus_loss',
  'copy_paste_block',
  'multi_monitor',
  'screen_capture'
]

/**
 * Marca o desmarca un módulo cuidando las dependencias.
 *
 * Marcar la reverificación marca la verificación, y quitar la verificación
 * quita la reverificación: la API rechaza una sin la otra, y es mejor que la
 * casilla lo resuelva a que el docente se entere al guardar.
 */
export function alternarModulo(
  elegidos: ReadonlySet<SupervisionModule>,
  id: SupervisionModule,
  activo: boolean
): Set<SupervisionModule> {
  const siguiente = new Set(elegidos)
  if (activo) {
    siguiente.add(id)
    const requisito = POR_ID.get(id)?.necesita
    if (requisito) siguiente.add(requisito)
  } else {
    siguiente.delete(id)
    for (const m of MODULOS) if (m.necesita === id) siguiente.delete(m.id)
  }
  return siguiente
}

/** Lo que tendrá que encender el estudiante. */
export function dispositivosQueUsa(modulos: Iterable<string>): {
  camara: boolean
  microfono: boolean
} {
  const grupos = new Set([...modulos].map((m) => modulo(m)?.grupo))
  return {
    // La verificación de identidad también usa la cámara.
    camara: grupos.has('camara') || grupos.has('identidad'),
    microfono: grupos.has('microfono')
  }
}

/** El cuerpo que espera la API: cada módulo vacío, los umbrales los pone ella. */
export function comoModulosElegidos(elegidos: Iterable<SupervisionModule>): ChosenModules {
  return Object.fromEntries([...elegidos].map((id) => [id, {}]))
}

/**
 * Lo que se le dice al estudiante que se vigila.
 *
 * `watched_modules` cuando la API lo manda. Si no (una API anterior), las
 * claves de `modules`: es lo que se mostraba antes, y la API y la web se
 * despliegan por separado.
 */
export function modulosVigilados(examen: {
  modules: Record<string, unknown>
  watched_modules?: SupervisionModule[]
}): SupervisionModule[] {
  const ids = examen.watched_modules ?? (Object.keys(examen.modules) as SupervisionModule[])
  return MODULOS.map((m) => m.id).filter((id) => ids.includes(id))
}

/** Los módulos agrupados por con qué se observan, en el orden del catálogo. */
export function agrupar(
  ids: Iterable<string>
): Array<{ grupo: (typeof GRUPOS)[number]; modulos: Modulo[] }> {
  const presentes = new Set(ids)
  return GRUPOS.map((grupo) => ({
    grupo,
    modulos: MODULOS.filter((m) => m.grupo === grupo.id && presentes.has(m.id))
  })).filter((g) => g.modulos.length > 0)
}
