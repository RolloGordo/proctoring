# Evidencias

Capturas y videos que demuestran el avance, organizados **por semana y por integrante**. El docente
evalúa el trabajo **individual**, así que cada uno sube lo suyo a su propia carpeta.

```
docs/evidencias/
└── semana-05/
    ├── hector/
    ├── rider/
    ├── pierreluiggi/
    └── jesus/
```

## Qué cuenta como evidencia

La reunión del 03/10/2026 dejó clarísimo el criterio del docente: **investigar no es entregar**. Sus
palabras fueron "no lo van a llenar de pura investigación, algo que sea tangible", y "yo necesito
tener resultados de esa investigación".

Así que:

| Sirve | No sirve |
|---|---|
| Captura de la terminal con la prueba pasando | Captura del documento donde explicas la prueba |
| Video del detector marcando un rostro en vivo | Diagrama de cómo funcionaría el detector |
| Swagger respondiendo 201 a un POST real | El esquema del endpoint en Notion |
| Enlace a la ejecución del CI en verde | Captura del archivo `ci.yml` |
| Tabla con los umbrales probados y sus números | "Se investigó que el umbral adecuado es 0.6" |

Un documento o un diagrama vale **como acompañamiento** de algo que corre, nunca en su lugar.

## Cómo nombrar los archivos

```
<codigo-tarea>-<descripcion-corta>.<ext>
```

Por ejemplo: `EN-005-swagger-post-201.png`, `TA-003-focus-lost-altab.mp4`.

## Límites

- Nada de audio ni video pesado versionado: `.gitignore` bloquea `*.wav`, `*.mp4` y compañía. Si la
  evidencia es un video, súbelo a Drive o a un release y deja aquí un `.md` con el enlace y lo que
  se ve en él.
- Capturas en PNG o JPG, recortadas a lo que importa.
- Nada de credenciales visibles en las capturas: revisa antes de subir.

## Checklist de la semana

Cada integrante, en su carpeta: la evidencia de cada tarea que cerró, más un `resumen.md` con la
tarea, las horas aproximadas y el enlace al pull request. Es lo que se pega en Notion.
