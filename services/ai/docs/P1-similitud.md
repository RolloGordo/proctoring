# Semana 6 · P1 · Similitud con el enunciado

Responsable: Pierreluiggi. Nueva guía: 4 h estimadas. Rama prevista: `feat/SPEC-008-similitud`.
No se registran esas horas como realizadas automáticamente.

## Archivos y propósito

- `spikes/similarity.py`: valida grabaciones y hashes; ejecuta Whisper small;
  compara la transcripción REAL con el enunciado mediante MiniLM; elige umbral
  con calibración y calcula ROC, AUC y FPR sobre prueba final separada.
- `spikes/prepare_pairs.py`: convierte el plan completado en manifiesto; calcula
  SHA-256 sobre los archivos reales y se niega a inventar referencias o grabaciones.
- `docs/P1-recording-plan.json` y la guía personal separada: 63 guiones originales
  asistidos por IA, 21 preguntas × 3 clases. No son observaciones medidas.
- `tests/test_similarity.py`: curvas con empates, puntuaciones inválidas y prueba
  de que alterar el test no altera el umbral elegido en calibración.
- `pyproject.toml` y `uv.lock`: dependencia opcional `similarity`, separada del
  entorno ligero de SP-007 y CI. Los modelos y audios siguen ignorados por Git.

## Decisiones que debes explicar

Q01–Q14: 42 audios de calibración. Q15–Q21: 21 de test final. Una misma pregunta
no puede aparecer en ambos conjuntos, aunque se cambie su identificador.
La selección del umbral maximiza TPR−FPR en calibración, con desempate a menor
FPR y mayor umbral. Se compara además con el umbral de referencia proporcionado
por configuración, sin fijar el umbral del sistema en el código.

Las clases reading y dictation son positivas de similitud; unrelated es negativa.
El FPR aquí significa habla no relacionada que parece similar. NO es la tasa de
acusaciones falsas. Una lectura puede puntuar alto sin generar alerta.

Se emplean embeddings normalizados y coseno limitado a [0,1], sin interpretarlo
como probabilidad. Una transcripción vacía obtiene 0. Los textos que exceden el
contexto del modelo se rechazan para evitar truncarlos silenciosamente.

Los resultados incluyen manifiesto hash, revisión del modelo, entorno, WER de
Whisper por muestra, tiempos, puntuaciones y hablantes compartidos entre splits.
Un solo hablante limita la generalización; no se oculta esa condición.

## Ejecución cuando existan grabaciones

Desde `services/ai`:

```powershell
uv sync --locked --extra similarity
uv run python -m spikes.prepare_pairs docs/P1-recording-plan.json datasets/p1_own
uv run --extra similarity python -m spikes.similarity datasets/p1_own/manifest.csv --revision e8f8c211226b894fcb81acc59f3b34ba3efd5f42 --reference-threshold 0.6 --output results/similarity.json
```

Primero completar el plan con archivos reales y referencias revisadas. Las
ejecuciones preservan resultados anteriores exigiendo un nombre de salida nuevo.
Los puntos de ROC se guardan en JSON. La figura exportable y las métricas finales
se elaborarán con la evaluación real, no con puntuaciones inventadas.

## Investigación

https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

Consultado el 08/10/2026 para confirmar interfaz, dimensión 384 y longitud de
contexto del modelo solicitado. La revisión se consultó en Hugging Face y se
fijó en `e8f8c211226b894fcb81acc59f3b34ba3efd5f42` para no depender de `main`.

## Pendiente para cerrar P1

Consentimientos, grabaciones, referencias escuchadas y verificadas, ejecución
con small/MiniLM, inspección de errores, figura ROC, revisión y PR con CI verde.
No confundir pruebas unitarias aprobadas con cumplimiento del criterio empírico.
