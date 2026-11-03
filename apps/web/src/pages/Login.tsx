import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { Burbuja } from '../components/Burbuja'
import { CapaPublica } from '../components/Capas'
import { revisarAcceso, type ErroresAcceso } from '../lib/acceso'
import { useAuth } from '../lib/auth-context'
import { CONTACTO } from '../lib/contacto'
import { FOTOS } from '../lib/fotos-portada'
import { inicioSegunRol } from '../lib/rutas'
import { authEnabled } from '../lib/supabase'
import { useBurbuja } from '../lib/use-burbuja'

/**
 * El acceso, con la misma voz que la portada.
 *
 * El título continúa los verbos de la portada —detecta, documenta, decide,
 * empieza— y la burbuja de cristal vuelve con un estudiante en su portátil,
 * para que se note que es la misma casa. El formulario es lo que manda: va a la
 * derecha, en su propio panel, y en el teléfono sube justo después del título.
 *
 * Lo que se puede revisar sin preguntarle a nadie se revisa aquí, campo por
 * campo (`lib/acceso.ts`); lo demás lo dice Supabase, ya traducido.
 *
 * La burbuja va vacía y sigue al cursor por el lado izquierdo; en cuanto el
 * cursor entra al formulario, o se escribe en él, vuelve a su sitio.
 */

export function Login() {
  const { entrar, salir, token, cargando, rol, perfilListo } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string>()
  const [errores, setErrores] = useState<ErroresAcceso>({})
  const [enviando, setEnviando] = useState(false)
  const [verClave, setVerClave] = useState(false)
  const [mayusculas, setMayusculas] = useState(false)
  const raiz = useRef<HTMLDivElement>(null)
  const lienzo = useRef<HTMLCanvasElement>(null)
  const campoCorreo = useRef<HTMLInputElement>(null)
  const campoClave = useRef<HTMLInputElement>(null)

  useBurbuja(raiz, lienzo)

  // Sin Supabase configurado no hay a quien pedirle credenciales.
  if (!authEnabled) return <Navigate to="/" replace />
  if (!cargando && token && rol) return <Navigate to={inicioSegunRol(rol)} replace />

  // Hay sesión pero el perfil todavía no ha llegado. Si ya se consultó y no hay
  // rol, la cuenta existe en Supabase pero no tiene perfil: esperar para
  // siempre dejaría a la persona mirando «Entrando…» sin saber qué pasa.
  const sinPerfil = !cargando && Boolean(token)

  async function enviar(evento: FormEvent): Promise<void> {
    evento.preventDefault()
    setError(undefined)
    const encontrados = revisarAcceso(email, password)
    setErrores(encontrados)
    // El foco va al primer campo que hay que arreglar: quien usa lector de
    // pantalla oye el error, y quien teclea no tiene que buscarlo.
    if (encontrados.correo) return campoCorreo.current?.focus()
    if (encontrados.clave) return campoClave.current?.focus()

    setEnviando(true)
    try {
      // No se navega aquí: cuando llegan el token y el perfil este mismo
      // componente se vuelve a pintar y redirige al panel que corresponde.
      await entrar(email.trim(), password)
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : 'No se pudo iniciar sesión')
    } finally {
      setEnviando(false)
    }
  }

  const describeClave =
    [errores.clave && 'acceso-clave-error', mayusculas && 'acceso-clave-mayus']
      .filter(Boolean)
      .join(' ') || undefined

  return (
    <CapaPublica enAcceso>
      <div ref={raiz} className="pub-acceso pub-marco">
        <canvas ref={lienzo} className="pub-lienzo" aria-hidden="true" />

        <div className="pub-acceso-portada">
          <Tecleado texto="Entra" />
          <p className="pub-intro" data-burbuja-refracta>
            Docentes y estudiantes, con su correo institucional.
          </p>
          <Burbuja fotos={[FOTOS.escribe]} ancla sigue />
        </div>

        <section
          className="pub-acceso-panel"
          aria-labelledby="acceso-titulo"
          data-burbuja-evita="lado"
        >
          {sinPerfil ? (
            perfilListo ? (
              <>
                <h2 id="acceso-titulo">Cuenta sin perfil</h2>
                <p className="pub-acceso-texto">
                  Tu cuenta existe, pero no tiene un perfil en el sistema. Avisa a tu docente.
                </p>
                <button type="button" className="pub-boton" onClick={() => void salir()}>
                  Cerrar sesión
                </button>
              </>
            ) : (
              <>
                <h2 id="acceso-titulo">Entrando…</h2>
                <p className="pub-acceso-texto" role="status">
                  Cargando tu perfil.
                </p>
              </>
            )
          ) : (
            <>
              <h2 id="acceso-titulo">Iniciar sesión</h2>

              <form className="pub-formulario" onSubmit={(e) => void enviar(e)} noValidate>
                {error && (
                  <p className="pub-error" role="alert">
                    {error}
                  </p>
                )}

                <div className="pub-campo">
                  <label htmlFor="acceso-correo">Correo institucional</label>
                  <input
                    ref={campoCorreo}
                    id="acceso-correo"
                    type="email"
                    inputMode="email"
                    autoComplete="username"
                    autoCapitalize="none"
                    spellCheck={false}
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value)
                      setErrores((antes) => ({ ...antes, correo: undefined }))
                    }}
                    placeholder="nombre@upao.edu.pe"
                    aria-invalid={errores.correo ? true : undefined}
                    aria-describedby={errores.correo ? 'acceso-correo-error' : undefined}
                  />
                  {errores.correo && (
                    <p id="acceso-correo-error" className="pub-campo-error">
                      {errores.correo}
                    </p>
                  )}
                </div>

                <div className="pub-campo">
                  <label htmlFor="acceso-clave">Contraseña</label>
                  <div className="pub-campo-clave">
                    <input
                      ref={campoClave}
                      id="acceso-clave"
                      type={verClave ? 'text' : 'password'}
                      autoComplete="current-password"
                      value={password}
                      onChange={(e) => {
                        setPassword(e.target.value)
                        setErrores((antes) => ({ ...antes, clave: undefined }))
                      }}
                      onKeyUp={(e) => setMayusculas(e.getModifierState('CapsLock'))}
                      onBlur={() => setMayusculas(false)}
                      aria-invalid={errores.clave ? true : undefined}
                      aria-describedby={describeClave}
                    />
                    <button
                      type="button"
                      className="pub-campo-ver"
                      aria-controls="acceso-clave"
                      aria-pressed={verClave}
                      onClick={() => setVerClave((antes) => !antes)}
                    >
                      {verClave ? 'Ocultar' : 'Mostrar'}
                    </button>
                  </div>
                  {mayusculas && (
                    <p id="acceso-clave-mayus" className="pub-campo-nota">
                      Bloq Mayús está activado.
                    </p>
                  )}
                  {errores.clave && (
                    <p id="acceso-clave-error" className="pub-campo-error">
                      {errores.clave}
                    </p>
                  )}
                </div>

                <button type="submit" className="pub-boton pub-acceso-entrar" disabled={enviando}>
                  {enviando ? 'Entrando…' : 'Entrar'}
                </button>
              </form>

              <p className="pub-acceso-ayuda">
                ¿No puedes entrar? Escribe a <a href={`mailto:${CONTACTO}`}>{CONTACTO}</a>.
              </p>
            </>
          )}
        </section>
      </div>
    </CapaPublica>
  )
}

/** Cuánto tarda cada letra del título y cuánto espera antes de la primera. */
const LETRA_MS = 130
const ANTES_MS = 450

/**
 * El título se teclea letra a letra cada vez que se entra, y el punto hace de
 * cursor: va tras la última letra escrita y, al terminar, se queda
 * parpadeando, como si esperara a que escribas tú.
 *
 * El lector de pantalla oye el título entero desde el principio (`sr-only`);
 * lo que se teclea va oculto para él, que si no lo leería letra a letra. Con el
 * movimiento reducido sale entero y el punto no parpadea.
 */
function Tecleado({ texto }: { texto: string }) {
  const [quieto] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  const [escritas, setEscritas] = useState(quieto ? texto.length : 0)

  useEffect(() => {
    if (quieto) return
    let cuenta = 0
    let intervalo = 0
    const espera = window.setTimeout(() => {
      intervalo = window.setInterval(() => {
        cuenta += 1
        setEscritas(cuenta)
        if (cuenta >= texto.length) window.clearInterval(intervalo)
      }, LETRA_MS)
    }, ANTES_MS)
    return () => {
      window.clearTimeout(espera)
      window.clearInterval(intervalo)
    }
  }, [texto, quieto])

  const terminado = escritas >= texto.length
  return (
    <h1 className="pub-capitulo pub-tecleado" data-burbuja-refracta>
      <span className="sr-only">{texto}.</span>
      <span aria-hidden="true">{texto.slice(0, escritas)}</span>
      <span
        aria-hidden="true"
        className={terminado ? 'pub-tecleado-punto pub-tecleado-espera' : 'pub-tecleado-punto'}
      >
        .
      </span>
    </h1>
  )
}
