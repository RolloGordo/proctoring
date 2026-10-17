# Fuentes y motivo de consulta · actualización del 8–9/10/2026

- Guía entregada por el líder: `pierreluiggi-ia-audio.md`. Es la nueva asignación
  P1–P5. Sus instrucciones de publicación no se ejecutaron porque el usuario
  pidió mantener el trabajo local.
- Código local de `tasks.py`, schemas internos, `audio_analysis.py`, evidence,
  y README de supervisión sobre la base cb09aea: para usar el contrato existente
  y mantener las decisiones de alerta exclusivamente en la API.
- https://github.com/ricky0123/vad/blob/master/docs/user-guide/api.md
  y https://github.com/ricky0123/vad/blob/master/docs/user-guide/browser.md:
  para callbacks de habla, reutilización de MediaStream y assets locales. Se
  verificaron además las declaraciones y el código de la versión instalada 0.0.30;
  no se asumió que la documentación de `master` fuese idéntica.
- https://supabase.com/docs/reference/javascript/file-buckets-uploadtosignedurl
  y https://supabase.com/docs/guides/storage/serving/downloads:
  para subida con URL firmada y descarga privada. Se contrastó la subida con el
  SDK instalado y el contrato de evidence de la API.
- https://www.imsglobal.org/question/qtiv2p1/imsqti_implv2p1.html:
  referencia QTI ya consultada en el avance anterior; el manifiesto referencia
  recursos y no reemplaza el contenido de las preguntas.
- https://github.com/clovaai/aasist y
  https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2:
  fuentes del trabajo previo, reutilizadas para modelos y limitaciones. AASIST
  no aporta diarización ni identifica por sí mismo una segunda voz.
- https://github.com/advisories/GHSA-82fw-gwwq-j7x9 y
  https://github.com/advisories/GHSA-85c8-ppgw-ccpr:
  referencias devueltas por npm audit. Se pasó a Vitest 4.1.11; la instalación
  posterior informó cero vulnerabilidades. No se ejecutó `audit fix --force`.

No se descargaron voces nuevas ni se aceptaron condiciones de Common Voice o
permisos de clonación. No hay nuevas métricas de P1/P2 sin dataset. Los resultados
de SP-007 se conservan como evidencia previa, con su alcance original.
