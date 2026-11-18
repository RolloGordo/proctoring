// Estrés de la API con k6 (batería completa, 18/11/2026).
//
//   docker run --rm --network host -v $PWD/.datos:/datos -v $PWD/k6:/k6 grafana/k6:0.57.0 \
//     run /k6/estres.js
//
// Tres fases sobre el escenario de `completa/sembrar.py` (exámenes con presets
// distintos, dos `custom` con módulos apagados):
//
// 1. **pico_ingreso**: todos los estudiantes entran a la vez (código, matrícula
//    con consentimiento, estado). Es el peor minuto real de un examen.
// 2. **modulos**: 30 señales por segundo de los 12 tipos, en todos los presets.
//    Cada respuesta se compara con el dominio: si el módulo está apagado en un
//    `custom` tiene que ser 400; si no, 201 con la severidad de `severity.py`.
//    Comprueba que bajo carga no se cuela ni se pierde nada.
// 3. **rampa**: señales de 20 a 900 por segundo, subiendo cada minuto, hasta
//    encontrar el punto en que la API deja de responder a tiempo. Los docentes
//    siguen leyendo la sala, las alertas, las señales y el semáforo a la vez.
//
// Las señales se reparten en turno entre todos los estudiantes: con 600, ni a
// 900/s se pasa del límite de 120 escrituras por minuto y persona, así que un
// 429 aquí sería un fallo de verdad y no el límite haciendo su trabajo.

import http from 'k6/http'
import { check, sleep } from 'k6'
import exec from 'k6/execution'
import { SharedArray } from 'k6/data'
import { Counter, Rate, Trend } from 'k6/metrics'

const API = __ENV.API || 'http://127.0.0.1:8080/api/v1'
const RUTA = __ENV.ESCENARIO || '/datos/escenario-k6.json'
// SharedArray: una sola copia para todos los VU (con 2500 VU, copiar los
// tokens en cada uno serían gigas de memoria del generador).
const EXAMENES = new SharedArray('examenes', () =>
  JSON.parse(open(RUTA)).examenes.map((e) => ({ id: e.id, docente_token: e.docente_token })),
)
const ALUMNOS = new SharedArray('alumnos', () =>
  JSON.parse(open(RUTA)).examenes.flatMap((e) =>
    e.estudiantes.map((s) => ({ id: s.id, token: s.token, sid: e.id, codigo: e.codigo, preset: e.preset, modulos: e.modulos, preguntas: e.preguntas })),
  ),
)
const N = ALUMNOS.length
const RAMPA = (__ENV.RAMPA || '100,200,350,500,700,900').split(',').map(Number)

// Copia de EVENT_MODULES (domain/exam_session.py).
const MODULOS_DE = {
  focus_lost: ['focus_loss'],
  copy_attempt: ['copy_paste_block'],
  gaze_away: ['gaze'],
  face_absent: ['gaze'],
  extra_person: ['extra_person'],
  extra_display: ['multi_monitor'],
  suspicious_process: ['screen_capture'],
  screen_share: ['screen_capture'],
  speech_detected: ['ai_voice', 'external_voices'],
  prohibited_object: ['objects'],
  framing_lost: ['gaze', 'objects'],
  identity_check: ['face_verification', 'face_reverification'],
}
const TIPOS = Object.keys(MODULOS_DE)

// Copia de default_severity (domain/severity.py).
function severidad(tipo, ms) {
  switch (tipo) {
    case 'extra_person':
    case 'suspicious_process':
    case 'screen_share':
      return 'high'
    case 'prohibited_object':
    case 'copy_attempt':
    case 'extra_display':
    case 'speech_detected':
      return 'medium'
    case 'framing_lost':
      return ms >= 30000 ? 'medium' : 'low'
    case 'focus_lost':
      return ms >= 30000 ? 'high' : ms >= 5000 ? 'medium' : 'low'
    case 'face_absent':
      return ms >= 15000 ? 'high' : ms >= 5000 ? 'medium' : 'low'
    case 'gaze_away':
      return ms >= 10000 ? 'medium' : 'low'
    default:
      return 'low'
  }
}

const vigila = (a, tipo) => !a.preset.startsWith('custom') || MODULOS_DE[tipo].some((m) => a.modulos.includes(m))

const moduloCorrecto = new Rate('modulo_correcto')
const severidadCorrecta = new Rate('severidad_correcta')
const rechazadas = new Counter('senales_rechazadas_por_modulo')
const ingresoCompleto = new Trend('ingreso_completo', true)

const etapas = RAMPA.map((t) => ({ target: t, duration: '1m' })).concat([{ target: 0, duration: '15s' }])
const INICIO_MODULOS = Number(__ENV.INICIO_MODULOS || 150)
const INICIO_RAMPA = INICIO_MODULOS + 100

// Umbrales «testigo» por etapa: no cortan nada, solo hacen que el resumen
// traiga el p95 de cada minuto de la rampa.
const porEtapa = {}
RAMPA.forEach((t) => {
  porEtapa[`http_req_duration{etapa:${t}}`] = ['p(95)>=0']
  porEtapa[`http_req_failed{etapa:${t}}`] = ['rate>=0']
  porEtapa[`iterations{etapa:${t}}`] = ['count>=0']
})

export const options = {
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
  setupTimeout: '2m',
  scenarios: {
    pico_ingreso: { executor: 'per-vu-iterations', vus: N, iterations: 1, maxDuration: '140s', exec: 'ingreso' },
    modulos: {
      executor: 'constant-arrival-rate', rate: 30, timeUnit: '1s', duration: __ENV.MODULOS_DURACION || '90s',
      preAllocatedVUs: 60, maxVUs: 200, startTime: `${INICIO_MODULOS}s`, exec: 'modulo',
    },
    rampa: {
      executor: 'ramping-arrival-rate', startRate: 20, timeUnit: '1s', stages: etapas,
      preAllocatedVUs: 400, maxVUs: 2500, startTime: `${INICIO_RAMPA}s`, exec: 'senal',
    },
    docentes: {
      executor: 'constant-vus', vus: EXAMENES.length, duration: `${RAMPA.length * 60 + 15}s`,
      startTime: `${INICIO_RAMPA}s`, exec: 'docente',
    },
  },
  thresholds: {
    'http_req_failed{scenario:pico_ingreso}': ['rate<0.01'],
    'http_req_duration{scenario:pico_ingreso}': ['p(95)<3000'],
    'http_req_failed{scenario:modulos}': ['rate<0.01'],
    modulo_correcto: ['rate>0.999'],
    severidad_correcta: ['rate>0.999'],
    'http_req_duration{scenario:docentes}': ['p(95)>=0'],
    'http_req_duration{scenario:rampa}': ['p(95)>=0'],
    ...porEtapa,
  },
}

const json = (token) => ({ headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } })
const ahora = () => new Date(Date.now() - 200).toISOString()

export function ingreso() {
  const a = ALUMNOS[exec.scenario.iterationInTest]
  const t0 = Date.now()
  const o = json(a.token)
  const r1 = http.post(`${API}/sessions/join`, JSON.stringify({ access_code: a.codigo }), { ...o, tags: { name: 'ingreso: código' } })
  const r2 = http.post(`${API}/exam/${a.sid}/enroll`, JSON.stringify({ accepts_supervision: true }), { ...o, tags: { name: 'ingreso: matrícula' } })
  const r3 = http.get(`${API}/exam/${a.sid}/me`, { ...o, tags: { name: 'ingreso: mi estado' } })
  check(r1, { 'código 200': (r) => r.status === 200 })
  check(r2, { 'matrícula 2xx': (r) => r.status >= 200 && r.status < 300 })
  check(r3, { 'estado 200': (r) => r.status === 200 })
  if (r1.status === 200 && r2.status < 300 && r3.status === 200) ingresoCompleto.add(Date.now() - t0)
}

function duracion(tipo) {
  if (['suspicious_process', 'extra_display', 'copy_attempt', 'screen_share', 'identity_check'].includes(tipo)) return 0
  return Math.floor(Math.random() * 45000)
}

function mandar(a, tipo, ms, tags, esperados) {
  return http.post(
    `${API}/events`,
    JSON.stringify({
      session_id: a.sid, student_id: a.id, question_id: a.preguntas[Math.floor(Math.random() * a.preguntas.length)], event_type: tipo,
      started_at: ahora(), duration_ms: ms, metadata: { carga: 'k6' },
    }),
    { ...json(a.token), tags, ...(esperados ? { responseCallback: esperados } : {}) },
  )
}

export function modulo() {
  const a = ALUMNOS[exec.scenario.iterationInTest % N]
  const tipo = TIPOS[exec.scenario.iterationInTest % TIPOS.length]
  const ms = duracion(tipo)
  const debe = vigila(a, tipo)
  // Un 400 de un módulo apagado es la respuesta correcta, no un fallo.
  const r = mandar(a, tipo, ms, { name: 'señal (módulos)', tipo, preset: a.preset }, debe ? null : http.expectedStatuses(400))
  if (r.status === 429 || r.status >= 500) return // fallo de capacidad: ya lo cuenta http_req_failed
  const ok = debe ? r.status === 201 : r.status === 400
  moduloCorrecto.add(ok, { tipo, preset: a.preset })
  if (!debe && r.status === 400) rechazadas.add(1, { tipo, preset: a.preset })
  if (debe && r.status === 201) severidadCorrecta.add(r.json('severity') === severidad(tipo, ms), { tipo })
}

export function senal() {
  const i = exec.scenario.iterationInTest
  const a = ALUMNOS[i % N]
  const validos = TIPOS.filter((t) => vigila(a, t))
  const tipo = validos[i % validos.length]
  // La etapa es el objetivo del minuto en curso: con ella el resumen da el p95 de cada escalón.
  const minuto = Math.min(Math.floor((Date.now() - exec.scenario.startTime) / 60000), RAMPA.length - 1)
  const r = mandar(a, tipo, duracion(tipo), { name: 'señal (rampa)', etapa: String(RAMPA[minuto]) })
  check(r, { 'señal 201': (x) => x.status === 201 })
}

export function docente() {
  const e = EXAMENES[(exec.vu.idInTest - 1) % EXAMENES.length]
  const o = { headers: { Authorization: `Bearer ${e.docente_token}` } }
  http.batch([
    ['GET', `${API}/sessions/${e.id}/participants`, null, { ...o, tags: { name: 'docente: sala' } }],
    ['GET', `${API}/sessions/${e.id}/alerts`, null, { ...o, tags: { name: 'docente: alertas' } }],
    ['GET', `${API}/sessions/${e.id}/events`, null, { ...o, tags: { name: 'docente: señales' } }],
    ['GET', `${API}/sessions/${e.id}/risk`, null, { ...o, tags: { name: 'docente: semáforo' } }],
  ])
  sleep(2)
}

export function handleSummary(data) {
  return { '/salida/k6-estres.json': JSON.stringify(data) }
}
