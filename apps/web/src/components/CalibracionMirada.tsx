import { useEffect, useRef, useState } from 'react'
import { abrirCamara } from '../supervision/camara'
import { CALIBRATION_STEPS, combinarMuestras, estimateCalibration, MUESTRAS_POR_PASO, saveCalibration, validarPaso, type CalibrationSample } from '../supervision/calibration'

/** Pausa entre fotogramas de un mismo paso: seis en algo menos de un segundo. */
const PAUSA_MUESTRA_MS = 140

/** Five short pose checks before admission. Optional; no photo is persisted. */
export function CalibracionMirada({ sessionId, studentId, defaultDeg = 25 }: {
  sessionId: string; studentId: string; defaultDeg?: number
}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const cameraRef = useRef<Awaited<ReturnType<typeof abrirCamara>> | null>(null)
  const [samples, setSamples] = useState<CalibrationSample[]>([])
  const [ready, setReady] = useState(false)
  const [saving, setSaving] = useState(false)
  const [completed, setCompleted] = useState(false)
  const [error, setError] = useState<string>()

  useEffect(() => () => cameraRef.current?.cerrar(), [])

  async function start() {
    setError(undefined)
    setSaving(true)
    try {
      cameraRef.current?.cerrar()
      const camera = await abrirCamara()
      cameraRef.current = camera
      if (videoRef.current) {
        videoRef.current.srcObject = camera.video.srcObject
        await videoRef.current.play()
      }
      setReady(true)
      setSamples([])
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No se pudo abrir la cámara para calibrar.')
    } finally { setSaving(false) }
  }

  async function take() {
    const video = videoRef.current
    if (!video || saving) return
    setSaving(true)
    setError(undefined)
    try {
      const { measureHeadPose } = await import('../supervision/detectores/vision')
      // Varios fotogramas por paso (Jesús): un parpadeo en el instante justo
      // ya no falsea la calibración de los ojos para todo el examen.
      const tomadas: CalibrationSample[] = []
      for (let i = 0; i < MUESTRAS_POR_PASO; i += 1) {
        if (i > 0) await new Promise((r) => setTimeout(r, PAUSA_MUESTRA_MS))
        tomadas.push(await measureHeadPose(video))
      }
      const measurement = combinarMuestras(tomadas)
      if (!measurement) {
        throw new Error('Debe verse exactamente un rostro. Acomódate e inténtalo otra vez.')
      }
      const problema = validarPaso(samples.length, measurement, samples[0])
      if (problema) throw new Error(problema)
      const next = [...samples, measurement]
      setSamples(next)
      if (next.length === CALIBRATION_STEPS.length) {
        const result = estimateCalibration(next, defaultDeg)
        saveCalibration(sessionId, studentId, result)
        cameraRef.current?.cerrar()
        cameraRef.current = null
        setReady(false)
        setCompleted(true)
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No se pudo medir la orientación.')
    } finally { setSaving(false) }
  }

  return <section className="tarjeta" style={{ marginTop: 'var(--e4)' }} aria-label="Calibración de la mirada">
    <div className="tarjeta-cuerpo">
      <h3>Calibración de la mirada (recomendada)</h3>
      <p className="ayuda">Toma menos de un minuto: mirarás el centro y las cuatro esquinas de tu pantalla. Así el sistema aprende hasta dónde llega tu pantalla y no confunde leer la parte de abajo con mirar fuera, lo que evita avisos falsos durante el examen. No se guarda ningún video ni fotografía. Si la omites, se usan los valores del docente y queda constancia en los eventos.</p>
      {completed ? <p role="status" className="aviso aviso-exito">Calibración guardada para esta sesión en este dispositivo. Ya puedes iniciar el examen.</p> : <>
        <video ref={videoRef} autoPlay playsInline muted style={{ display: ready ? 'block' : 'none', width: 260, maxWidth: '100%', borderRadius: 8 }} aria-label="Vista previa de calibración" />
        {ready ? <>
          <p><strong>Paso {samples.length + 1} de 5:</strong> {CALIBRATION_STEPS[samples.length]}</p>
          <button type="button" className="boton boton-secundario" disabled={saving} onClick={() => void take()}>{saving ? 'Midiendo… no te muevas' : 'Registrar esta posición'}</button>
        </> : <button type="button" className="boton boton-secundario" disabled={saving} onClick={() => void start()}>{saving ? 'Abriendo cámara…' : 'Iniciar calibración'}</button>}
      </>}
      {error && <p className="aviso" role="alert">{error}</p>}
    </div>
  </section>
}
