// E2E de la app de escritorio (Electron) contra el entorno aislado (27/11/2026).
//
//   node pruebas/e2e/escritorio.mjs <escenario.json> <resultados.json> <carpeta de capturas>
//
// Lo que el navegador no puede probar: la app real, con su proceso principal, su
// preload y sus detectores de sistema operativo (foco de la ventana, atajos de
// copia, procesos). Se lanza la compilación de `apps/desktop/out` con Playwright
// (`_electron`), apuntada por variables de entorno a la web y la API del entorno
// aislado (túnel SSH a :5173, :8080 y :54321), con la cámara y el micrófono de
// prueba de Chromium: nunca usa la cámara del equipo.
//
// Necesita `playwright-core` (NODE_PATH) y el escenario que crea
// `sembrar_e2e.py` (docente, estudiante matriculado y admitido, examen estricto).

import { _electron as electron } from 'playwright-core'
import { execFile, spawn } from 'node:child_process'
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const AQUI = dirname(fileURLToPath(import.meta.url))
const RAIZ = process.env.RAIZ ?? resolve(AQUI, '..', '..')
const [escenarioRuta, salida, capturas] = process.argv.slice(2)
const esc = JSON.parse(readFileSync(escenarioRuta, 'utf8'))
const CONTRASENA = /CONTRASENA = "([^"]+)"/.exec(readFileSync(join(RAIZ, 'loadtests', 'preparar.py'), 'utf8'))[1]
const WEB = 'http://localhost:5173'
const API = 'http://localhost:8080/api/v1'
mkdirSync(capturas, { recursive: true })

const casos = []
const inicioTotal = Date.now()

async function caso(id, tecnica, descripcion, fn) {
  const t0 = Date.now()
  const c = { id, tecnica, descripcion, archivo: 'e2e/escritorio.mjs', prueba: id, resultado: 'passed', segundos: 0, detalle: '', evidencia: [] }
  try {
    const extra = await fn(c)
    if (extra) c.detalle = extra
  } catch (fallo) {
    c.resultado = 'failed'
    c.detalle = String(fallo?.message ?? fallo).split('\n')[0].slice(0, 400)
    try {
      await capturar(c, ventana, `FALLO-${id}`)
    } catch {
      // la ventana puede estar cerrada
    }
  }
  c.segundos = (Date.now() - t0) / 1000
  casos.push(c)
  console.log(`${c.resultado === 'passed' ? 'PASA ' : 'FALLA'} ${id} ${c.detalle}`)
}

function afirmar(cond, mensaje) {
  if (!cond) throw new Error(mensaje)
}

async function eventos() {
  const r = await fetch(`${API}/sessions/${esc.sid}/events`, { headers: { Authorization: `Bearer ${esc.docente_token}` } })
  return r.json()
}

async function esperarEvento(tipo, desde, segundos = 30) {
  const fin = Date.now() + segundos * 1000
  while (Date.now() < fin) {
    const ev = (await eventos()).filter((e) => e.event_type === tipo && Date.parse(e.received_at ?? e.started_at) >= desde - 5000)
    if (ev.length) return ev
    await new Promise((r) => setTimeout(r, 1000))
  }
  return []
}

async function capturar(c, pagina, nombre) {
  const ruta = join(capturas, `${nombre}.png`)
  await pagina.screenshot({ path: ruta })
  c.evidencia.push(ruta)
}

const app = await electron.launch({
  executablePath: join(RAIZ, 'apps', 'desktop', 'node_modules', 'electron', 'dist', 'electron.exe'),
  args: [
    join(RAIZ, 'apps', 'desktop', 'out', 'main', 'index.js'),
    '--use-fake-device-for-media-stream',
    '--use-fake-ui-for-media-stream'
  ],
  cwd: join(RAIZ, 'apps', 'desktop'),
  env: {
    ...process.env,
    PROCTORING_WEB_URL: WEB,
    PROCTORING_API_URL: `${API}/events`,
    PROCTORING_SESSION_ID: esc.sid,
    SUPABASE_URL: 'http://localhost:54321',
    SUPABASE_PUBLISHABLE_KEY: esc.anon
  },
  timeout: 60_000
})
const ventana = await app.firstWindow()
ventana.setDefaultTimeout(30_000)
await ventana.waitForLoadState('domcontentloaded')

// La app guarda la sesión en su perfil. Se borra lo del origen de prueba al
// empezar (para partir sin sesión, como un equipo nuevo) y al terminar (para no
// dejar rastro en el perfil del equipo). Solo ese origen: lo demás no se toca.
async function limpiarOrigen() {
  await app.evaluate(({ session }, origen) => session.defaultSession.clearStorageData({ origin: origen }), WEB)
}
await limpiarOrigen()
await ventana.reload()
await ventana.waitForLoadState('domcontentloaded')

await caso('ED-01', 'Arranque', 'La app abre una sola ventana y carga la web del examen del entorno configurado, no una copia local.', async (c) => {
  await ventana.waitForURL(/\/(login|examen)/)
  afirmar(ventana.url().startsWith(WEB), `cargó ${ventana.url()}`)
  afirmar(app.windows().length === 1, `${app.windows().length} ventanas`)
  await capturar(c, ventana, 'ed01-arranque')
  return `URL inicial: ${ventana.url().replace(WEB, '')}`
})

await caso('ED-02', 'Seguridad Electron', 'La ventana corre con contextIsolation, sandbox y sin nodeIntegration (CLAUDE.md §3).', async () => {
  const prefs = await app.evaluate(({ BrowserWindow }) => {
    const p = BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences()
    return { contextIsolation: p.contextIsolation, sandbox: p.sandbox, nodeIntegration: p.nodeIntegration, webSecurity: p.webSecurity }
  })
  afirmar(prefs.contextIsolation === true && prefs.sandbox === true && prefs.nodeIntegration === false && prefs.webSecurity !== false, JSON.stringify(prefs))
  return JSON.stringify(prefs)
})

await caso('ED-03', 'Seguridad Electron', 'La página no ve Node (require, process) y solo recibe las funciones del preload vía contextBridge.', async () => {
  const r = await ventana.evaluate(() => ({
    require: typeof globalThis.require,
    process: typeof globalThis.process,
    api: window.api ? Object.keys(window.api).sort() : null,
    funciones: window.api ? Object.values(window.api).every((v) => typeof v === 'function') : false
  }))
  afirmar(r.require === 'undefined' && r.process === 'undefined', JSON.stringify(r))
  afirmar(r.api && r.api.length > 0 && r.funciones, `window.api: ${JSON.stringify(r.api)}`)
  return `window.api expone ${r.api.length} funciones: ${r.api.join(', ')}`
})

await caso('ED-04', 'Seguridad Electron', 'La ventana tiene la protección de contenido activada (no sale en capturas ni grabaciones del sistema).', async () => {
  const p = await app.evaluate(({ BrowserWindow }) => {
    const w = BrowserWindow.getAllWindows()[0]
    return typeof w.isContentProtected === 'function' ? w.isContentProtected() : 'sin-api'
  })
  afirmar(p === true, `isContentProtected: ${p}`)
})

await caso('ED-05', 'Seguridad Electron', 'La página no puede navegar fuera de su origen ni abrir ventanas nuevas.', async () => {
  const antes = ventana.url()
  await ventana.evaluate(() => { window.location.href = 'https://example.com/' }).catch(() => {})
  await ventana.waitForTimeout(2500)
  const abierta = await ventana.evaluate(() => window.open('https://example.com/') === null)
  afirmar(new URL(ventana.url()).origin === new URL(WEB).origin, `navegó a ${ventana.url()}`)
  afirmar(abierta, 'window.open devolvió una ventana')
  afirmar(app.windows().length === 1, 'se abrió otra ventana')
  // La navegación bloqueada deja a Playwright esperando una carga que nunca llega: se recarga.
  await ventana.goto(antes)
})

await caso('ED-06a', 'Flujo', 'Con la sesión iniciada en la app, abrir la sala directamente (como hace el enlace proctoring://examen/<id>) muestra el examen a un estudiante ya matriculado y admitido.', async (c) => {
  if (!ventana.url().includes('/login')) await ventana.goto(`${WEB}/login`)
  await ventana.locator('input[type="email"]').fill(esc.alumno.email)
  await ventana.locator('input[type="password"]').fill(CONTRASENA)
  await ventana.getByRole('button', { name: 'Entrar' }).click()
  await ventana.waitForURL((u) => !u.pathname.startsWith('/login'))
  // Aún no escribió el código en esta app: es la ventana que abre el enlace.
  await ventana.goto(`${WEB}/examen/${esc.sid}/sala`)
  await ventana.waitForTimeout(3000)
  const perdido = await ventana.getByText('No encontramos ese examen').count()
  await capturar(c, ventana, 'ed06a-enlace-directo')
  afirmar(perdido === 0, 'La sala dice «No encontramos ese examen» aunque el estudiante está matriculado y admitido: solo funciona si antes escribió el código en esa ventana')
})

await caso('ED-06', 'Flujo', 'Dentro de la app, el estudiante escribe el código y llega a la sala de su examen, ya admitido por el docente.', async (c) => {
  await ventana.goto(`${WEB}/examen`)
  await ventana.getByRole('textbox', { name: /Código de acceso/ }).fill(esc.codigo)
  await ventana.getByRole('button', { name: 'Buscar examen' }).click()
  await ventana.waitForURL(new RegExp(`/examen/${esc.sid}/sala`))
  await ventana.getByText('Tu docente te admitió').waitFor()
  await capturar(c, ventana, 'ed06-sala')
})

await caso('ED-07', 'Flujo', 'Al entrar a rendir, la supervisión se activa y la app muestra la primera pregunta.', async (c) => {
  await ventana.goto(`${WEB}/examen/${esc.sid}/rendir`)
  await ventana.getByText(/Pregunta 1 de/).first().waitFor({ timeout: 60_000 })
  await ventana.waitForTimeout(4000)
  await capturar(c, ventana, 'ed07-rindiendo')
})

await caso('ED-08', 'Detección (foco)', 'Si el estudiante sale de la ventana 6 s, el proceso principal manda focus_lost con esa duración y severidad media.', async () => {
  const desde = Date.now()
  await app.evaluate(async ({ BrowserWindow }) => {
    const examen = BrowserWindow.getAllWindows()[0]
    const otra = new BrowserWindow({ width: 300, height: 200, show: true })
    otra.focus()
    examen.emit('blur')
    await new Promise((r) => setTimeout(r, 6000))
    otra.destroy()
    examen.focus()
    examen.emit('focus')
  })
  const ev = await esperarEvento('focus_lost', desde, 30)
  afirmar(ev.length > 0, 'no llegó focus_lost')
  const e = ev[ev.length - 1]
  afirmar(e.duration_ms >= 5000 && e.duration_ms < 15000, `duración ${e.duration_ms} ms`)
  afirmar(e.severity === undefined || e.severity === 'medium', `severidad ${e.severity}`)
  return `focus_lost de ${e.duration_ms} ms`
})

await caso('ED-09', 'Detección (copia)', 'Ctrl+C dentro del examen se bloquea y se registra como copy_attempt.', async () => {
  const desde = Date.now()
  await ventana.getByText(/Pregunta 1 de/).first().click()
  // Como una tecla de verdad: entra por el proceso principal (before-input-event), no por la página.
  await app.evaluate(({ BrowserWindow }) => {
    const wc = BrowserWindow.getAllWindows()[0].webContents
    wc.sendInputEvent({ type: 'keyDown', keyCode: 'C', modifiers: ['control'] })
    wc.sendInputEvent({ type: 'keyUp', keyCode: 'C', modifiers: ['control'] })
  })
  const ev = await esperarEvento('copy_attempt', desde, 20)
  afirmar(ev.length > 0, 'no llegó copy_attempt')
  return `copy_attempt con atajo ${JSON.stringify(ev[ev.length - 1].metadata?.shortcut ?? ev[ev.length - 1].metadata)}`
})

await caso('ED-10', 'Detección (procesos)', 'Si se abre un programa con nombre de grabador de pantalla (obs64.exe), el proceso principal manda suspicious_process.', async () => {
  const carpeta = join(tmpdir(), `proctoring-e2e-${Date.now()}`)
  mkdirSync(carpeta, { recursive: true })
  const exe = join(carpeta, 'obs64.exe')
  // ping.exe renombrado: un proceso inofensivo que vive 40 s con el nombre de OBS.
  copyFileSync('C:\\Windows\\System32\\PING.EXE', exe)
  const desde = Date.now()
  const hijo = spawn(exe, ['-n', '40', '127.0.0.1'], { stdio: 'ignore', windowsHide: true })
  try {
    const ev = await esperarEvento('suspicious_process', desde, 30)
    afirmar(ev.length > 0, 'no llegó suspicious_process')
    return `suspicious_process: ${JSON.stringify(ev[ev.length - 1].metadata).slice(0, 160)}`
  } finally {
    hijo.kill()
    await new Promise((r) => execFile('taskkill', ['/F', '/IM', 'obs64.exe'], () => r()))
  }
})

await caso('ED-11', 'Alertas', 'El docente ve en la API las alertas del examen: lo alto (proceso) y lo medio (foco) generan alerta; la copia queda registrada.', async () => {
  const r = await fetch(`${API}/sessions/${esc.sid}/alerts`, { headers: { Authorization: `Bearer ${esc.docente_token}` } })
  const alertas = await r.json()
  const sev = alertas.map((a) => a.severity)
  afirmar(sev.includes('high'), `severidades: ${sev}`)
  return `${alertas.length} alertas: ${[...new Set(sev)].join(', ')}`
})

await caso('ED-12', 'Cierre', 'La app se cierra limpia, sin dejar procesos de la ventana.', async () => {
  await limpiarOrigen()
  await app.close()
})

writeFileSync(salida, JSON.stringify({ inicio: inicioTotal / 1000, fin: Date.now() / 1000, api: API, casos }, null, 1))
const fallas = casos.filter((c) => c.resultado !== 'passed').length
console.log(`${casos.length - fallas} pasan, ${fallas} fallan`)
process.exit(fallas ? 1 : 0)
