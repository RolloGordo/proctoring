/**
 * La burbuja de la portada y del acceso, en WebGL.
 *
 * Un solo lienzo fijo, a pantalla completa, dibuja una burbuja de cristal que
 * viaja con el scroll entre las «anclas» de la página: huecos del diseño
 * marcados con `data-burbuja`. En cada ancla se posa y se llena con su foto;
 * entre una y otra se aleja (se encoge y se oscurece, para que el texto que
 * cruza siga leyéndose), se estira un poco según la velocidad y cambia de foto
 * con un frente que sale del centro.
 *
 * Un ancla con `data-burbuja-sigue` es la de ThoughtLab, si hay ratón: la
 * burbuja va vacía, de cristal oscuro, y sigue al cursor. Lo que tiene detrás
 * se ve a través de ella, aumentado y doblado en el canto: el texto marcado
 * con `data-burbuja-refracta` se copia a una textura, carácter a carácter y en
 * su sitio, y el sombreador la mira a través de la lente. Vuelve a su sitio
 * cuando el cursor entra en algo marcado con `data-burbuja-evita` o cuando se
 * escribe en ello.
 *
 * Todo lo que se ve sale del sombreador: la forma que respira, la esfera
 * iluminada (luz difusa, brillo, nube), la lente, la dispersión de color y el
 * filo blanco del canto. El DOM no se toca: las anclas siguen siendo la
 * burbuja de CSS con sus `<img>` y su texto alternativo, que es lo que ven
 * quien no tiene WebGL y el lector de pantalla.
 *
 * Coste: el cuadrado que se dibuja es solo el de la burbuja, no la pantalla; el
 * bucle se para con la pestaña oculta, y la textura del texto solo se rehace
 * cuando la burbuja lo toca y algo cambió.
 */

/** Cuánto tarda cada foto del carrusel del ancla que tiene varias. */
const RELEVO_MS = 6500
/** Cuánto dura el cambio de una foto a la siguiente. */
const CAMBIO_MS = 1400
/** Lado de la textura: potencia de dos, para tener mipmaps también en WebGL 1. */
const LADO_TEXTURA = 1024
/** El cuadrado dibujado mide esto por el radio: deja sitio al estiramiento. */
const MARGEN = 1.3
/** Lo más que se aleja el borde del centro, respirando y estirada. */
const ALCANCE = 1.1

const VERTICES = `
attribute vec2 aPos;
uniform vec2 uCentro;
uniform float uRadio;
uniform vec2 uVista;
varying vec2 vP;
varying vec2 vPx;
void main() {
  vP = aPos * ${MARGEN.toFixed(2)};
  vec2 px = uCentro + vec2(aPos.x, -aPos.y) * uRadio * ${MARGEN.toFixed(2)};
  vPx = px;
  gl_Position = vec4(px.x / uVista.x * 2.0 - 1.0, 1.0 - px.y / uVista.y * 2.0, 0.0, 1.0);
}
`

const FRAGMENTOS = `
precision highp float;
varying vec2 vP;
varying vec2 vPx;
uniform vec2 uCentro;
uniform float uRadio;
uniform vec2 uVista;
uniform sampler2D uFotoA;
uniform sampler2D uFotoB;
uniform sampler2D uTexto;
uniform float uMezcla;
uniform float uVacia;
uniform float uTiempo;
uniform vec2 uVelocidad;
uniform vec2 uPuntero;
uniform float uCerca;
uniform float uPixel;
uniform float uLejania;
uniform float uFundido;

float azar(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float ruido(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(azar(i), azar(i + vec2(1.0, 0.0)), f.x),
             mix(azar(i + vec2(0.0, 1.0)), azar(i + vec2(1.0, 1.0)), f.x), f.y);
}

vec3 muestra(sampler2D foto, vec2 n, float escala, float dispersion, float desenfoque) {
  vec2 c = vec2(0.5);
  float r = texture2D(foto, c + n * 0.5 * escala * (1.0 + dispersion), desenfoque).r;
  float g = texture2D(foto, c + n * 0.5 * escala, desenfoque).g;
  float b = texture2D(foto, c + n * 0.5 * escala * (1.0 - dispersion), desenfoque).b;
  return vec3(r, g, b);
}

void main() {
  float t = uTiempo;

  // Se estira poco en la dirección en que se mueve: lo justo para notar la
  // inercia sin que se vea estrujada.
  float rapidez = length(uVelocidad);
  float k = clamp(rapidez * 0.045, 0.0, 0.18);
  vec2 dir = rapidez > 0.0001 ? uVelocidad / rapidez : vec2(0.0, 1.0);
  vec2 lado = vec2(-dir.y, dir.x);
  vec2 q = dir * (dot(vP, dir) / (1.0 + k)) + lado * (dot(vP, lado) / (1.0 - 0.4 * k));

  // Respira con tres ondas largas y lentas, casi redonda, y se abomba un poco
  // hacia el puntero.
  float a = atan(q.y, q.x);
  float fuerza = 1.0 + 2.0 * k + 0.35 * uCerca;
  float onda = 0.017 * sin(2.0 * a - t * 0.35 + 2.1)
             + 0.012 * sin(3.0 * a + t * 0.5)
             + 0.006 * sin(5.0 * a - t * 0.7 + 1.3);
  float lp = length(uPuntero);
  float bulto = lp > 0.0001
    ? 0.035 * uCerca * pow(max(dot(normalize(q + 1e-5), uPuntero / lp), 0.0), 2.0)
    : 0.0;
  float radio = 1.0 + onda * fuerza + bulto;
  float rr = length(q) / radio;
  if (rr > ${ALCANCE.toFixed(2)} - 0.06) discard;

  // La esfera: su normal en cada punto, la luz arriba a la izquierda y algo
  // hacia quien mira, el brillo y el borde que refleja más (Fresnel).
  vec2 n = q / radio;
  float h = sqrt(max(1.0 - rr * rr, 0.0));
  float canto = 1.0 - h;
  vec3 normal = vec3(n, h);
  vec3 luz = normalize(vec3(-0.5 + 0.12 * sin(t * 0.2) + uPuntero.x * 0.1 * uCerca, 0.62, 0.62));
  float difusa = max(dot(normal, luz), 0.0);
  vec3 medio = normalize(luz + vec3(0.0, 0.0, 1.0));
  float brillo = pow(max(dot(normal, medio), 0.0), 70.0);
  float lustre = pow(max(dot(normal, medio), 0.0), 9.0);
  float fresnel = pow(canto, 2.6);

  // Con foto: la lente aumenta el centro y comprime hacia el borde, con la
  // foto un poco desplazada contra el puntero, como si estuviera detrás.
  float escala = mix(0.7, 1.0, pow(canto, 1.4)) * (0.95 + 0.025 * sin(t * 0.17));
  vec2 nf = n - uPuntero * 0.03 * uCerca;
  float dispersion = 0.05 * pow(canto, 2.2);
  float desenfoque = 3.5 * pow(canto, 3.0);
  vec3 fotoA = muestra(uFotoA, nf, escala, dispersion, desenfoque);
  vec3 fotoB = muestra(uFotoB, nf, escala, dispersion, desenfoque);
  float frente = uMezcla * 1.4 - 0.2;
  float m = smoothstep(frente + 0.12, frente - 0.12, rr + 0.05 * sin(a * 4.0 + t * 1.5));
  // Con el movimiento reducido no hay frente que avance: un fundido y ya.
  m = mix(m, uMezcla, uFundido);
  vec3 conFoto = mix(fotoA, fotoB, m) * (0.78 + 0.32 * difusa);

  // Vacía: humo oscuro con nube y luz de esfera, y a través del cristal el
  // texto de detrás. Se mira más cerca del centro de lo que está (la lente
  // aumenta), cerca del canto se dobla hacia dentro (el texto salta, como en
  // un vaso) y cada color va un poco desplazado, que es la dispersión.
  vec2 desdeCentro = vPx - uCentro;
  vec2 mira = desdeCentro * mix(0.58, 1.0, pow(canto, 1.2))
            - normalize(desdeCentro + 1e-5) * uRadio * 0.1 * pow(canto, 2.5);
  float separa = 0.06 * pow(canto, 1.5);
  vec4 tR = texture2D(uTexto, (uCentro + mira * (1.0 + separa)) / uVista);
  vec4 tG = texture2D(uTexto, (uCentro + mira) / uVista);
  vec4 tB = texture2D(uTexto, (uCentro + mira * (1.0 - separa)) / uVista);
  float nube = ruido(n * 2.4 + vec2(t * 0.05, -t * 0.04)) * 0.6
             + ruido(n * 5.1 - vec2(t * 0.07, t * 0.03)) * 0.4;
  vec3 humo = mix(vec3(0.3), vec3(0.015), smoothstep(0.0, 0.95, rr))
            * (0.6 + 0.6 * difusa)
            + (nube - 0.5) * 0.07;
  vec3 vacia = vec3(
    mix(humo.r, tR.r * 0.9, tR.a),
    mix(humo.g, tG.g * 0.9, tG.a),
    mix(humo.b, tB.b * 0.9, tB.a)
  );

  vec3 color = mix(conFoto, vacia, uVacia);

  // Lejos (entre dos anclas) se oscurece, para que el texto que cruza se lea.
  color *= 1.0 - 0.55 * uLejania;

  // La banda oscura de dentro del canto, como en el cristal grueso.
  color *= 1.0 - 0.55 * smoothstep(0.74, 0.93, rr);

  // El canto: ancho y de colores, azul y violeta del lado de la luz, ámbar
  // del otro, con el filo blanco encima y un resplandor cálido por dentro del
  // lado en sombra, que es la luz que atraviesa la esfera y sale por detrás.
  float cara = dot(normalize(q + 1e-5), normalize(luz.xy));
  vec3 azul = vec3(0.3, 0.52, 1.0);
  vec3 violeta = vec3(0.66, 0.46, 1.0);
  vec3 ambar = vec3(1.0, 0.62, 0.22);
  vec3 tono = cara > 0.0 ? mix(violeta, azul, cara) : mix(violeta, ambar, -cara);
  float banda = smoothstep(0.8, 0.975, rr);
  color = mix(color, tono, banda * (0.35 + 0.6 * abs(cara)));
  float filo = smoothstep(0.935, 0.988, rr);
  color = mix(color, vec3(1.0), filo * (0.45 + 0.5 * abs(cara)));
  float resplandor = smoothstep(0.55, 0.9, rr) * (1.0 - smoothstep(0.9, 0.97, rr)) * max(-cara, 0.0);
  color += ambar * resplandor * 0.18;
  // El brillo es suave a propósito: un punto blanco duro la convertía en una
  // bola de billar; en el cristal la luz se nota sobre todo en el canto.
  color += vec3(1.0) * (fresnel * 0.12 + lustre * 0.07 + brillo * 0.2);

  float alfa = 1.0 - smoothstep(1.0 - uPixel * 1.5, 1.0, rr);
  float halo = (1.0 - smoothstep(1.0, 1.035, rr)) * 0.2 * (1.0 - alfa);
  gl_FragColor = vec4(color * alfa + tono * halo, alfa + halo);
}
`

type Rect = { x: number; y: number; r: number }

type Ancla = {
  nodo: HTMLElement
  fotos: string[]
  /** La foto del carrusel que toca ahora (las anclas de una sola, siempre 0). */
  actual: number
  /** Sin foto: cristal oscuro que deja ver el texto de detrás. */
  vacia: boolean
  /** Sigue al cursor mientras la burbuja está posada en ella. */
  sigue: boolean
}

type Textura = { tex: WebGLTexture; lista: boolean }

/** Resorte con algo de rebote: sigue al objetivo con retraso y se pasa un poco. */
const RIGIDEZ = 120
const AMORTIGUACION = 2 * 0.72 * Math.sqrt(RIGIDEZ)
/** Detrás del cursor va más suelta, como si flotara: tarda más y rebota menos. */
const RIGIDEZ_CURSOR = 45
const AMORTIGUACION_CURSOR = 2 * 0.85 * Math.sqrt(RIGIDEZ_CURSOR)

export type OpcionesBurbuja = {
  /**
   * Quien pide menos movimiento: no viaja ni respira. Hay una burbuja quieta en
   * cada ancla, que sube y baja con la página como cualquier otra imagen, y el
   * carrusel cambia de foto con un fundido. Queda el cristal, que no es
   * movimiento.
   */
  sinMovimiento?: boolean
  /**
   * Hay ratón o lápiz (`hover: hover` y puntero fino). Sin él las anclas que
   * siguen al cursor se quedan con sus fotos: una burbuja vacía y quieta en un
   * teléfono no enseñaría nada.
   */
  conCursor?: boolean
  /**
   * Lo que la burbuja que sigue no pisa: si el cursor entra o se escribe ahí,
   * vuelve a su sitio. Con `lado`, además, no pasa de su borde izquierdo (el
   * formulario del acceso).
   */
  evita?: { nodo: HTMLElement; lado: boolean }[]
  /** El texto que se ve a través de la burbuja vacía. */
  refracta?: HTMLElement[]
  /**
   * Lo que tiene fondo propio en los bordes de la página (la cabecera, el
   * pie): la burbuja, vacía o con foto, pasa siempre por encima de ellos y no
   * por detrás, donde su fondo la cortaba en recto.
   */
  bordes?: HTMLElement[]
}

function entre(valor: number, minimo: number, maximo: number): number {
  return Math.min(Math.max(valor, minimo), Math.max(minimo, maximo))
}

function suave(t: number): number {
  const x = Math.min(Math.max(t, 0), 1)
  return x * x * (3 - 2 * x)
}

/**
 * Monta la burbuja sobre `lienzo`. Devuelve la función que la desmonta, o
 * `null` si el navegador no tiene WebGL: entonces se queda la de CSS.
 *
 * `respaldo` da, para cada foto, otra que probar si esa no carga.
 */
export function montarBurbuja(
  lienzo: HTMLCanvasElement,
  nodos: HTMLElement[],
  respaldo: (src: string) => string | undefined,
  alPerderse: () => void,
  {
    sinMovimiento = false,
    conCursor = false,
    evita = [],
    refracta = [],
    bordes = []
  }: OpcionesBurbuja = {}
): (() => void) | null {
  const contexto = lienzo.getContext('webgl', { premultipliedAlpha: true, antialias: false })
  if (!contexto || nodos.length === 0) return null
  // Con nombre propio y ya sin `null`: las funciones de dentro no heredan el
  // estrechamiento de tipo de una comprobación hecha fuera.
  const gl: WebGLRenderingContext = contexto

  const programa = compilar(gl)
  if (!programa) return null

  const anclas: Ancla[] = nodos.map((nodo) => {
    const fotos = (nodo.dataset.burbuja ?? '').split(/\s+/).filter(Boolean)
    const sigue = conCursor && nodo.dataset.burbujaSigue !== undefined
    // La que sigue va vacía: sus fotos son para la de CSS y para quien no
    // tiene ratón.
    const vacia = sigue || fotos.length === 0
    return { nodo, fotos: vacia ? [''] : fotos, actual: 0, vacia, sigue }
  })

  // Dónde cae el sujeto de cada foto a lo ancho (`data-burbuja-foco`, en el
  // mismo orden que las fotos): el recorte cuadrado se centra ahí.
  const focos = new Map<string, number>()
  nodos.forEach((nodo) => {
    const fotos = (nodo.dataset.burbuja ?? '').split(/\s+/).filter(Boolean)
    const valores = (nodo.dataset.burbujaFoco ?? '').split(/\s+/).map(Number)
    fotos.forEach((src, i) => focos.set(src, Number.isFinite(valores[i]) ? valores[i] : 0.5))
  })

  // El cuadrado: dos triángulos de -1 a 1.
  const bufer = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, bufer)
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW)
  const aPos = gl.getAttribLocation(programa, 'aPos')
  gl.enableVertexAttribArray(aPos)
  gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0)
  gl.useProgram(programa)
  gl.enable(gl.BLEND)
  gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA)

  const u = (nombre: string) => gl.getUniformLocation(programa, nombre)
  const uni = {
    centro: u('uCentro'),
    radio: u('uRadio'),
    vista: u('uVista'),
    fotoA: u('uFotoA'),
    fotoB: u('uFotoB'),
    texto: u('uTexto'),
    mezcla: u('uMezcla'),
    vacia: u('uVacia'),
    tiempo: u('uTiempo'),
    velocidad: u('uVelocidad'),
    puntero: u('uPuntero'),
    cerca: u('uCerca'),
    pixel: u('uPixel'),
    lejania: u('uLejania'),
    fundido: u('uFundido')
  }
  gl.uniform1i(uni.fotoA, 0)
  gl.uniform1i(uni.fotoB, 1)
  gl.uniform1i(uni.texto, 2)
  gl.uniform1f(uni.fundido, sinMovimiento ? 1 : 0)

  let destruida = false

  // Las texturas de las fotos: un gris oscuro mientras cargan, recortadas a
  // cuadrado alrededor de su foco cuando llegan.
  const texturas = new Map<string, Textura>()
  function textura(src: string): Textura {
    const ya = texturas.get(src)
    if (ya) return ya
    const tex = gl.createTexture()
    const entrada: Textura = { tex, lista: false }
    texturas.set(src, entrada)
    gl.activeTexture(gl.TEXTURE0)
    gl.bindTexture(gl.TEXTURE_2D, tex)
    gl.texImage2D(
      gl.TEXTURE_2D,
      0,
      gl.RGBA,
      1,
      1,
      0,
      gl.RGBA,
      gl.UNSIGNED_BYTE,
      new Uint8Array([26, 26, 26, 255])
    )
    // La vacía no tiene foto: se queda con el gris de espera, que no se ve.
    if (!src) return entrada
    cargar(src, (imagen) => {
      if (destruida) return
      const lado = document.createElement('canvas')
      lado.width = LADO_TEXTURA
      lado.height = LADO_TEXTURA
      const ctx = lado.getContext('2d')
      if (!ctx) return
      // Un SVG sin tamaño propio da 0: se dibuja a la medida de la textura.
      const anchoFoto = imagen.naturalWidth || LADO_TEXTURA
      const altoFoto = imagen.naturalHeight || LADO_TEXTURA
      const corte = Math.min(anchoFoto, altoFoto)
      ctx.drawImage(
        imagen,
        (anchoFoto - corte) * (focos.get(src) ?? 0.5),
        (altoFoto - corte) / 2,
        corte,
        corte,
        0,
        0,
        LADO_TEXTURA,
        LADO_TEXTURA
      )
      gl.activeTexture(gl.TEXTURE0)
      gl.bindTexture(gl.TEXTURE_2D, tex)
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true)
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, lado)
      gl.generateMipmap(gl.TEXTURE_2D)
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR)
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
      entrada.lista = true
    })
    return entrada
  }

  function cargar(src: string, listo: (imagen: HTMLImageElement) => void, segunda = false) {
    const imagen = new Image()
    imagen.decoding = 'async'
    imagen.onload = () => listo(imagen)
    imagen.onerror = () => {
      const otra = respaldo(src)
      if (!segunda && otra) cargar(otra, listo, true)
    }
    imagen.src = src
  }

  anclas.forEach((ancla) => ancla.fotos.forEach(textura))

  // La textura del texto que se ve a través: del tamaño de la ventana, sin
  // mipmaps (no es potencia de dos) y transparente hasta que se dibuja.
  const lienzoTexto = document.createElement('canvas')
  const texturaTexto = gl.createTexture()
  gl.activeTexture(gl.TEXTURE2)
  gl.bindTexture(gl.TEXTURE_2D, texturaTexto)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
  gl.texImage2D(
    gl.TEXTURE_2D,
    0,
    gl.RGBA,
    1,
    1,
    0,
    gl.RGBA,
    gl.UNSIGNED_BYTE,
    new Uint8Array([0, 0, 0, 0])
  )
  let firmaTexto = ''
  // La letra propia llega después del primer dibujo: entonces se rehace.
  void document.fonts?.ready.then(() => (firmaTexto = ''))

  /** ¿La burbuja, en `x`, `y` con radio `r`, toca algo de `lista`? */
  function toca(lista: HTMLElement[], x: number, y: number, r: number): boolean {
    const alcance = r * ALCANCE
    return lista.some((raiz) => {
      const caja = raiz.getBoundingClientRect()
      return (
        caja.width > 0 &&
        x + alcance > caja.left &&
        x - alcance < caja.right &&
        y + alcance > caja.top &&
        y - alcance < caja.bottom
      )
    })
  }

  /**
   * Copia el texto de `refracta` a la textura, cada carácter en el sitio
   * exacto en que lo pinta el navegador (`Range` por carácter): así, en el
   * canto, la copia empalma con el original. Solo si algo cambió: el texto,
   * su sitio, su opacidad o la ventana.
   */
  function actualizarTexto() {
    const ppp = Math.min(window.devicePixelRatio || 1, 1.5)
    const firma = [ancho, alto, ppp]
    for (const raiz of refracta) {
      const r = raiz.getBoundingClientRect()
      firma.push(Math.round(r.left), Math.round(r.top), Math.round(r.width))
      raiz
        .querySelectorAll('*')
        .forEach((hijo) => firma.push(Number(getComputedStyle(hijo).opacity)))
    }
    const clave = firma.join(',') + refracta.map((raiz) => raiz.textContent).join('|')
    if (clave === firmaTexto) return
    firmaTexto = clave

    lienzoTexto.width = Math.max(1, Math.round(ancho * ppp))
    lienzoTexto.height = Math.max(1, Math.round(alto * ppp))
    const ctx = lienzoTexto.getContext('2d')
    if (!ctx) return
    ctx.setTransform(ppp, 0, 0, ppp, 0, 0)
    ctx.clearRect(0, 0, ancho, alto)
    const rango = document.createRange()
    for (const raiz of refracta) {
      const andador = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT)
      for (let nodo = andador.nextNode(); nodo; nodo = andador.nextNode()) {
        const texto = nodo as Text
        const padre = texto.parentElement
        // Lo que solo existe para el lector de pantalla no se ve: no se copia.
        if (!padre || padre.closest('.sr-only')) continue
        const estilo = getComputedStyle(padre)
        let opacidad = 1
        for (
          let el: HTMLElement | null = padre;
          el && el !== raiz.parentElement;
          el = el.parentElement
        )
          opacidad *= Number(getComputedStyle(el).opacity)
        if (opacidad === 0) continue
        ctx.globalAlpha = opacidad
        ctx.fillStyle = estilo.color
        ctx.font = `${estilo.fontStyle} ${estilo.fontWeight} ${estilo.fontSize} ${estilo.fontFamily}`
        const medida = ctx.measureText('Hg')
        const sube = medida.fontBoundingBoxAscent
        const baja = medida.fontBoundingBoxDescent
        const mayusculas = estilo.textTransform === 'uppercase'
        for (let i = 0; i < texto.length; i++) {
          const letra = texto.data[i]
          if (/\s/.test(letra)) continue
          rango.setStart(texto, i)
          rango.setEnd(texto, i + 1)
          const caja = rango.getBoundingClientRect()
          if (caja.width === 0) continue
          const linea = caja.top + (caja.height - (sube + baja)) / 2 + sube
          ctx.fillText(mayusculas ? letra.toUpperCase() : letra, caja.left, linea)
        }
      }
    }
    gl.activeTexture(gl.TEXTURE2)
    gl.bindTexture(gl.TEXTURE_2D, texturaTexto)
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false)
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, lienzoTexto)
  }

  /**
   * ¿Tiene que ir el lienzo por encima de todo (`pub-lienzo-encima`)? Si la
   * burbuja vacía toca texto, para enseñarlo a través del cristal; y si
   * cualquiera toca la cabecera o el pie, para no quedar cortada por su fondo.
   * El resto del tiempo va detrás y no tapa nada. Si va encima y está vacía,
   * rehace la textura del texto.
   */
  function atenderTexto(x: number, y: number, r: number, vacia: number) {
    const conTexto = vacia > 0.5 && toca(refracta, x, y, r)
    const encima = conTexto || toca(bordes, x, y, r)
    lienzo.classList.toggle('pub-lienzo-encima', encima)
    if (encima && vacia > 0.5) actualizarTexto()
  }

  // El estado del resorte, en píxeles CSS de la ventana.
  let pos = { x: 0, y: 0 }
  const vel = { x: 0, y: 0 }
  let radio = 0
  let velRadio = 0
  let iniciada = false
  const puntero = { x: -1e4, y: -1e4 }
  // Solo un ratón o un lápiz «pasean» la burbuja: un dedo no tiene cursor.
  let hayCursor = false

  // El carrusel: cuándo cambió por última vez y desde qué foto.
  let relevoDesde = performance.now()
  let fotoAnterior: string | null = null

  let ancho = 0
  let alto = 0
  function medir() {
    const ppp = Math.min(window.devicePixelRatio || 1, 2)
    ancho = window.innerWidth
    alto = window.innerHeight
    lienzo.width = Math.round(ancho * ppp)
    lienzo.height = Math.round(alto * ppp)
    gl.viewport(0, 0, lienzo.width, lienzo.height)
  }
  medir()

  function rectDe(nodo: HTMLElement): Rect | null {
    const r = nodo.getBoundingClientRect()
    if (r.width === 0) return null
    return { x: r.left + r.width / 2, y: r.top + r.height / 2, r: r.width / 2 }
  }

  /**
   * A dónde va la burbuja ahora: entre el ancla que queda por encima del
   * centro de la pantalla y la que viene por debajo, según lo cerca que está
   * cada una. Se queda posada el primer y el último tramo del camino, y en
   * medio se aparta hacia el centro, como si se alejara.
   */
  function objetivo() {
    const visibles = anclas
      .map((ancla) => ({ ancla, rect: rectDe(ancla.nodo) }))
      .filter((v): v is { ancla: Ancla; rect: Rect } => v.rect !== null)
    if (visibles.length === 0) return null
    const mitad = alto / 2
    let i = 0
    while (i < visibles.length - 1 && visibles[i + 1].rect.y < mitad) i++
    const a = visibles[i]
    const b = visibles[Math.min(i + 1, visibles.length - 1)]
    let s = 0
    if (a !== b && a.rect.y < mitad)
      s = suave(((mitad - a.rect.y) / (b.rect.y - a.rect.y) - 0.12) / 0.76)
    const arco = Math.sin(Math.PI * s)
    return {
      x: a.rect.x + (b.rect.x - a.rect.x) * s - arco * ancho * 0.22,
      y: a.rect.y + (b.rect.y - a.rect.y) * s,
      r: (a.rect.r + (b.rect.r - a.rect.r) * s) * (1 - 0.22 * arco),
      anclaA: a,
      anclaB: b,
      s,
      lejania: arco
    }
  }

  let cuadro = 0
  let anterior = performance.now()
  const inicio = anterior

  type Trazo = {
    x: number
    y: number
    r: number
    fotoA: string
    fotoB: string
    mezcla: number
    vacia: number
    tiempo: number
    vx: number
    vy: number
    px: number
    py: number
    cerca: number
    lejania: number
  }

  function dibujar(t: Trazo) {
    if (t.y + t.r * MARGEN < 0 || t.y - t.r * MARGEN > alto || t.r < 2) return
    gl.activeTexture(gl.TEXTURE0)
    gl.bindTexture(gl.TEXTURE_2D, textura(t.fotoA).tex)
    gl.activeTexture(gl.TEXTURE1)
    gl.bindTexture(gl.TEXTURE_2D, textura(t.fotoB).tex)
    gl.activeTexture(gl.TEXTURE2)
    gl.bindTexture(gl.TEXTURE_2D, texturaTexto)
    gl.uniform2f(uni.centro, t.x, t.y)
    gl.uniform1f(uni.radio, t.r)
    gl.uniform2f(uni.vista, ancho, alto)
    gl.uniform1f(uni.mezcla, t.mezcla)
    gl.uniform1f(uni.vacia, t.vacia)
    gl.uniform1f(uni.tiempo, t.tiempo)
    gl.uniform2f(uni.velocidad, t.vx, t.vy)
    gl.uniform2f(uni.puntero, t.px, t.py)
    gl.uniform1f(uni.cerca, t.cerca)
    gl.uniform1f(uni.pixel, 1 / t.r)
    gl.uniform1f(uni.lejania, t.lejania)
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4)
  }

  /** El carrusel de un ancla con varias fotos: qué dos mezclar y cuánto. */
  function relevo(ancla: Ancla, ahora: number) {
    if (ancla.fotos.length > 1 && ahora - relevoDesde > RELEVO_MS) {
      fotoAnterior = ancla.fotos[ancla.actual]
      ancla.actual = (ancla.actual + 1) % ancla.fotos.length
      relevoDesde = ahora
    }
    const fotoB = ancla.fotos[ancla.actual]
    return { fotoA: fotoAnterior ?? fotoB, fotoB, mezcla: suave((ahora - relevoDesde) / CAMBIO_MS) }
  }

  function pasoQuieto(ahora: number) {
    gl.clearColor(0, 0, 0, 0)
    gl.clear(gl.COLOR_BUFFER_BIT)
    let encima = false
    let conTexto = false
    for (const ancla of anclas) {
      const rect = rectDe(ancla.nodo)
      if (!rect) continue
      if (ancla.vacia && toca(refracta, rect.x, rect.y, rect.r)) conTexto = true
      if (toca(bordes, rect.x, rect.y, rect.r)) encima = true
      const fotos =
        ancla.fotos.length > 1
          ? relevo(ancla, ahora)
          : { fotoA: ancla.fotos[0], fotoB: ancla.fotos[0], mezcla: 1 }
      dibujar({
        ...rect,
        ...fotos,
        vacia: ancla.vacia ? 1 : 0,
        tiempo: 0,
        vx: 0,
        vy: 0,
        px: 0,
        py: 0,
        cerca: 0,
        lejania: 0
      })
    }
    lienzo.classList.toggle('pub-lienzo-encima', encima || conTexto)
    if (conTexto) actualizarTexto()
  }

  /**
   * A dónde la lleva el cursor, si está posada en un ancla que sigue y nada
   * se lo impide; `null` si debe quedarse en su sitio.
   */
  function trasCursor(r: number, ancla: Rect): { x: number; y: number } | null {
    if (!hayCursor) return null
    // El ancla tiene que verse: una vez fuera de pantalla, no hay a quién seguir.
    if (ancla.y + ancla.r < 0 || ancla.y - ancla.r > alto) return null
    let tope = ancho + r * 0.4
    for (const { nodo, lado } of evita) {
      if (nodo.contains(document.activeElement)) return null
      const caja = nodo.getBoundingClientRect()
      const holgura = 24
      if (
        puntero.x > caja.left - holgura &&
        puntero.x < caja.right + holgura &&
        puntero.y > caja.top - holgura &&
        puntero.y < caja.bottom + holgura
      )
        return null
      if (lado && caja.bottom > 0 && caja.top < alto) tope = Math.min(tope, caja.left - r * 1.08)
    }
    // Puede asomarse por los bordes de la ventana y subir sobre la cabecera,
    // como la de ThoughtLab.
    return { x: entre(puntero.x, -r * 0.4, tope), y: entre(puntero.y, r * 0.2, alto - r * 0.2) }
  }

  function paso(ahora: number) {
    cuadro = requestAnimationFrame(paso)
    if (sinMovimiento) {
      pasoQuieto(ahora)
      return
    }
    const dt = Math.min((ahora - anterior) / 1000, 1 / 30)
    anterior = ahora
    const meta = objetivo()
    if (!meta) return
    const a = meta.anclaA.ancla
    const b = meta.anclaB.ancla
    const posada = meta.s < 0.001 || a === b

    const dx = puntero.x - pos.x
    const dy = puntero.y - pos.y
    const distancia = Math.hypot(dx, dy) / Math.max(radio, 1)
    const cerca = 1 - suave((distancia - 0.9) / 1.4)
    // Por defecto, el puntero solo la atrae un poco cuando pasa cerca.
    let mx = meta.x + dx * 0.05 * cerca
    let my = meta.y + dy * 0.05 * cerca
    const tras = posada && a.sigue ? trasCursor(meta.r, meta.anclaA.rect) : null
    if (tras) {
      mx = tras.x
      my = tras.y
    } else if (a.sigue && posada) {
      mx = meta.x
      my = meta.y
    }
    const rigidez = tras ? RIGIDEZ_CURSOR : RIGIDEZ
    const amortiguacion = tras ? AMORTIGUACION_CURSOR : AMORTIGUACION

    if (!iniciada) {
      pos = { x: mx, y: my }
      radio = meta.r
      iniciada = true
    }
    vel.x += (rigidez * (mx - pos.x) - amortiguacion * vel.x) * dt
    vel.y += (rigidez * (my - pos.y) - amortiguacion * vel.y) * dt
    pos.x += vel.x * dt
    pos.y += vel.y * dt
    velRadio += (RIGIDEZ * (meta.r - radio) - AMORTIGUACION * velRadio) * dt
    radio += velRadio * dt

    // Qué fotos se mezclan: en viaje, la del ancla de arriba con la de abajo;
    // posada en un ancla con carrusel, la anterior con la actual.
    let fotos: { fotoA: string; fotoB: string; mezcla: number }
    let vacia: number
    if (posada) {
      fotos = relevo(a, ahora)
      vacia = a.vacia ? 1 : 0
    } else {
      const mezcla = suave((meta.s - 0.3) / 0.4)
      fotos = { fotoA: a.fotos[a.actual], fotoB: b.fotos[b.actual], mezcla }
      vacia = (a.vacia ? 1 : 0) * (1 - mezcla) + (b.vacia ? 1 : 0) * mezcla
      // Al volver a posarse no se repite un relevo que ya ocurrió.
      fotoAnterior = null
      relevoDesde = ahora - CAMBIO_MS
    }

    atenderTexto(pos.x, pos.y, radio, vacia)
    gl.clearColor(0, 0, 0, 0)
    gl.clear(gl.COLOR_BUFFER_BIT)
    dibujar({
      x: pos.x,
      y: pos.y,
      r: radio,
      ...fotos,
      vacia,
      tiempo: (ahora - inicio) / 1000,
      vx: vel.x / radio,
      vy: -vel.y / radio,
      px: dx / radio,
      py: -dy / radio,
      cerca,
      lejania: meta.lejania
    })
  }

  function alMover(evento: PointerEvent) {
    puntero.x = evento.clientX
    puntero.y = evento.clientY
    hayCursor = evento.pointerType === 'mouse' || evento.pointerType === 'pen'
  }
  function alSalir() {
    puntero.x = -1e4
    puntero.y = -1e4
    hayCursor = false
  }
  function alCambiarVisibilidad() {
    cancelAnimationFrame(cuadro)
    if (!document.hidden) {
      anterior = performance.now()
      cuadro = requestAnimationFrame(paso)
    }
  }
  function alPerder(evento: Event) {
    evento.preventDefault()
    cancelAnimationFrame(cuadro)
    alPerderse()
  }

  window.addEventListener('resize', medir)
  window.addEventListener('pointermove', alMover, { passive: true })
  document.documentElement.addEventListener('pointerleave', alSalir)
  document.addEventListener('visibilitychange', alCambiarVisibilidad)
  lienzo.addEventListener('webglcontextlost', alPerder)
  cuadro = requestAnimationFrame(paso)

  return () => {
    destruida = true
    cancelAnimationFrame(cuadro)
    lienzo.classList.remove('pub-lienzo-encima')
    window.removeEventListener('resize', medir)
    window.removeEventListener('pointermove', alMover)
    document.documentElement.removeEventListener('pointerleave', alSalir)
    document.removeEventListener('visibilitychange', alCambiarVisibilidad)
    lienzo.removeEventListener('webglcontextlost', alPerder)
    texturas.forEach(({ tex }) => gl.deleteTexture(tex))
    gl.deleteTexture(texturaTexto)
    gl.deleteBuffer(bufer)
    gl.deleteProgram(programa)
  }
}

function compilar(gl: WebGLRenderingContext): WebGLProgram | null {
  const programa = gl.createProgram()
  const partes: [number, string][] = [
    [gl.VERTEX_SHADER, VERTICES],
    [gl.FRAGMENT_SHADER, FRAGMENTOS]
  ]
  for (const [tipo, fuente] of partes) {
    const sombreador = gl.createShader(tipo)
    if (!sombreador || !programa) return null
    gl.shaderSource(sombreador, fuente)
    gl.compileShader(sombreador)
    if (!gl.getShaderParameter(sombreador, gl.COMPILE_STATUS)) {
      console.warn('La burbuja no compila:', gl.getShaderInfoLog(sombreador))
      return null
    }
    gl.attachShader(programa, sombreador)
  }
  if (!programa) return null
  gl.linkProgram(programa)
  if (!gl.getProgramParameter(programa, gl.LINK_STATUS)) {
    console.warn('La burbuja no enlaza:', gl.getProgramInfoLog(programa))
    return null
  }
  return programa
}
