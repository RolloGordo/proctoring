# P5 · QTI 2.1 e IMS Content Packaging

En el plan anterior QTI se llamaba P3. En la guía nueva es P5, con 6 h estimadas.
Se conserva el parser de cinco tipos y se amplía sin modificar la API.

`parse_qti(xml)` devuelve preguntas internas y diagnósticos. `api_questions(result)`
convierte Decimal a texto y opciones a `{option_text, is_correct}`: su salida va
en `{"questions": [...]}` al endpoint del banco. La función no hace llamadas HTTP.

`parse_manifest(xml, resources)` recibe el manifiesto y un diccionario que contiene
los bytes de los archivos referenciados, por ejemplo `{"items/q1.xml": b"..."}`.
El manifiesto solo no contiene las preguntas. La extracción del ZIP pertenece al
adaptador de Héctor; esta función no extrae archivos ni descarga recursos.
Admite recursos `imsqti_item_xmlv2p1` del namespace IMS Content Packaging 1.1,
con límites de tamaño/cantidad. Rechaza URLs, rutas absolutas, `..`, DTD, entidades
y `xml:base`. Cada recurso no compatible deja un diagnóstico y se conserva el resto.
No es un ejecutor SCORM ni un importador general de objetos de aprendizaje.

Para producir JSON separado de los diagnósticos:

```powershell
uv run python -m spikes.qti_demo tests/fixtures/qti/numeric_tolerance.xml --output results/qti-revision.json --api-output results/qti-request.json
```

El cuerpo del POST es `qti-request.json`. El archivo de revisión conserva advertencias
y preguntas omitidas para revisarlas antes de importar. No se debe presentar el
lote omitido como si todas las preguntas se hubieran importado.

Se comprobaron seis fixtures que cubren cinco tipos (dos variantes numéricas)
contra `NewQuestion` y `Question.create` reales del repositorio. La atomicidad del
guardado pertenece al endpoint existente. No se probó un POST contra una base real
en esta entrega. Se mantienen las limitaciones del parser documentadas en P5-qti.md:
texto, interacción única y evaluación representable.
