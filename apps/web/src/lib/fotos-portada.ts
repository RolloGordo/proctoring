/**
 * Las fotos de la burbuja, de Unsplash (licencia de Unsplash: uso libre, sin
 * atribución obligatoria; la damos igual en el pie). Se sirven desde nuestro
 * dominio, no desde el de Unsplash: la portada no le hace peticiones a nadie
 * más, como dice la política de privacidad.
 *
 * `foco` es dónde cae el sujeto a lo ancho (0 izquierda, 1 derecha): la
 * burbuja es cuadrada y recorta los lados, y sin él el estudiante de la
 * primera quedaba cortado. Cada una tiene un respaldo del repositorio por si
 * el fichero faltara: así la burbuja nunca queda vacía.
 *
 * En WebP desde el 13/11/2026: de 611 a 248 KB las seis, sin diferencia
 * visible a ese tamaño. Los JPG originales siguen en `public/portada/`.
 */
export type Foto = {
  src: string
  respaldo: string
  alt: string
  foco: number
  autor: string
  perfil: string
}

export const FOTOS = {
  rinde: {
    src: '/portada/promo-rinde.webp',
    respaldo: '/portada/foto-1.jpg',
    alt: 'Un estudiante con auriculares, concentrado frente a su portátil.',
    foco: 0.3,
    autor: 'Wes Hicks',
    perfil: 'https://unsplash.com/@sickhews'
  },
  escribe: {
    src: '/portada/promo-escribe.webp',
    respaldo: '/portada/foto-2.jpg',
    alt: 'Un estudiante escribe en su portátil.',
    foco: 0.5,
    autor: 'Christian Velitchkov',
    perfil: 'https://unsplash.com/@cvelitchkov'
  },
  casa: {
    src: '/portada/promo-casa.webp',
    respaldo: '/portada/foto-3.jpg',
    alt: 'Un estudiante con auriculares rinde desde casa.',
    foco: 0.5,
    autor: 'Vitaly Gariev',
    perfil: 'https://unsplash.com/@silverkblack'
  },
  camara: {
    src: '/portada/promo-camara.webp',
    respaldo: '/portada/escena-senales.svg',
    alt: 'Una cámara web sobre el monitor.',
    foco: 0.45,
    autor: 'Emiliano Cicero',
    perfil: 'https://unsplash.com/@emilianocicero'
  },
  docente: {
    src: '/portada/promo-docente.webp',
    respaldo: '/portada/escena-docente.svg',
    alt: 'Una docente revisa en su portátil, frente a la pizarra.',
    foco: 0.5,
    autor: 'Vitaly Gariev',
    perfil: 'https://unsplash.com/@silverkblack'
  },
  hoja: {
    src: '/portada/promo-hoja.webp',
    respaldo: '/portada/escena-estudiante.svg',
    alt: 'Una mano marca las respuestas de una hoja de examen.',
    foco: 0.6,
    autor: 'Nguyen Dang Hoang Nhu',
    perfil: 'https://unsplash.com/@nguyendhn'
  }
} satisfies Record<string, Foto>

export const RESPALDOS = new Map(Object.values(FOTOS).map((foto) => [foto.src, foto.respaldo]))

/** Cada autor una vez, en el orden en que salen sus fotos. */
export const AUTORES = Object.values(FOTOS).filter(
  (foto, indice, todas) => todas.findIndex((otra) => otra.autor === foto.autor) === indice
)
