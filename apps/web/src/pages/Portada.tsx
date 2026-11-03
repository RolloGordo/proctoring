import { type CSSProperties, type RefObject, useEffect, useRef, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { CapaPublica } from '../components/Capas'
import { useAuth } from '../lib/auth-context'
import { inicioSegunRol } from '../lib/rutas'
import { montarBurbuja } from '../lib/burbuja'
import { authEnabled } from '../lib/supabase'

/**
 * La portada: lo primero que ve quien no ha iniciado sesión.
 *
 * Explica qué es el sistema antes de pedir credenciales. Quien ya tiene sesión
 * no pasa por aquí: va directo a su panel.
 *
 * **Dice solo lo que el sistema hace.** Lo que todavía no funciona en
 * producción lleva «En desarrollo» en vez de venderse como hecho: una portada
 * que promete más de lo que hay es lo primero que un docente evaluador detecta.
 *
 * La composición sale del propio lema. Sus tres verbos —detecta, documenta,
 * decide— abren cada uno su capítulo a tamaño de arquitectura, y el titular es
 * la frase que resume el proyecto: decide el docente.
 */

const DESCARGA = 'https://github.com/RolloGordo/proctoring/releases/latest'

/**
 * Las fotos de la burbuja, de Unsplash (licencia libre, créditos en el pie de
 * la portada). Cada una tiene un respaldo que vive en el repositorio por si el
 * fichero faltara: así la burbuja nunca queda vacía.
 */
type Foto = { src: string; respaldo: string; alt: string }

const FOTOS = {
  rinde: {
    src: '/portada/promo-rinde.jpg',
    respaldo: '/portada/foto-1.jpg',
    alt: 'Un estudiante con auriculares, concentrado frente a su portátil.'
  },
  escribe: {
    src: '/portada/promo-escribe.jpg',
    respaldo: '/portada/foto-2.jpg',
    alt: 'Un estudiante escribe en su portátil.'
  },
  casa: {
    src: '/portada/promo-casa.jpg',
    respaldo: '/portada/foto-3.jpg',
    alt: 'Un estudiante con auriculares rinde desde casa.'
  },
  camara: {
    src: '/portada/promo-camara.jpg',
    respaldo: '/portada/escena-senales.svg',
    alt: 'Una cámara web encendida sobre el monitor.'
  },
  docente: {
    src: '/portada/promo-docente.jpg',
    respaldo: '/portada/escena-docente.svg',
    alt: 'Una docente revisa en su portátil, frente a la pizarra.'
  },
  hoja: {
    src: '/portada/promo-hoja.jpg',
    respaldo: '/portada/escena-estudiante.svg',
    alt: 'Una mano marca las respuestas de una hoja de examen.'
  }
} satisfies Record<string, Foto>

const RESPALDOS = new Map(Object.values(FOTOS).map((foto) => [foto.src, foto.respaldo]))

/**
 * Lo que observa, y en qué estado está **en producción**.
 *
 * La consulta a una IA va por separado del habla, y en desarrollo: el habla se
 * detecta, se transcribe y llega al docente con su fragmento, pero la alerta de
 * consulta exige además la similitud con la pregunta y una voz sintética, y en
 * producción todavía no se calcula ninguna de las dos. Identidad igual: se
 * guarda la foto de referencia, pero ninguna verificación ha terminado aún de
 * punta a punta.
 */
const FAMILIAS = [
  {
    nombre: 'Entorno del equipo',
    texto:
      'Salir de la ventana del examen, conectar un segundo monitor o abrir aplicaciones de captura, control remoto o máquinas virtuales.',
    listo: true
  },
  {
    nombre: 'Mirada y presencia',
    texto:
      'Mirada fuera de la pantalla, rostro ausente, una segunda persona en cámara o un celular a la vista.',
    listo: true
  },
  {
    nombre: 'Habla durante el examen',
    texto:
      'Cuando el micrófono oye voz, el docente recibe el fragmento de audio y su transcripción para decidir.',
    listo: true
  },
  {
    nombre: 'Consulta a una IA por voz',
    texto:
      'Compara lo dicho con la pregunta en curso y escucha si responde una voz sintética. Solo avisa si ocurren las dos cosas.',
    listo: false
  },
  {
    nombre: 'Identidad',
    texto:
      'Verificación por rostro al entrar. Si la cámara no reconoce a alguien, el docente lo admite a mano.',
    listo: false
  }
]

const RECORRIDO = [
  {
    momento: 'Antes',
    titulo: 'El docente prepara el examen',
    texto: 'Elige las preguntas o su banco, decide qué se supervisa y recibe un código de acceso.'
  },
  {
    momento: 'Al entrar',
    titulo: 'El estudiante acepta',
    texto:
      'Ve todo lo que se va a observar antes de empezar. Sin su aceptación no recibe ni una pregunta.'
  },
  {
    momento: 'Durante',
    titulo: 'Se guardan señales, no vídeo',
    texto:
      'Cada señal queda con su hora, la pregunta en curso y su evidencia: una captura o un fragmento de voz.'
  },
  {
    momento: 'Después',
    titulo: 'El docente revisa',
    texto: 'Abre el expediente de cada estudiante, con el riesgo desglosado señal por señal.'
  }
]

const PRINCIPIOS = [
  {
    titulo: 'Auditor, no juez.',
    texto:
      'Calcula un riesgo desglosado por señal y entrega la evidencia. Nunca anula un examen por su cuenta: la decisión es del docente y lleva una justificación escrita.'
  },
  {
    titulo: 'Sin vídeo continuo.',
    texto:
      'La detección corre en el equipo del estudiante. Solo salen eventos, capturas sueltas y fragmentos de audio en los que hay voz.'
  },
  {
    titulo: 'Con consentimiento.',
    texto:
      'El estudiante ve, antes de empezar, cada cosa que se observa. La supervisión empieza cuando acepta, no antes.'
  }
]

type Caso = 'lee' | 'consulta'

/**
 * Lo único que el visitante toca: la regla que distingue al proyecto.
 *
 * Leer la pregunta en voz alta para concentrarse no es pedirle la respuesta a
 * una IA, y el sistema no los trata igual. Las frases son un ejemplo y lo dice;
 * los nombres de los campos y de los niveles son los del producto.
 */
const CASOS: Record<
  Caso,
  {
    opcion: string
    voz: string
    respuesta?: string
    similitud: string
    sintetica: string
    nivel: 'media' | 'alta'
    nivelTexto: string
    resultado: string
  }
> = {
  lee: {
    opcion: 'Lee la pregunta en voz alta',
    voz: '¿Qué mide la elasticidad precio de la demanda?',
    similitud: 'Alta',
    sintetica: 'No',
    nivel: 'media',
    nivelTexto: 'Media',
    resultado: 'Habla detectada. El docente recibe el fragmento y decide si importa.'
  },
  consulta: {
    opcion: 'Le pregunta a una IA',
    voz: 'Oye, ¿qué mide la elasticidad precio de la demanda?',
    respuesta: 'Mide cuánto cambia la cantidad demandada cuando cambia el precio…',
    similitud: 'Alta',
    sintetica: 'Sí',
    nivel: 'alta',
    nivelTexto: 'Alta',
    resultado: 'Posible consulta a una IA: se cumplen las dos condiciones.'
  }
}

export function Portada() {
  const { token, rol } = useAuth()
  const [caso, setCaso] = useState<Caso>('lee')
  const raiz = useRef<HTMLDivElement>(null)
  const lienzo = useRef<HTMLCanvasElement>(null)

  useAparecer(raiz)
  useBurbuja(raiz, lienzo)

  // Quien ya tiene sesión no necesita la portada: va a lo suyo.
  if (authEnabled && token && rol) return <Navigate to={inicioSegunRol(rol)} replace />

  const entrar = authEnabled ? '/login' : '/docente'
  const textoEntrar = authEnabled ? 'Iniciar sesión' : 'Entrar'
  const actual = CASOS[caso]

  return (
    <CapaPublica>
      <div ref={raiz}>
        <canvas ref={lienzo} className="pub-lienzo" aria-hidden="true" />

        <section className="pub-hero pub-marco" aria-labelledby="portada-titulo">
          {/* El salto va tras «el»: «Decide el / docente.» son dos líneas de
           * nueve y ocho letras. Tras «Decide», «el docente.» no cabía y salían
           * tres. */}
          {/* Nada del primer pantallazo espera a una animación: lo que explica
           * qué es esto tiene que estar a la vista desde el primer fotograma. El
           * movimiento de esta sección lo pone el relevo de las pantallas. */}
          <h1 id="portada-titulo" className="pub-hero-titulo">
            Decide el
            <br />
            docente.
          </h1>

          <div className="pub-hero-cuerpo">
            <div>
              <p className="pub-declaracion">
                Proctoring supervisa exámenes remotos y le entrega al docente la evidencia de cada
                señal. Nunca decide por él.
              </p>
              <div className="pub-acciones">
                <Link to={entrar} className="pub-boton">
                  {textoEntrar}
                </Link>
                <a href="#empieza" className="pub-enlace">
                  Rendir un examen
                </a>
              </div>
            </div>

            <Burbuja fotos={[FOTOS.rinde, FOTOS.escribe, FOTOS.casa]} />
          </div>
        </section>

        <section className="pub-seccion pub-marco" id="que-detecta" aria-labelledby="detecta">
          <div className="pub-capitulo-cabeza">
            <div>
              <h2 id="detecta" className="pub-capitulo" data-aparece>
                Detecta.
              </h2>
              <p className="pub-intro" data-aparece style={{ '--orden': 1 } as Estilo}>
                Mientras el estudiante rinde, cada módulo vigila una cosa y solo avisa cuando la ve.
              </p>
            </div>
            <Burbuja fotos={[FOTOS.camara]} ancla />
          </div>

          <ul className="pub-familias">
            {FAMILIAS.map((familia, indice) => (
              <li
                key={familia.nombre}
                className="pub-familia"
                data-aparece
                style={{ '--orden': indice } as Estilo}
              >
                <h3>{familia.nombre}</h3>
                <p>{familia.texto}</p>
                <span className="pub-familia-estado" data-listo={familia.listo || undefined}>
                  {familia.listo ? 'Disponible' : 'En desarrollo'}
                </span>
              </li>
            ))}
          </ul>

          <div className="pub-demo" data-aparece>
            <div>
              <h3>Leer la pregunta no es consultar a una IA.</h3>
              <p className="pub-demo-texto">
                Hay quien lee en voz alta para concentrarse. Elige un caso y mira cómo le llega cada
                uno al docente.
              </p>
              <div className="pub-demo-control" role="group" aria-label="Elige un caso">
                {(Object.keys(CASOS) as Caso[]).map((clave) => (
                  <button
                    key={clave}
                    type="button"
                    className="pub-opcion"
                    aria-pressed={caso === clave}
                    onClick={() => setCaso(clave)}
                  >
                    {CASOS[clave].opcion}
                  </button>
                ))}
              </div>
              <p className="pub-demo-nota">
                Las frases son un ejemplo. La regla es la del sistema: la alerta de consulta exige
                las dos condiciones a la vez.
              </p>
            </div>

            {/* La región que se anuncia es fija; lo que cambia va dentro. Si
             * la propia región se remontara con la `key`, el lector de
             * pantalla no anunciaría el cambio. La `key` es para repetir la
             * pequeña animación al cambiar de caso. */}
            <div aria-live="polite">
              <div data-ui key={caso}>
                <div className="pub-ui-cabeza">
                  <strong>Fragmento de voz</strong>
                  <span>Pregunta 3 · 12:07:10</span>
                </div>
                <div className="pub-ui-cuerpo">
                  <blockquote className="pub-ui-cita">
                    <small>Estudiante</small>«{actual.voz}»
                  </blockquote>
                  {actual.respuesta && (
                    <blockquote className="pub-ui-cita" data-sintetica>
                      <small>Segunda voz</small>«{actual.respuesta}»
                    </blockquote>
                  )}
                  <dl className="pub-ui-medidas">
                    <dt>Similitud con la pregunta</dt>
                    <dd>{actual.similitud}</dd>
                    <dt>Voz sintética</dt>
                    <dd>{actual.sintetica}</dd>
                  </dl>
                  <p className="pub-ui-resultado">
                    <span className="pub-ui-nivel" data-nivel={actual.nivel}>
                      {actual.nivelTexto}
                    </span>
                    {actual.resultado}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="pub-seccion pub-marco" id="como-funciona" aria-labelledby="documenta">
          <h2 id="documenta" className="pub-capitulo" data-aparece>
            Documenta.
          </h2>
          <p className="pub-intro" data-aparece style={{ '--orden': 1 } as Estilo}>
            No se graba vídeo. Cada señal queda en el expediente con su hora y su evidencia.
          </p>

          <div className="pub-documenta">
            <ol className="pub-recorrido">
              {RECORRIDO.map((paso, indice) => (
                <li key={paso.momento} data-aparece style={{ '--orden': indice } as Estilo}>
                  <span className="pub-momento">{paso.momento}</span>
                  <h3>{paso.titulo}</h3>
                  <p>{paso.texto}</p>
                </li>
              ))}
            </ol>

            <div data-ui data-aparece style={{ '--orden': 2 } as Estilo}>
              <div className="pub-ui-cabeza">
                <strong>Expediente del estudiante</strong>
                <span>Riesgo: medio</span>
              </div>
              <ol className="pub-linea">
                <li>
                  <time>12:06:58</time>
                  <span>
                    Monitor adicional
                    <small>2 monitores conectados</small>
                  </span>
                  <span className="pub-ui-nivel" data-nivel="media">
                    Media
                  </span>
                </li>
                <li>
                  <time>12:07:00</time>
                  <span>
                    Aplicación sospechosa
                    <small>Control remoto en ejecución</small>
                  </span>
                  <span className="pub-ui-nivel" data-nivel="alta">
                    Alta
                  </span>
                </li>
                <li>
                  <time>12:07:12</time>
                  <span>
                    Mirada fuera de pantalla
                    <small>Giro de cabeza de 29°, umbral 25° · con captura</small>
                  </span>
                  <span className="pub-ui-nivel" data-nivel="baja">
                    Baja
                  </span>
                </li>
              </ol>
              <div className="pub-ui-decision">
                <p>Decisión del docente</p>
                <blockquote>
                  Confirmada. La aplicación de control remoto estuvo abierta durante todo el examen.
                </blockquote>
              </div>
            </div>
          </div>
        </section>

        <section className="pub-seccion pub-marco" id="principios" aria-labelledby="decide">
          <div className="pub-capitulo-cabeza">
            <h2 id="decide" className="pub-capitulo" data-aparece>
              Decide.
            </h2>
            <Burbuja fotos={[FOTOS.docente]} ancla />
          </div>

          <div className="pub-decide">
            <div className="pub-principios">
              {PRINCIPIOS.map((principio, indice) => (
                <article
                  key={principio.titulo}
                  className="pub-principio"
                  data-aparece
                  style={{ '--orden': indice } as Estilo}
                >
                  <h3>{principio.titulo}</h3>
                  <p>{principio.texto}</p>
                </article>
              ))}
            </div>

            <aside className="pub-cifra" data-aparece style={{ '--orden': 1 } as Estilo}>
              <strong>4,4 s</strong>
              <p>
                tarda de media el análisis de un fragmento de voz en el servidor, medido sobre 18
                fragmentos de exámenes reales. El objetivo del proyecto es menos de 10 s.
              </p>
            </aside>
          </div>
        </section>

        <section className="pub-seccion pub-marco" id="empieza" aria-labelledby="empieza-titulo">
          <div className="pub-capitulo-cabeza">
            <h2 id="empieza-titulo" className="pub-capitulo" data-aparece>
              Empieza.
            </h2>
            <Burbuja fotos={[FOTOS.hoja]} ancla />
          </div>

          <div className="pub-puertas">
            <article className="pub-puerta" data-aparece>
              <h3>Si eres docente</h3>
              <p>
                Desde el navegador: crea tus cursos y exámenes, elige qué se supervisa, admite a tus
                estudiantes y recibe las alertas mientras el examen ocurre.
              </p>
              <div className="pub-acciones">
                <Link to={entrar} className="pub-boton">
                  {textoEntrar}
                </Link>
              </div>
            </article>

            <article className="pub-puerta" data-aparece style={{ '--orden': 1 } as Estilo}>
              <h3>Si eres estudiante</h3>
              <p>
                El examen se rinde en la aplicación de escritorio, en una ventana protegida. Pide la
                cámara y el micrófono solo después de que aceptas.
              </p>
              <div className="pub-acciones">
                <a href={DESCARGA} className="pub-enlace" target="_blank" rel="noreferrer">
                  Descargar para Windows
                </a>
              </div>
            </article>
          </div>
        </section>
      </div>
    </CapaPublica>
  )
}

type Estilo = CSSProperties & Record<'--orden', number>

/**
 * La burbuja: un hueco del diseño donde se posa la de WebGL.
 *
 * Por sí sola es la burbuja de CSS con sus fotos, que es lo que se ve sin
 * WebGL o con el movimiento reducido. Cuando la de WebGL arranca, esta se
 * vuelve transparente pero sigue en su sitio: marca dónde posarse y conserva
 * el texto alternativo para el lector de pantalla.
 *
 * `ancla` es la de los capítulos: más pequeña y solo en pantallas anchas,
 * donde junto al título queda sitio libre.
 */
function Burbuja({ fotos, ancla = false }: { fotos: Foto[]; ancla?: boolean }) {
  return (
    <figure
      className={ancla ? 'pub-burbuja pub-burbuja-ancla' : 'pub-burbuja'}
      data-burbuja={fotos.map((foto) => foto.src).join(' ')}
    >
      <div className="pub-burbuja-forma">
        {fotos.map((foto) => (
          <img
            key={foto.src}
            src={foto.src}
            alt={foto.alt}
            width={1200}
            height={1200}
            decoding="async"
            onError={(e) => {
              const img = e.currentTarget
              // Una sola vez: si el respaldo tampoco estuviera, volver a
              // asignarlo dispararía `onError` otra vez, y en bucle.
              if (img.dataset.respaldo === 'si') {
                img.style.display = 'none'
                return
              }
              img.dataset.respaldo = 'si'
              img.src = foto.respaldo
            }}
          />
        ))}
      </div>
    </figure>
  )
}

/**
 * Arranca la burbuja de WebGL sobre las anclas de la página.
 *
 * No arranca con el movimiento reducido: la burbuja que viaja, se estira y
 * respira es justo lo que esa preferencia pide no ver. Tampoco sin WebGL. En
 * los dos casos se queda la de CSS, quieta.
 */
function useBurbuja(
  raiz: RefObject<HTMLDivElement | null>,
  lienzo: RefObject<HTMLCanvasElement | null>
) {
  useEffect(() => {
    const nodo = raiz.current
    const canvas = lienzo.current
    if (!nodo || !canvas) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    const anclas = Array.from(nodo.querySelectorAll<HTMLElement>('[data-burbuja]'))
    const desmontar = montarBurbuja(
      canvas,
      anclas,
      (src) => RESPALDOS.get(src),
      () => nodo.classList.remove('pub-con-burbuja')
    )
    if (!desmontar) return
    nodo.classList.add('pub-con-burbuja')

    return () => {
      desmontar()
      nodo.classList.remove('pub-con-burbuja')
    }
  }, [raiz, lienzo])
}

/**
 * Enseña cada `[data-aparece]` cuando entra en pantalla, **cada vez**.
 *
 * Al salir del todo de la pantalla se vuelve a esconder, así que al volver a
 * pasar por él aparece otra vez: la página no se queda «ya cargada» después
 * del primer recorrido. Son dos observadores porque el que enseña espera a que
 * la pieza suba un poco (el margen de abajo), y ese margen no sirve para
 * esconder: la pieza desaparecería mientras todavía se ve en el borde.
 *
 * La clase `pub-js` va en `<html>` y es la que esconde lo que todavía no se ha
 * visto: sin este script nada se esconde, y si el navegador no tiene
 * `IntersectionObserver`, todo se enseña de golpe en vez de quedarse oculto.
 */
function useAparecer(raiz: RefObject<HTMLDivElement | null>) {
  useEffect(() => {
    const nodo = raiz.current
    if (!nodo) return
    const piezas = Array.from(nodo.querySelectorAll<HTMLElement>('[data-aparece]'))

    if (typeof IntersectionObserver === 'undefined') {
      piezas.forEach((pieza) => pieza.classList.add('visto'))
      return
    }

    document.documentElement.classList.add('pub-js')
    const ensena = new IntersectionObserver(
      (entradas) => {
        for (const entrada of entradas) {
          if (entrada.isIntersecting) entrada.target.classList.add('visto')
        }
      },
      { rootMargin: '0px 0px -10% 0px', threshold: 0.12 }
    )
    const esconde = new IntersectionObserver((entradas) => {
      for (const entrada of entradas) {
        if (!entrada.isIntersecting) entrada.target.classList.remove('visto')
      }
    })
    piezas.forEach((pieza) => {
      ensena.observe(pieza)
      esconde.observe(pieza)
    })

    return () => {
      ensena.disconnect()
      esconde.disconnect()
      document.documentElement.classList.remove('pub-js')
    }
  }, [raiz])
}
