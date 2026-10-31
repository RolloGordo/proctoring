# -*- coding: utf-8 -*-
"""Monta las tres escenas del fondo de la portada con capturas reales.

Salen del propio sistema, de los exámenes del 20/10. Antes de usarlas se les
quita lo que no puede salir en una página pública:

- los correos de los estudiantes, que en el panel de alertas aparecen bajo cada
  aviso, subrayados en ámbar;
- las caras de las capturas de cámara.

El desenfoque no es decorativo: el JPEG se sirve a cualquiera que entre, y en
una página pública nadie tiene por qué poder leer el correo de un estudiante ni
reconocer su cara. Lo que la escena tiene que contar —que hay alertas, que
tienen hora, que cada una guarda su captura— se cuenta igual.
"""

import numpy as np
from PIL import Image, ImageFilter

ORIGEN = {
    "alertas": "image7.png",
    "linea": "image8.png",
    "evidencia": "image9.png",
}
SALIDA = r"C:\Users\Usuario\Desktop\proctoring\apps\web\public\portada"

#: El ámbar del subrayado de un enlace, que es como se pinta cada correo.
SUBRAYADO = (232, 167, 0)
#: Alto de la línea de texto que va encima del subrayado.
ALTO_CORREO = 20

LIENZO = (1600, 1000)
FONDO = (246, 247, 248)


def difuminar(imagen, caja, radio=14):
    """Desenfoca un rectángulo sobre la propia imagen."""
    recorte = imagen.crop(caja).filter(ImageFilter.GaussianBlur(radio))
    imagen.paste(recorte, caja)


def tapar_correos(imagen):
    """Encuentra los correos por su subrayado y los desenfoca."""
    pixeles = np.array(imagen)
    alto, ancho, _ = pixeles.shape
    es_subrayado = np.all(np.abs(pixeles.astype(int) - SUBRAYADO) <= 12, axis=2)
    tapados = 0
    for y in range(alto):
        columnas = np.flatnonzero(es_subrayado[y])
        # Un subrayado de correo es una tirada larga; un borde suelto no.
        if columnas.size < 60:
            continue
        x0, x1 = int(columnas[0]), int(columnas[-1]) + 1
        difuminar(imagen, (x0, max(0, y - ALTO_CORREO), min(ancho, x1), min(alto, y + 2)))
        tapados += 1

    # El último correo del panel queda cortado por el borde inferior y su
    # subrayado se va fuera de la imagen, así que no hay nada que encontrar.
    # Se tapa la franja entera: ahí abajo no hay nada que valga la pena leer, y
    # un correo visible en una página pública no se arregla después.
    difuminar(imagen, (0, alto - ALTO_CORREO - 12, ancho, alto))
    return tapados


def tapar_caras(imagen, cajas):
    for caja in cajas:
        difuminar(imagen, caja, radio=26)


def escena(imagen, destino):
    """Pone el panel a la derecha, que es donde el velo deja ver algo."""
    lienzo = Image.new("RGB", LIENZO, FONDO)
    alto = int(LIENZO[1] * 0.92)
    ancho = round(imagen.width * alto / imagen.height)
    panel = imagen.resize((ancho, alto), Image.LANCZOS)
    lienzo.paste(panel, (LIENZO[0] - ancho - 40, (LIENZO[1] - alto) // 2))
    lienzo.save(destino, quality=82, optimize=True)
    print(f"  {destino}  {lienzo.size}")


linea = Image.open(ORIGEN["linea"]).convert("RGB")
escena(linea, rf"{SALIDA}\foto-1.jpg")

alertas = Image.open(ORIGEN["alertas"]).convert("RGB")
print("  correos tapados:", tapar_correos(alertas))
escena(alertas, rf"{SALIDA}\foto-2.jpg")

evidencia = Image.open(ORIGEN["evidencia"]).convert("RGB")
tapar_caras(evidencia, [(570, 120, 955, 342), (570, 574, 955, 800)])
escena(evidencia, rf"{SALIDA}\foto-3.jpg")
