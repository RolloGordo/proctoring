import { FaceLandmarker, FilesetResolver } from '@mediapipe/tasks-vision'
import { angulosDesdeMatriz, reglasVision } from '../../src/supervision/detectores/vision-core'
import { SeguimientoCondicion } from '../../src/supervision/seguimiento'

const video = document.querySelector<HTMLVideoElement>('#video')!
const canvas = document.querySelector<HTMLCanvasElement>('#overlay')!
const context = canvas.getContext('2d')!
const status = document.querySelector<HTMLElement>('#status')!
const events = document.querySelector<HTMLElement>('#events')!
let stream: MediaStream | undefined
let model: FaceLandmarker | undefined
let running = false
let frame = 0
let lastProcessed = 0
let clipUrl: string | undefined
let clipName = 'camera'
const tracking = {
  gaze_away: new SeguimientoCondicion({ minimoMs: 3000 }),
  face_absent: new SeguimientoCondicion({ minimoMs: 5000 }),
  extra_person: new SeguimientoCondicion({ minimoMs: 2000 })
}
const log: string[] = []
let predictions: string[] = ['time_ms,faces,yaw_deg,pitch_deg,gaze_away,face_absent,extra_person']
const started = { value: 0 }
function download(filename: string, blob: Blob) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = filename; a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 2000)
}
function snapshot(event: string) {
  const still = document.createElement('canvas')
  still.width = video.videoWidth; still.height = video.videoHeight
  still.getContext('2d')!.drawImage(video, 0, 0)
  still.toBlob(b => { if (b) download(`${event}-${Date.now()}.jpg`, b) }, 'image/jpeg', .7)
}
function tick() {
  if (!running || !model) return
  if (video.readyState < 2) { frame = requestAnimationFrame(tick); return }
  const nowMonotonic = performance.now()
  if (nowMonotonic - lastProcessed < 66) { frame = requestAnimationFrame(tick); return }
  lastProcessed = nowMonotonic
  canvas.width = video.videoWidth; canvas.height = video.videoHeight
  const r = model.detectForVideo(video, nowMonotonic)
  const faces = r.faceLandmarks.length
  const angles = faces === 1 ? angulosDesdeMatriz(r.facialTransformationMatrixes[0]) : null
  const flags = reglasVision(faces, angles?.yaw ?? null, 25, 2)
  const now = Date.now()
  predictions.push([
    (clipUrl ? video.currentTime * 1000 : now - started.value).toFixed(0),faces,angles?.yaw ?? '',angles?.pitch ?? '',
    +flags.gaze_away,+flags.face_absent,+flags.extra_person
  ].join(','))
  context.clearRect(0, 0, canvas.width, canvas.height)
  context.fillStyle = '#4fffa6'
  for (const mesh of r.faceLandmarks) for (const p of mesh) {
    context.fillRect(p.x * canvas.width, p.y * canvas.height, 2, 2)
  }
  status.textContent = `Rostros: ${faces}\nYaw: ${angles?.yaw.toFixed(1) ?? 'N/D'}°\nPitch: ${angles?.pitch.toFixed(1) ?? 'N/D'}°\nCondiciones: ${JSON.stringify(flags)}`
  for (const kind of Object.keys(tracking) as (keyof typeof tracking)[]) {
    const episode = tracking[kind].actualizar(flags[kind], now)
    if (!episode) continue
    log.push(`${kind}: ${episode.duracionMs} ms`)
    events.textContent = log.join('\n')
    snapshot(kind)
  }
  frame = requestAnimationFrame(tick)
}
async function stop() {
  running = false; cancelAnimationFrame(frame)
  for (const kind of Object.keys(tracking) as (keyof typeof tracking)[]) {
    const episode = tracking[kind].cerrar()
    if (episode) log.push(`${kind}: ${episode.duracionMs} ms (cierre)`)
  }
  events.textContent = log.join('\n') || 'Ninguno'
  stream?.getTracks().forEach(t => t.stop()); stream = undefined
  video.srcObject = null
  video.removeAttribute('src')
  if (clipUrl) { URL.revokeObjectURL(clipUrl); clipUrl = undefined }
  video.load()
}
document.querySelector<HTMLButtonElement>('#start')!.onclick = async () => {
  if (running) return
  try {
    const wasm = await FilesetResolver.forVisionTasks('/mediapipe/wasm')
    model ??= await FaceLandmarker.createFromOptions(wasm, {
      baseOptions: { modelAssetPath: '/mediapipe/face_landmarker.task' },
      numFaces: 2, outputFacialTransformationMatrixes: true, runningMode: 'VIDEO'
    })
    clipName = 'camera'
    predictions = ['time_ms,faces,yaw_deg,pitch_deg,gaze_away,face_absent,extra_person']
    stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    video.srcObject = stream; await video.play()
    started.value = Date.now(); running = true; tick()
  } catch (e) { status.textContent = `No se pudo iniciar: ${String(e)}`; await stop() }
}
document.querySelector<HTMLInputElement>('#clip')!.onchange = async (event) => {
  const file = (event.currentTarget as HTMLInputElement).files?.[0]
  if (!file) return
  await stop()
  try {
    const wasm = await FilesetResolver.forVisionTasks('/mediapipe/wasm')
    model ??= await FaceLandmarker.createFromOptions(wasm, {
      baseOptions: { modelAssetPath: '/mediapipe/face_landmarker.task' },
      numFaces: 2, outputFacialTransformationMatrixes: true, runningMode: 'VIDEO'
    })
    predictions = ['time_ms,faces,yaw_deg,pitch_deg,gaze_away,face_absent,extra_person']
    log.length = 0; events.textContent = 'Ninguno'
    clipName = file.name.replace(/\.[^.]+$/, '').replace(/[^a-zA-Z0-9_-]/g, '_')
    clipUrl = URL.createObjectURL(file)
    video.src = clipUrl
    video.onended = () => { void stop(); download(`${clipName}.csv`, new Blob([predictions.join('\n') + '\n'], { type: 'text/csv' })) }
    await video.play()
    started.value = Date.now(); running = true; tick()
  } catch (e) { status.textContent = `Error del clip: ${String(e)}`; await stop() }
}
document.querySelector<HTMLButtonElement>('#stop')!.onclick = () => { void stop() }
document.querySelector<HTMLButtonElement>('#export')!.onclick = () => {
  download(`${clipName}.csv`, new Blob([predictions.join('\n') + '\n'], { type: 'text/csv' }))
}
window.addEventListener('pagehide', () => { void stop() })
