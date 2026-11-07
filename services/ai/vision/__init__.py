"""API de imagen propia del proyecto (Jesús Limay, atributo de Disponibilidad).

Verificación facial con modelos gratuitos y livianos de OpenCV Zoo (YuNet +
SFace int8, unos 10 MB) que viajan **dentro de la imagen**: el worker no
descarga nada al arrancar, así que un arranque en frío sin red no deja la
verificación caída.

Se elige con la variable `FACE_ENGINE` (ver `face_pipeline.py`):

- `insightface` (por defecto, el motor de siempre)
- `opencv` (este paquete)

El por defecto no cambia hasta recalibrar `similarity_threshold` con
`datasets/sp007_own`: SFace mide en otra escala que ArcFace.
"""

from vision.opencv_sface import MODELOS, VerificadorOpenCV, verificar_modelos

__all__ = ["MODELOS", "VerificadorOpenCV", "verificar_modelos"]
