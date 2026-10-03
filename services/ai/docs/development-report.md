# Informe de desarrollo del módulo de audio

Responsable: Zevallos Bocanegra Piereluiggi (rzecvallosb1@upao.edu.pe).
Fecha de inicio: 03/10/2026.
Tarea inicial: SP-007, prueba de transcripción de voz en español.
Rama: feat/SP-007-spanish-transcription, creada desde origin/develop.

## Objetivo de la primera entrega

Ejecutar una prueba real que reciba un archivo de audio en español, produzca una transcripción y mida el tiempo de procesamiento. Con transcripciones de referencia se medirá la tasa de error por palabra (WER). Esta prueba no demuestra detección de fraude ni de voz sintética.

## Estado comprobado al iniciar

Se clonó el repositorio del equipo y se revisaron CLAUDE.md, el README general, services/ai/README.md, .gitignore y las instrucciones de evidencias. La carpeta services/ai contiene inicialmente solo su README. Algunos archivos descritos en los documentos, como worker_stub.py, pyproject.toml y docker-compose.yml, no están presentes en esta copia de develop. No se ha ejecutado un servicio de IA ni descargado modelos o datasets.

## Registro de cambios

### 03/10/2026 — Preparación del entorno

- Se clonó develop en la carpeta del escritorio Sistemas/Taller/proctoring.
- Se creó una rama exclusiva para SP-007.
- Se añadió services/ai/docs/development-report.md: este informe conserva el motivo de cada cambio y las evidencias de validación.
- Se añadió services/ai/docs/dataset-plan.md: define cómo registrar procedencia, etiquetas y separación de los datos antes de recoger audios.
- La clonación requirió usar el almacén de certificados de Windows mediante una opción local al comando de Git. No se desactivó la verificación TLS ni se modificó la configuración global.

## Cómo documentar cada implementación

Para cada archivo o carpeta añadido o modificado, registrar:

1. Ruta y tarea del backlog.
2. Problema que resuelve y razón para crearlo o modificarlo.
3. Entradas, salidas y relación con otros componentes.
4. Dependencias y motivo de elección, incluyendo versión y licencia cuando corresponda.
5. Comando de ejecución o reproducción.
6. Pruebas realizadas y resultados observados, distinguiendo resultados reales de metas.
7. Limitaciones, pendientes y evidencia asociada.

## Validación de esta entrega

Se comprobó la clonación y la creación de la rama. Esta entrega es preparación del espacio de trabajo y documentación; no constituye todavía una implementación funcional de SP-007. No se han creado commits, enviado cambios ni abierto un PR.

## Próximo incremento

Implementar la prueba autónoma de transcripción en services/ai/spikes, con salida reproducible y medición de tiempo. Evaluar small y, si el tiempo resulta excesivo, base según la guía del servicio. No inventar WER: requiere audio real y texto de referencia revisado.

## Coordinación pendiente

El CSV asigna HU-008 (foco de ventana) a Pierreluiggi, pero CLAUDE.md asigna el foco de Electron a Rider. Registrar la discrepancia y aclararla antes de implementar esa parte; no bloquea SP-007. La guía del servicio también menciona componentes aún ausentes y nombres de campos que deberán contrastarse con las migraciones antes de integrar.
