/**
 * La burbuja de la portada, en WebGL.
 *
 * Un solo lienzo fijo, a pantalla completa y detrás del contenido, dibuja una
 * burbuja de cristal que viaja con el scroll entre las «anclas» de la página:
 * huecos del diseño marcados con `data-burbuja`. En cada ancla se posa y se
 * llena con su foto; entre una y otra se aleja (se encoge y se oscurece, para
 * que el texto que cruza siga leyéndose), se estira según la velocidad y
 * cambia de foto con un frente que sale del centro.
 *
 * Todo lo que se ve sale del sombreador: la forma que respira, la lente que
 * aumenta el centro y comprime el borde, la dispersión de color en el canto, el
 * borde blanco y el reflejo. El DOM no se toca: las anclas siguen siendo la
 * burbuja de CSS con sus `<img>` y su texto alternativo, que es lo que ven
 * quien no tiene WebGL y el lector de pantalla.
 *
 * Coste: el cuadrado que se dibuja es solo el de la burbuja, no la pantalla, y
 * el bucle se para con la pestaña oculta y cuando la burbuja queda lejos.
 */

/** Cuánto tarda cada foto del carrusel del ancla que tiene varias. */
const RELEVO_MS = 6500
/** Cuánto dura el cambio de una foto a la siguiente. */
const CAMBIO_MS = 1400
/** Lado de la textura: potencia de dos, para tener mipmaps también en WebGL 1. */
const LADO_TEXTURA = 1024
/** El cuadrado dibujado mide esto por el radio: deja sitio al estiramiento. */
const MARGEN = 1.45

const VERTICES = `
attribute vec2 aPos;
uniform vec2 uCentro;
uniform float uRadio;
uniform vec2 uVista;
varying vec2 vP;
void main() {
  vP = aPos * ${MARGEN.toFixed(2)};
  vec2 px = uCentro + vec2(aPos.x, -aPos.y) * uRadio * ${MARGEN.toFixed(2)};
  gl_Position = vec4(px.x / uVista.x * 2.0 - 1.0, 1.0 - px.y / uVista.y * 2.0, 0.0, 1.0);
}
`

const FRAGMENTOS = `
precision highp float;
varying vec2 vP;
uniform sampler2D uFotoA;
uniform sampler2D uFotoB;
uniform float uMezcla;
uniform float uTiempo;
uniform vec2 uVelocidad;
uniform vec2 uPuntero;
uniform float uCerca;
uniform float uPixel;
uniform float uLejania;

vec3 muestra(sampler2D foto, vec2 n, float escala, float dispersion, float desenfoque) {
  vec2 c = vec2(0.5);
  float r = texture2D(foto, c + n * 0.5 * escala * (1.0 + dispersion), desenfoque).r;
  float g = texture2D(foto, c + n * 0.5 * escala, desenfoque).g;
  float b = texture2D(foto, c + n * 0.5 * escala * (1.0 - dispersion), desenfoque).b;
  return vec3(r, g, b);
}

void main() {
  float t = uTiempo;

  // Se estira en la dirección en que se mueve y adelgaza de lado.
  float rapidez = length(uVelocidad);
  float k = clamp(rapidez * 0.07, 0.0, 0.3);
  vec2 dir = rapidez > 0.0001 ? uVelocidad / rapidez : vec2(0.0, 1.0);
  vec2 lado = vec2(-dir.y, dir.x);
  vec2 q = dir * (dot(vP, dir) / (1.0 + k)) + lado * (dot(vP, lado) / (1.0 - 0.45 * k));

  // La forma respira: cuatro ondas lentas alrededor del borde, más fuertes
  // cuando se mueve o cuando el puntero se acerca, y un bulto hacia él.
  float a = atan(q.y, q.x);
  float fuerza = 1.0 + 3.2 * k + 0.7 * uCerca;
  float onda = 0.026 * sin(3.0 * a + t * 0.7)
             + 0.017 * sin(5.0 * a - t * 1.1 + 1.3)
             + 0.010 * sin(8.0 * a + t * 1.7 + 0.4)
             + 0.015 * sin(2.0 * a - t * 0.45 + 2.1);
  float lp = length(uPuntero);
  float bulto = lp > 0.0001
    ? 0.06 * uCerca * pow(max(dot(normalize(q + 1e-5), uPuntero / lp), 0.0), 4.0)
    : 0.0;
  float radio = 1.0 + onda * fuerza + bulto;
  float rr = length(q) / radio;
  if (rr > 1.04) discard;

  vec2 n = q / radio;
  float h = sqrt(max(1.0 - rr * rr, 0.0));
  float canto = 1.0 - h;

  // La lente: aumenta el centro y comprime hacia el borde, con la foto un poco
  // desplazada contra el puntero, como si estuviera detrás del cristal.
  float escala = mix(0.7, 1.0, pow(canto, 1.4)) * (0.95 + 0.025 * sin(t * 0.17));
  vec2 paralaje = -uPuntero * 0.03 * uCerca;
  float dispersion = 0.05 * pow(canto, 2.2);
  float desenfoque = 3.5 * pow(canto, 3.0);
  vec2 nf = n + paralaje;
  vec3 fotoA = muestra(uFotoA, nf, escala, dispersion, desenfoque);
  vec3 fotoB = muestra(uFotoB, nf, escala, dispersion, desenfoque);

  // El relevo entra desde el centro con un frente ondulado.
  float frente = uMezcla * 1.4 - 0.2;
  float m = smoothstep(frente + 0.12, frente - 0.12, rr + 0.05 * sin(a * 4.0 + t * 1.5));
  vec3 color = mix(fotoA, fotoB, m) * 0.93;

  // Lejos (entre dos anclas) se oscurece, para que el texto que cruza se lea.
  color *= 1.0 - 0.55 * uLejania;

  // La banda oscura de dentro del canto, como en el cristal grueso.
  color *= 1.0 - 0.7 * smoothstep(0.78, 0.97, rr);

  // El canto iridiscente: azul y violeta del lado de la luz, ámbar del otro.
  vec2 haciaLuz = normalize(vec2(-0.65 + 0.15 * sin(t * 0.2), 0.76) + uPuntero * 0.15 * uCerca);
  float cara = dot(normalize(q + 1e-5), haciaLuz);
  vec3 azul = vec3(0.32, 0.5, 1.0);
  vec3 violeta = vec3(0.64, 0.44, 1.0);
  vec3 ambar = vec3(1.0, 0.63, 0.2);
  vec3 tono = cara > 0.0 ? mix(violeta, azul, cara) : mix(violeta, ambar, -cara);
  float banda = smoothstep(0.885, 0.982, rr);
  color = mix(color, tono, banda * (0.5 + 0.45 * abs(cara)));
  float filo = smoothstep(0.972, 0.993, rr);
  color = mix(color, vec3(1.0), filo * (0.55 + 0.45 * max(cara, 0.0)));

  // El reflejo de la ventana, arriba a la izquierda.
  float reflejo = smoothstep(0.45, 0.0, length(n - vec2(-0.38, 0.44)));
  color += vec3(1.0) * reflejo * 0.12;

  float alfa = 1.0 - smoothstep(1.0 - uPixel * 1.5, 1.0, rr);
  float halo = (1.0 - smoothstep(1.0, 1.035, rr)) * 0.22 * (1.0 - alfa);
  gl_FragColor = vec4(color * alfa + tono * halo, alfa + halo);
}
`

type Rect = { x: number; y: number; r: number }

type Ancla = {
  nodo: HTMLElement
  fotos: string[]
  /** La foto del carrusel que toca ahora (las anclas de una sola, siempre 0). */
  actual: number
}

type Textura = { tex: WebGLTexture; lista: boolean }

/** Resorte con algo de rebote: sigue al objetivo con retraso y se pasa un poco. */
const RIGIDEZ = 120
const AMORTIGUACION = 2 * 0.68 * Math.sqrt(RIGIDEZ)

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
  alPerderse: () => void
): (() => void) | null {
  const contexto = lienzo.getContext('webgl', { premultipliedAlpha: true, antialias: false })
  if (!contexto || nodos.length === 0) return null
  // Con nombre propio y ya sin `null`: las funciones de dentro no heredan el
  // estrechamiento de tipo de una comprobación hecha fuera.
  const gl: WebGLRenderingContext = contexto

  const programa = compilar(gl)
  if (!programa) return null

  const anclas: Ancla[] = nodos.map((nodo) => ({
    nodo,
    fotos: (nodo.dataset.burbuja ?? '').split(/\s+/).filter(Boolean),
    actual: 0
  }))

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
    mezcla: u('uMezcla'),
    tiempo: u('uTiempo'),
    velocidad: u('uVelocidad'),
    puntero: u('uPuntero'),
    cerca: u('uCerca'),
    pixel: u('uPixel'),
    lejania: u('uLejania')
  }
  gl.uniform1i(uni.fotoA, 0)
  gl.uniform1i(uni.fotoB, 1)

  let destruida = false

  // Las texturas: un gris oscuro mientras la foto carga, recortada a cuadrado
  // al centro cuando llega.
  const texturas = new Map<string, Textura>()
  function textura(src: string): Textura {
    const ya = texturas.get(src)
    if (ya) return ya
    const tex = gl.createTexture()
    const entrada: Textura = { tex, lista: false }
    texturas.set(src, entrada)
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
        (anchoFoto - corte) / 2,
        (altoFoto - corte) / 2,
        corte,
        corte,
        0,
        0,
        LADO_TEXTURA,
        LADO_TEXTURA
      )
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

  // El estado del resorte, en píxeles CSS de la ventana.
  let pos = { x: 0, y: 0 }
  const vel = { x: 0, y: 0 }
  let radio = 0
  let velRadio = 0
  let iniciada = false
  const puntero = { x: -1e4, y: -1e4 }

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
   * cada una. Entre dos anclas se aparta hacia el centro, como si se alejara.
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
    if (a !== b && a.rect.y < mitad) s = suave((mitad - a.rect.y) / (b.rect.y - a.rect.y))
    const arco = Math.sin(Math.PI * s)
    return {
      x: a.rect.x + (b.rect.x - a.rect.x) * s - arco * ancho * 0.22,
      y: a.rect.y + (b.rect.y - a.rect.y) * s,
      r: (a.rect.r + (b.rect.r - a.rect.r) * s) * (1 - 0.22 * arco),
      a: a.ancla,
      b: b.ancla,
      s,
      lejania: arco
    }
  }

  let cuadro = 0
  let anterior = performance.now()
  const inicio = anterior

  function paso(ahora: number) {
    cuadro = requestAnimationFrame(paso)
    const dt = Math.min((ahora - anterior) / 1000, 1 / 30)
    anterior = ahora
    const meta = objetivo()
    if (!meta) return

    // El puntero atrae un poco a la burbuja cuando pasa cerca.
    const dx = puntero.x - pos.x
    const dy = puntero.y - pos.y
    const distancia = Math.hypot(dx, dy) / Math.max(radio, 1)
    const cerca = 1 - suave((distancia - 0.9) / 1.4)
    const mx = meta.x + dx * 0.05 * cerca
    const my = meta.y + dy * 0.05 * cerca

    if (!iniciada) {
      pos = { x: mx, y: my }
      radio = meta.r
      iniciada = true
    }
    vel.x += (RIGIDEZ * (mx - pos.x) - AMORTIGUACION * vel.x) * dt
    vel.y += (RIGIDEZ * (my - pos.y) - AMORTIGUACION * vel.y) * dt
    pos.x += vel.x * dt
    pos.y += vel.y * dt
    velRadio += (RIGIDEZ * (meta.r - radio) - AMORTIGUACION * velRadio) * dt
    radio += velRadio * dt

    // Qué fotos se mezclan: en viaje, la del ancla de arriba con la de abajo;
    // posada en un ancla con carrusel, la anterior con la actual.
    const quieta = meta.s < 0.001 || meta.a === meta.b
    if (quieta && meta.a.fotos.length > 1 && ahora - relevoDesde > RELEVO_MS) {
      fotoAnterior = meta.a.fotos[meta.a.actual]
      meta.a.actual = (meta.a.actual + 1) % meta.a.fotos.length
      relevoDesde = ahora
    }
    let fotoA: string
    let fotoB: string
    let mezcla: number
    if (quieta) {
      fotoB = meta.a.fotos[meta.a.actual]
      fotoA = fotoAnterior ?? fotoB
      mezcla = suave((ahora - relevoDesde) / CAMBIO_MS)
    } else {
      fotoA = meta.a.fotos[meta.a.actual]
      fotoB = meta.b.fotos[meta.b.actual]
      mezcla = suave((meta.s - 0.3) / 0.4)
      // Al volver a posarse no se repite un relevo que ya ocurrió.
      fotoAnterior = null
      relevoDesde = ahora - CAMBIO_MS
    }

    gl.clearColor(0, 0, 0, 0)
    gl.clear(gl.COLOR_BUFFER_BIT)
    const fuera = pos.y + radio * MARGEN < 0 || pos.y - radio * MARGEN > alto
    if (fuera || radio < 2) return

    gl.activeTexture(gl.TEXTURE0)
    gl.bindTexture(gl.TEXTURE_2D, textura(fotoA).tex)
    gl.activeTexture(gl.TEXTURE1)
    gl.bindTexture(gl.TEXTURE_2D, textura(fotoB).tex)
    gl.uniform2f(uni.centro, pos.x, pos.y)
    gl.uniform1f(uni.radio, radio)
    gl.uniform2f(uni.vista, ancho, alto)
    gl.uniform1f(uni.mezcla, mezcla)
    gl.uniform1f(uni.tiempo, (ahora - inicio) / 1000)
    gl.uniform2f(uni.velocidad, vel.x / radio, -vel.y / radio)
    gl.uniform2f(uni.puntero, dx / radio, -dy / radio)
    gl.uniform1f(uni.cerca, cerca)
    gl.uniform1f(uni.pixel, 1 / radio)
    gl.uniform1f(uni.lejania, meta.lejania)
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4)
  }

  function alMover(evento: PointerEvent) {
    puntero.x = evento.clientX
    puntero.y = evento.clientY
  }
  function alSalir() {
    puntero.x = -1e4
    puntero.y = -1e4
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
    window.removeEventListener('resize', medir)
    window.removeEventListener('pointermove', alMover)
    document.documentElement.removeEventListener('pointerleave', alSalir)
    document.removeEventListener('visibilitychange', alCambiarVisibilidad)
    lienzo.removeEventListener('webglcontextlost', alPerder)
    texturas.forEach(({ tex }) => gl.deleteTexture(tex))
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
