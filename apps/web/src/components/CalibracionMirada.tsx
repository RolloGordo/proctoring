import { useEffect, useRef, useState } from 'react'
import { abrirCamara } from '../supervision/camara'
import { CALIBRATION_STEPS, estimateCalibration, saveCalibration, type CalibrationSample } from '../supervision/calibration'

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
      const measurement = await measureHeadPose(video)
      if (measurement.faceCount !== 1 || measurement.yaw === null) {
        throw new Error('Debe verse exactamente un rostro. Acomódate e inténtalo otra vez.')
      }
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

  return <section className="tarjeta" style={{ marginTop: 'var(--e4)' }} aria-label="Calibración opcional de la mirada">
    <div className="tarjeta-cuerpo">
      <h3>Calibración breve de cámara</h3>
      <p className="ayuda">Antes del examen puedes ajustar la orientación de cabeza a tu pantalla. No se guarda ningún video ni fotografía. Si la omites, se usa el umbral del docente y se deja constancia de ello en los eventos.</p>
      {completed ? <p role="status" className="aviso aviso-exito">Calibración guardada para esta sesión en este dispositivo. Ya puedes iniciar el examen.</p> : <>
        <video ref={videoRef} autoPlay playsInline muted style={{ display: ready ? 'block' : 'none', width: 260, maxWidth: '100%', borderRadius: 8 }} aria-label="Vista previa de calibración" />
        {ready ? <>
          <p><strong>Paso {samples.length + 1} de 5:</strong> {CALIBRATION_STEPS[samples.length]}</p>
          <button type="button" className="boton boton-secundario" disabled={saving} onClick={() => void take()}>{saving ? 'Midiendo…' : 'Registrar esta posición'}</button>
        </> : <button type="button" className="boton boton-secundario" disabled={saving} onClick={() => void start()}>{saving ? 'Abriendo cámara…' : 'Iniciar calibración (opcional)'}</button>}
      </>}
      {error && <p className="aviso" role="alert">{error}</p>}
    </div>
  </section>
}
