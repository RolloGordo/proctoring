# Recolección J1 — SPEC-007

Se necesitan 3–4 personas del equipo con consentimiento escrito, sin grabaciones personales en Git. Para cada clip `P01_01.mp4` se conserva localmente un `etiquetas/P01_01.txt` con líneas `00:00-00:12 mirando_pantalla`. El manifiesto tiene los campos `id,archivo,persona,condicion,duracion_s,sha256`. Guardar videos en `datasets/videos/` (no versionar); registrar SHA-256 exacto y dividir calibración de prueba final antes de optimizar umbrales. Registrar iluminación, lentes, teclado, mirada lateral, cara ausente, segunda persona y paso fugaz.

`python tools/dataset.py verificar` revisa rutas/hashes/etiquetas; `python tools/dataset.py registrar P01_01 videos/P01_01.mp4 P01 mirando_pantalla` añade un clip local con hash y duración obtenida de las etiquetas. Sin videos, la validación informa que el dataset está incompleto.
