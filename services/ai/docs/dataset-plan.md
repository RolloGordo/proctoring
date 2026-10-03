# Registro y preparación del dataset de audio

Estado al 03/10/2026: no se han recopilado, descargado ni generado audios. Este documento define el registro previsto, no acredita que exista un dataset.

## Finalidad

SP-007 necesita audios en español con transcripción de referencia para medir WER. TA-006 exige posteriormente al menos 60 audios etiquetados: lecturas, consultas a un asistente con respuesta sintética y silencios. No se considera completo TA-006 por preparar esta guía.

## Registro por muestra

Guardar un manifiesto con identificador, ruta local relativa, procedencia, fecha de obtención, autorización o licencia, identificador anónimo de hablante, idioma, duración, formato, frecuencia de muestreo, escenario, pregunta asociada, transcripción de referencia revisada, etiqueta humana/sintética/desconocida y partición de datos. Para voz sintética, registrar también modelo o herramienta generadora, versión disponible y condiciones de uso. No incluir nombres personales ni credenciales.

## Organización prevista

Los audios se almacenarán en services/ai/datasets, excluido por el .gitignore existente. Los modelos se mantendrán fuera del historial en una carpeta models o en la caché del proveedor. El código, la documentación del origen y los resultados agregados sí podrán versionarse tras revisar que no expongan datos personales.

## Calidad y evaluación

Revisar manualmente las transcripciones de referencia y documentar cualquier normalización aplicada al cálculo de WER. Separar entrenamiento, validación y prueba; evitar que el mismo audio o sus variantes aparezcan en particiones distintas. Procurar separación por hablante y documentar límites de cobertura. Ajustar umbrales con validación y reservar la prueba para la evaluación final.

La comparación inicial de transcripción no sustituye la evaluación del clasificador de voz sintética. Una transcripción parecida a la pregunta, por sí sola, no debe generar una alerta.

## Evidencias que se completarán con datos reales

Cantidad y duración de muestras, distribución por escenario, fuentes y licencias, versiones de modelos, configuración y equipo de ejecución, WER, tiempo de carga del modelo y tiempo de inferencia por separado. No reportar métricas mientras no se hayan ejecutado las pruebas.
