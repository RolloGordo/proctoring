# Semana 6 · P3 · Importación QTI 2.1

Responsable: Pierreluiggi. Estimación del plan: 6 h, no horas certificadas.
Rama: `feat/SPEC-003-importar-qti`. Base: `cb09aea`.

## Qué se implementó y por qué

`spikes/qti_import.py` contiene `parse_qti(xml)`, una función pura que devuelve
preguntas y diagnósticos. No abre archivos, no usa la red ni escribe en la base
de datos. Así Héctor puede llamarla desde su endpoint y decidir cómo mostrar las
preguntas omitidas antes de guardar el lote.

Las preguntas son argumentos compatibles con `NewQuestion`: Decimal conserva
los decimales de puntos y respuestas, y las opciones son pares texto/correcta.
El adaptador de la API debe convertir `question_type` a `QuestionType` y después
construir `NewQuestion(**fields)`. No se importan módulos de la API en el servicio
de IA: se conserva la separación entre servicios.

`spikes/qti_demo.py` es la demostración por consola. Convierte Decimal a cadenas
y las opciones al formato JSON de la API. La propiedad `issues` es de la vista
previa; al enviar a la API se usa únicamente `questions`. No envía solicitudes.

`tests/fixtures/qti/` contiene seis XML originales creados para este proyecto,
uno por tipo más uno con tolerancia numérica. No son exámenes de terceros ni un
dataset de aprendizaje automático. `tests/test_qti_import.py` verifica los cinco
tipos, puntuación, tolerancia, entradas inválidas, límites y omisiones explicadas.

## Soporte y límites explícitos

- Selección única, verdadero/falso por etiquetas inequívocas, número, completar
  texto y desarrollo con calificación manual.
- QTI 2.1, UTF-8, una interacción por ítem, texto sencillo. Máximo 1 MB y 200 ítems.
- Tolerancia numérica absoluta, inclusiva y simétrica: patrón explícito `equal`
  contra `correct`, con puntuación máxima o cero. Otros procesamientos se omiten.
- `match_correct` conserva su puntuación de un punto; `defaultValue` de SCORE
  no se interpreta erróneamente como puntuación máxima.
- No importa ZIP/SCORM, imágenes, MathML, crédito parcial, respuestas múltiples,
  reglas adaptativas ni QTI 1.2/3. Un manifiesto sin archivos de ítems no basta.
- No es un validador XSD completo ni un intérprete general de QTI. Los casos no
  representables se devuelven como diagnósticos, sin inventar respuestas.
- Rechaza DTD/entidades, XML malformado y límites excedidos. No carga recursos externos.
- Completar texto genera una advertencia: la API normaliza mayúsculas, tildes y
  espacios (conserva ñ), mientras QTI puede exigir coincidencia exacta. El adaptador
  debe mostrar `warnings` al docente antes de guardar; no se oculta esa diferencia.

## Reproducir y grabar evidencia

Desde `services/ai`, con uv instalado:

```powershell
uv sync --locked
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run python -m spikes.qti_demo tests/fixtures/qti/numeric_tolerance.xml --output results/qti-preview.json
```

Grabar la terminal ejecutando las pruebas, abrir el XML de tolerancia y el JSON
resultante, y explicar de dónde salen 3.14, 0.01 y los dos puntos. Mostrar también
una pregunta no soportada y su diagnóstico. No presentar esto como endpoint ya
desplegado: la conexión a la API corresponde a Héctor.

## Investigación

- https://www.imsglobal.org/question/qtiv2p1/imsqti_implv2p1.html
  Consultado el 08/10/2026 para comprobar la relación entre interacción y respuesta.
- https://www.imsglobal.org/question/qtiv2p1/imsqti_infov2p1.html
  Consultado para distinguir tipos de respuesta y reglas de puntuación.
- Contrato local: `services/api/src/proctoring_api/application/use_cases/manage_questions.py`
  en `cb09aea`. Se leyó para producir campos que la API reconoce; no se modificó.

## Estado

Implementación local y pruebas del parser. La validación de integración se registra
en la evidencia de la sesión. PR, CI remoto y endpoint: pendientes de publicación
y revisión del equipo. No se atribuyen seis horas reales por la estimación del plan.
