import { CapaPublica } from '../components/Capas'

/**
 * Política de privacidad y de almacenamiento en el navegador.
 *
 * **Cada afirmación está contrastada con el código**, no escrita de memoria ni
 * copiada de otra plataforma: qué capturas se toman y cuándo
 * (`apps/desktop/src/main/capturas.ts`), qué guarda la base
 * (`supabase/migrations`), a quién se manda el audio (`services/ai`), qué se
 * guarda en el navegador (`lib/supabase.ts`, `lib/examen-guardado.ts`,
 * `supervision/calibration.ts`). Si el sistema cambia, esta página cambia con
 * él.
 *
 * Donde el sistema no hace algo que se podría esperar —borrar las evidencias
 * pasado un plazo—, lo dice. Una política que promete lo que el código no hace
 * es peor que no tener ninguna.
 */

/** A quién se escribe para ejercer los derechos. */
const CONTACTO = 'hsilvav2@upao.edu.pe'
const ACTUALIZADA = '3 de noviembre de 2026'

export function Privacidad() {
  return (
    <CapaPublica>
      <article className="pub-legal pub-marco">
        <h1 className="pub-capitulo">Privacidad.</h1>
        <p className="pub-intro">
          Qué datos trata Proctoring, para qué, quién los ve y cómo pides que los corrijamos o los
          borremos.
        </p>
        <p className="pub-legal-fecha">Última actualización: {ACTUALIZADA}</p>

        <section aria-labelledby="quien">
          <h2 id="quien">Quién es responsable</h2>
          <p>
            Proctoring es un proyecto académico del curso Taller Integrador 1 de la Universidad
            Privada Antenor Orrego (Trujillo, Perú). El equipo del proyecto es responsable de los
            datos que trata la plataforma. Para cualquier consulta sobre tus datos escribe a{' '}
            <a href={`mailto:${CONTACTO}`}>{CONTACTO}</a>.
          </p>
          <p>
            Tratamos tus datos conforme a la Ley N.° 29733, Ley de Protección de Datos Personales, y
            su reglamento, aprobado por el Decreto Supremo N.° 016-2024-JUS.
          </p>
        </section>

        <section aria-labelledby="que-datos">
          <h2 id="que-datos">Qué datos tratamos</h2>
          <h3>De tu cuenta</h3>
          <p>
            Tu nombre, tu correo, tu rol (docente o estudiante) y, si eres estudiante, tu código.
          </p>

          <h3>De tus exámenes</h3>
          <p>
            Tus respuestas, la hora en que entregas, tu nota y la decisión del docente sobre tu
            caso.
          </p>

          <h3>De la supervisión, solo mientras rindes</h3>
          <p>
            Solo se activan los módulos que eligió el docente para ese examen, y solo después de que
            aceptas. Según el examen, pueden registrarse:
          </p>
          <ul>
            <li>
              Avisos de lo que ocurre en tu equipo: si sales de la ventana del examen, si conectas
              otro monitor o si hay abiertas aplicaciones de captura, control remoto o máquinas
              virtuales.
            </li>
            <li>
              <strong>Una captura de tu pantalla principal</strong> cuando se detecta una de esas
              aplicaciones, un monitor adicional o que compartes la pantalla. Como máximo veinte por
              examen, separadas al menos cinco segundos.
            </li>
            <li>
              <strong>Una foto de tu cámara</strong> cuando se detecta que miras fuera de la
              pantalla, que no estás o que hay otra persona o un celular a la vista.
            </li>
            <li>
              <strong>Un fragmento de audio</strong> cuando el micrófono oye voz, y su transcripción
              en texto.
            </li>
            <li>
              Si el examen verifica tu identidad: una foto de referencia de tu rostro y una
              representación numérica de él, que sirve para compararlo.
            </li>
          </ul>
          <p>
            <strong>No se graba ni se envía vídeo continuo</strong>, ni de la cámara ni de la
            pantalla. Todo lo de la lista es puntual: solo sale de tu equipo cuando hay una señal.
          </p>
          <p>
            Como cualquier servidor, los nuestros registran la dirección IP y la hora de cada
            petición.
          </p>
        </section>

        <section aria-labelledby="sensibles">
          <h2 id="sensibles">Tu rostro es un dato sensible</h2>
          <p>
            La imagen de tu rostro y su representación numérica son datos biométricos, y la ley los
            considera sensibles. Solo los tratamos con tu consentimiento expreso, que das antes de
            empezar el examen, después de ver todo lo que se va a observar. Sin ese consentimiento
            no recibes ninguna pregunta.
          </p>
        </section>

        <section aria-labelledby="para-que">
          <h2 id="para-que">Para qué los usamos</h2>
          <p>
            Para supervisar que el examen se rinda en las condiciones que fijó el docente y para
            entregarle la evidencia de cada señal. Nada más: no se usan para publicidad ni se
            venden.
          </p>
          <p>
            <strong>El sistema no decide sobre ti.</strong> Calcula un nivel de riesgo y muestra la
            evidencia, pero no anula ni califica un examen por su cuenta. La decisión es siempre del
            docente y lleva una justificación escrita.
          </p>
        </section>

        <section aria-labelledby="quien-ve">
          <h2 id="quien-ve">Quién los ve</h2>
          <p>
            El docente que creó el examen. El equipo del proyecto solo accede para mantener la
            plataforma funcionando.
          </p>
          <p>
            Para funcionar usamos estos proveedores, que guardan o procesan datos por encargo
            nuestro:
          </p>
          <ul>
            <li>Supabase: base de datos, cuentas y archivos. Servidores en São Paulo, Brasil.</li>
            <li>Render: los servidores de la aplicación y del análisis de audio.</li>
            <li>Vercel: la página web.</li>
            <li>
              Upstash: la cola de trabajos de análisis. Servidores en Virginia, Estados Unidos.
            </li>
            <li>Deepgram: la transcripción de los fragmentos de audio. Estados Unidos.</li>
          </ul>
          <p>
            Ninguno de estos proveedores está en el Perú, así que tus datos se transfieren a otros
            países, entre ellos Brasil y Estados Unidos.
          </p>
        </section>

        <section aria-labelledby="cuanto">
          <h2 id="cuanto">Cuánto tiempo los guardamos</h2>
          <p>
            Las capturas y los fragmentos de audio se guardan en almacenamiento privado: solo se
            abren con un enlace firmado que caduca.
          </p>
          <p>
            Las evidencias y las fotos de referencia <strong>no tienen un plazo de borrado</strong>:
            se conservan para que el docente pueda revisar o reabrir un caso. Puedes pedir en
            cualquier momento que borremos las tuyas, y lo haremos.
          </p>
        </section>

        <section aria-labelledby="derechos">
          <h2 id="derechos">Tus derechos</h2>
          <p>
            Puedes pedir en cualquier momento acceder a tus datos, que los corrijamos, que los
            borremos, oponerte a que los tratemos o recibirlos en un formato que puedas llevarte.
            Escribe a <a href={`mailto:${CONTACTO}`}>{CONTACTO}</a> desde el correo de tu cuenta.
          </p>
          <p>
            Si crees que no atendimos bien tu pedido, puedes reclamar ante la Autoridad Nacional de
            Protección de Datos Personales.
          </p>
        </section>

        <section aria-labelledby="cookies">
          <h2 id="cookies">Cookies y almacenamiento en tu navegador</h2>
          <p>
            <strong>Proctoring no usa cookies.</strong> Tampoco analítica, publicidad ni
            herramientas de seguimiento de terceros. Solo guarda en tu navegador lo imprescindible
            para funcionar:
          </p>
          <ul>
            <li>La sesión de tu cuenta, para que no tengas que entrar en cada página.</li>
            <li>Que ya cerraste el aviso sobre este almacenamiento, para no repetírtelo.</li>
            <li>
              Durante un examen, una copia de tus respuestas y el ajuste de la cámara. Se borran
              solos al cerrar la ventana.
            </li>
          </ul>
          <p>
            Como nada de esto es opcional, no hay nada que aceptar o rechazar: sin la sesión no
            podrías entrar, y sin la copia podrías perder respuestas si se corta la conexión.
          </p>
        </section>

        <section aria-labelledby="cambios">
          <h2 id="cambios">Si esta política cambia</h2>
          <p>
            Lo publicaremos aquí, con la fecha nueva arriba. Si el cambio afecta a lo que se observa
            durante un examen, lo verás antes de dar tu consentimiento.
          </p>
          <p className="pub-legal-nota">
            Este texto describe un proyecto académico. Antes de usar la plataforma fuera del curso,
            debe revisarlo el área legal de la universidad.
          </p>
        </section>
      </article>
    </CapaPublica>
  )
}
