import { AUTORES, type Foto } from '../lib/fotos-portada'

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
export function Burbuja({ fotos, ancla = false }: { fotos: Foto[]; ancla?: boolean }) {
  return (
    <figure
      className={ancla ? 'pub-burbuja pub-burbuja-ancla' : 'pub-burbuja'}
      data-burbuja={fotos.map((foto) => foto.src).join(' ')}
      data-burbuja-foco={fotos.map((foto) => foto.foco).join(' ')}
    >
      <div className="pub-burbuja-forma">
        {fotos.map((foto) => (
          <img
            key={foto.src}
            src={foto.src}
            alt={foto.alt}
            style={{ objectPosition: `${foto.foco * 100}% 50%` }}
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

/** La línea de autoría de las fotos, para el pie. */
export function CreditosFotos() {
  return (
    <>
      Fotos de{' '}
      {AUTORES.map((foto, indice) => (
        <span key={foto.autor}>
          {indice > 0 && (indice === AUTORES.length - 1 ? ' y ' : ', ')}
          <a href={foto.perfil} target="_blank" rel="noreferrer">
            {foto.autor}
          </a>
        </span>
      ))}{' '}
      en Unsplash.
    </>
  )
}
