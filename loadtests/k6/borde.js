// El borde de producción bajo carga (batería completa, 18/11/2026).
//
//   docker run --rm --network host -v $PWD/resultados:/salida -v $PWD/k6:/k6 grafana/k6:0.57.0 \
//     run /k6/borde.js
//
// **Solo lee**: la página, sus assets, `/health` de la API y el preflight de
// CORS, por el dominio real (TLS, Traefik, nginx). No crea cuentas ni datos:
// lo que se escribe en la base se prueba en el entorno aislado (`estres.js`).
//
// - **visitantes**: hasta 250 navegadores abriendo la web a la vez (HTML y
//   todos los assets con compresión, como un navegador sin caché).
// - **api**: 60 peticiones por segundo a `/health` y al preflight de CORS
//   desde el origen bueno; el de Vercel tiene que salir sin permiso.
// - **seguridad**: mientras tanto, lo que el endurecimiento del 18/11 promete
//   tiene que seguir siendo verdad bajo carga: 413 para un cuerpo de 5 MB,
//   404 para `/.env` y `/.git/config`, 401 para un token falsificado y las
//   cabeceras de seguridad en cada respuesta.

import http from 'k6/http'
import { check, sleep } from 'k6'
import { Rate, Trend } from 'k6/metrics'

const WEB = __ENV.WEB || 'https://proctoring-upao.app'
const API = __ENV.API || 'https://api.proctoring-upao.app'
const VISITANTES = Number(__ENV.VISITANTES || 250)

const paginaCompleta = new Trend('pagina_completa', true)
const seguridadOk = new Rate('seguridad_ok')

export const options = {
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
  scenarios: {
    visitantes: {
      executor: 'ramping-vus', exec: 'visitante', startVUs: 0,
      stages: [
        { target: Math.round(VISITANTES / 5), duration: '45s' },
        { target: VISITANTES, duration: '90s' },
        { target: VISITANTES, duration: '60s' },
        { target: 0, duration: '15s' },
      ],
    },
    api: { executor: 'constant-arrival-rate', exec: 'api', rate: 60, timeUnit: '1s', duration: '210s', preAllocatedVUs: 30, maxVUs: 200 },
    seguridad: { executor: 'constant-vus', exec: 'seguridad', vus: 2, duration: '200s' },
  },
  thresholds: {
    'http_req_failed{scenario:visitantes}': ['rate<0.01'],
    'http_req_duration{scenario:visitantes}': ['p(95)<1000'],
    'http_req_duration{scenario:api}': ['p(95)<500'],
    pagina_completa: ['p(95)<3000'],
    seguridad_ok: ['rate==1'],
  },
}

let assets = null
const comprimido = { headers: { 'Accept-Encoding': 'br, gzip' } }

export function visitante() {
  const t0 = Date.now()
  const r = http.get(`${WEB}/`, { ...comprimido, tags: { name: 'web: página' } })
  check(r, { 'página 200': (x) => x.status === 200 })
  if (!assets && r.status === 200) {
    assets = [...new Set((r.body.match(/\/assets\/[^"']+\.(js|css)/g) || []))]
  }
  const lista = (assets || []).map((a) => ['GET', `${WEB}${a}`, null, { ...comprimido, tags: { name: 'web: asset' } }])
  const resp = http.batch(lista)
  check(resp, { 'assets 200': (xs) => xs.every((x) => x.status === 200) })
  paginaCompleta.add(Date.now() - t0)
  sleep(2 + Math.random() * 3)
}

export function api() {
  const h = http.get(`${API}/health`, { tags: { name: 'api: /health' } })
  check(h, { 'health 200': (x) => x.status === 200 })
  const p = http.options(`${API}/api/v1/events`, null, {
    headers: { Origin: WEB, 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'authorization,content-type' },
    tags: { name: 'api: preflight CORS' },
  })
  check(p, { 'CORS al dominio': (x) => x.headers['Access-Control-Allow-Origin'] === WEB })
}

const CINCO_MB = 'x'.repeat(5 * 1024 * 1024)
const FALSO = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ4Iiwicm9sZSI6InRlYWNoZXIifQ.firmafalsa'

export function seguridad() {
  const no = { responseCallback: http.expectedStatuses({ min: 200, max: 499 }) }
  const pruebas = [
    ['413 a 5 MB', http.post(`${API}/api/v1/events`, CINCO_MB, { ...no, headers: { 'Content-Type': 'application/json' }, tags: { name: 'seg: 5 MB' } }), (x) => x.status === 413],
    ['/.env 404', http.get(`${WEB}/.env`, { ...no, tags: { name: 'seg: /.env' } }), (x) => x.status === 404],
    ['/.git 404', http.get(`${WEB}/.git/config`, { ...no, tags: { name: 'seg: /.git' } }), (x) => x.status === 404],
    ['token falso 401', http.get(`${API}/api/v1/sessions`, { ...no, headers: { Authorization: `Bearer ${FALSO}` }, tags: { name: 'seg: token falso' } }), (x) => x.status === 401],
    ['Vercel sin CORS', http.options(`${API}/api/v1/events`, null, { ...no, headers: { Origin: 'https://proctoring-brown.vercel.app', 'Access-Control-Request-Method': 'POST' }, tags: { name: 'seg: origen Vercel' } }), (x) => !x.headers['Access-Control-Allow-Origin']],
    ['HSTS y nosniff', http.get(`${WEB}/`, { ...no, tags: { name: 'seg: cabeceras' } }), (x) => (x.headers['Strict-Transport-Security'] || '').includes('max-age=31536000') && x.headers['X-Content-Type-Options'] === 'nosniff'],
  ]
  for (const [nombre, r, ok] of pruebas) {
    const bien = ok(r)
    seguridadOk.add(bien, { prueba: nombre })
    check(r, { [nombre]: () => bien })
  }
  sleep(5)
}

export function handleSummary(data) {
  return { '/salida/k6-borde.json': JSON.stringify(data) }
}
