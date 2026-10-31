# Informe de avance — Sistema Proctoring

**Corte:** 5 de octubre de 2026 · **Rama:** `develop` · **Repositorio:** <https://github.com/RolloGordo/proctoring> (público)

Todo lo de este documento se contrastó contra GitHub y contra el disco local. Los números salen de
`git log`, `gh pr list`, `pytest`, `npm test` y la API en ejecución, no de memoria.

---

## 0. Cifras globales

| Métrica | Valor |
|---|---|
| Commits en `develop` | **54** (38 de trabajo + 16 de integración) |
| Pull requests | **16** abiertos · **15 integrados** · 1 cerrado y reemplazado (#4 → #7) |
| CI | **7 jobs** en verde en cada PR y en cada push a `develop` |
| Pruebas automáticas | **452**: API 417 · IA 24 · escritorio 7 · web 4 |
| Contratos de arquitectura | **2 de 2** cumplidos (import-linter) |
| Endpoints de la API | **18 de negocio + `/health`** |
| Pantallas web | **9** (incluido el login) |
| Migraciones SQL | 4 · **15 tablas**, todas con RLS |
| Decisiones de arquitectura (ADR) | 10 |
| Código | API 6.486 líneas + 4.954 de pruebas · web 3.537 · escritorio 1.249 · IA 477 |
| Vulnerabilidades corregidas | 6, más 4 puntos verificados con prueba automática |
| Período | 3 y 4 de octubre de 2026 |

### Nota sobre la atribución (léela antes de pegar en Notion)

El historial de Git **no refleja bien quién hizo qué**, y conviene saberlo antes de que lo vea el
profesor:

- **Héctor figura con 35 de 38 commits de trabajo**, pero varios son trabajo de sus compañeros
  aplicado desde su copia local (Zevallos: `8f18a7d`, `3bedb3e`; Rider: correcciones y la subida de
  Electron). Los commits de Héctor lo dicen en el cuerpo del mensaje.
- **Rider** conserva su autoría en **1 commit** (`aac58cb`, 8.806 líneas, 32 archivos).
- **Zevallos** conserva su autoría en **2 commits** (`36016f2` y `c78139e`, 1.697 líneas, 20 archivos).
- Los PR #6, #7, #11 y #12 aparecen a nombre de `RolloGordo` aunque el contenido sea de Rider o de
  Zevallos, porque los abrió Héctor. Los **commits** sí conservan a su autor.
- En GitHub los contribuyentes son: `RolloGordo` 51 · `pierre0782` 2 · `RiderRuiz` 1.

Abajo cada sección separa **lo que hizo la persona** de **lo que Héctor integró o corrigió sobre su
trabajo**.

---

## 1. Héctor Silva Vega — Project Manager

**Área:** arquitectura, API hexagonal, infraestructura, CI/CD, seguridad.
**Commits propios:** 35 · **+28.762 / −886 líneas** · **266 archivos distintos**.

### 1.1 Base del proyecto (EN-003, EN-004, EN-006)

- Estructura del monorepo: `apps/`, `services/`, `packages/`, `supabase/`, `specs/`, `docs/`.
- **Contrato de evento compartido** (`packages/contracts/event.schema.json`) con un ejemplo válido
  por cada tipo de evento, validado en el CI. Es la fuente de verdad entre la app, la API y la IA.
- **Esquema de base de datos en Supabase**, creado por Héctor porque Jesús estaba de viaje:
  4 migraciones, 15 tablas, enums, RLS en todas, Realtime en `alerts` y `session_participants`,
  3 buckets privados de Storage (`evidences`, `audio-segments`, `reference-faces`).
- Endurecimiento del alta de usuarios: `handle_new_user` crea a todos como `student` y un disparador
  impide que alguien se promueva a `teacher` por su cuenta.
- Tipos de TypeScript generados desde el esquema real de Supabase.
- 10 ADR en `docs/adr/` (hexagonal en dos servicios, Electron para el estudiante, Supabase,
  detección liviana sin video continuo, Python en todo el backend, cola Redis/RQ, alertas por
  Realtime, exámenes propios sin LMS, monorepo con despliegue gratuito, autenticación en la API).

### 1.2 API principal (EN-005) — Python 3.12 + FastAPI, hexagonal

Capas separadas y verificadas en cada CI por **import-linter** (`adapters → application → domain`,
y dominio sin frameworks).

| Capa | Qué contiene |
|---|---|
| Dominio | `ProctoringEvent`, `ExamSession`, `Question`/`ExamQuestion`, `SessionParticipant`, `Answer`, `Alert`, severidad, errores |
| Puertos | repositorios de eventos, alertas, sesiones, preguntas, participantes, respuestas y perfiles; cola; almacenamiento; reloj; verificador de tokens |
| Casos de uso | registrar evento, listar eventos y alertas, crear/listar/ver sesión, unirse por código, preguntas, matrícula, respuestas, evidencia |
| Adaptadores | memoria · Supabase · Redis · HTTP (FastAPI) |

**Endpoints (19):**

```
POST /api/v1/events                                   registrar un evento
POST /api/v1/evidence/upload-url                      URL firmada para subir captura o audio
GET  /api/v1/sessions                                 mis exámenes (docente)
POST /api/v1/sessions                                 crear examen
GET  /api/v1/sessions/{id}                            ver un examen
POST /api/v1/sessions/join                            resolver el código de acceso (estudiante)
GET  /api/v1/sessions/{id}/events                     señales registradas
GET  /api/v1/sessions/{id}/alerts                     alertas
GET  /api/v1/sessions/{id}/questions                  preguntas CON respuestas (solo docente dueño)
POST /api/v1/sessions/{id}/questions                  añadir preguntas
GET  /api/v1/sessions/{id}/participants               sala de espera (docente)
POST /api/v1/sessions/{id}/participants/{sid}/identity  admitir/rechazar a mano
GET  /api/v1/exam/{id}/questions                      preguntas SIN respuestas (estudiante)
POST /api/v1/exam/{id}/enroll                         aceptar la supervisión y matricularse
GET  /api/v1/exam/{id}/me                             mi estado en el examen
PUT  /api/v1/exam/{id}/answers                        guardar respuestas
GET  /api/v1/exam/{id}/answers                        recuperar mis respuestas
POST /api/v1/exam/{id}/submit                         entregar
GET  /health
```

**Reglas de negocio que quedaron en el dominio:**

- `question_id` obligatorio para `speech_detected` y `gaze_away`; `duration_ms ≥ 0`; hora con zona.
- Severidad por tipo de evento. `speech_detected` siempre es **baja** a propósito: solo el servicio
  de IA, que compara con el enunciado, puede escalarla (leer en voz alta no debe alertar).
- Presets de supervisión **básica ⊂ estándar ⊂ estricta** y umbrales por módulo en un solo sitio.
- Código de acceso de 6 caracteres con `secrets`, sin letras ambiguas (sin O/0/I/1/L).
- **La respuesta correcta nunca llega al estudiante**, defendido con el *tipo*: `ExamQuestion` no
  declara `is_correct` ni `correct_*`; la única vía es `Question.for_student()`.
- Matrícula: **sin consentimiento no hay matrícula**; la verificación fallida no expulsa; admitir a
  mano registra quién lo hizo; no se puede entregar dos veces.

### 1.3 Seguridad (SPEC-001) — `docs/auditoria-seguridad.md`

- **Autenticación** con JWT de Supabase (ES256 por JWKS), lista cerrada de algoritmos, `exp`/`sub`/
  `aud`/`iss` exigidos; un usuario sin perfil **no recibe rol por defecto**.
- **ADR-0010:** la API usa la *service role key* y **omite RLS**, así que toda autorización por
  estudiante vive en la capa de aplicación.
- La API **se niega a arrancar** sin autenticación fuera de `local`/`test`, y con `CORS_ORIGINS=*`.
- Un docente solo accede a sus sesiones; un estudiante solo a sus eventos; un id ajeno y uno
  inexistente devuelven la **misma respuesta** (no se puede enumerar).
- Los 7 modelos de petición con `extra="forbid"` (contra asignación masiva).

| # | Hallazgo | Severidad | Estado |
|---|---|---|---|
| 1 | Electron 39 con 4 CVE que anulan `sandbox`/`nodeIntegration`; 6 avisos altos de `npm audit` → 0 | Alto | Corregido (Electron 44.5.1) |
| 2 | `metadata` de un evento sin tope de tamaño | Medio | Corregido (8 KB, 50 claves) |
| 3 | `CORS_ORIGINS=*` posible junto con credenciales | Medio | Corregido (no arranca) |
| 4 | Una ruta nueva podía quedar abierta sin que nada avisara | Medio | Corregido (prueba que recorre todas las rutas) |
| 5 | Sin limitación de peticiones; fuerza bruta en `/sessions/join` | Medio | Corregido (120/min general, **10/min en join**, por token antes que por IP) |
| 6 | Un estudiante podía pedir el examen de una sesión ajena | Medio | Corregido (`ensure_can_take_exam`) |

Verificado y correcto: sin SQL por concatenación, sin XSS (cero `innerHTML`/`dangerouslySetInnerHTML`),
cero secretos en el árbol **y en todo el historial**, RLS en las 15 tablas, eventos de solo
`insert`/`select` (son evidencia).
Pendiente documentado: registro de auditoría de accesos (bajo) y que el escritorio no verifica la
identidad del servidor mientras sea `http://localhost` (bajo).

**Secreto filtrado:** Héctor pegó una clave secreta de Supabase en el chat. Se avisó como comprometida,
no se escribió en ningún archivo y se rotó. Se comprobó que no había rastro en el árbol ni en el
historial **antes** de hacer público el repositorio.

### 1.4 CI/CD (EN-004)

**7 jobs** en GitHub Actions: detección de qué hay en el repo · API (ruff, formato, mypy, pytest,
import-linter) · contrato de evento · **imagen Docker de la API** (construye, arranca, comprueba
`/health`, hace un POST real y comprueba que no arranca sin auth fuera de local) · servicio de IA ·
web del docente · app de escritorio. Los tres últimos se saltan hasta que existe su manifiesto.

Además: protección de `main` (solo por PR), GitHub **secret scanning y push protection** activados,
`develop` como rama por defecto.

### 1.5 Infraestructura y cola (EN-006, TA-007)

- `docker compose up` levanta **API + Redis + worker de IA**, con healthcheck.
- **Cola real Redis + RQ** (`audio` y `high`), encolada *por nombre de función* para que la API no
  instale código de IA. Worker de prueba.
- **Subida de evidencia por URL firmada** de Supabase Storage: la app sube directo y a la API solo
  le llega el evento.
- Verificado contra el Supabase real: sesión, 11 módulos, eventos y alertas creados de verdad.

### 1.6 Alertas en vivo (SPEC-009, parcial)

La API crea una fila en `alerts` por cada evento relevante y la web del docente la recibe por
**Supabase Realtime** (sostiene la meta de avisar en menos de 5 s).

### 1.7 Web del docente y del estudiante (EN-002) — React 19 + TypeScript + Vite

- **Sistema de diseño** derivado del tema *Start Bootstrap Agency* (amarillo `#ffc800`, tinta
  `#212529`, Montserrat para títulos, Roboto Slab para texto), sin aspecto genérico.
- Autenticación con Supabase y **enrutado por rol**; sin Supabase configurado funciona en modo
  desarrollo.
- **9 pantallas, login incluido:**

| Ruta | Pantalla | Rol |
|---|---|---|
| `/login` | Iniciar sesión | ambos |
| `/sesiones` | Mis exámenes (con accesos directos) | docente |
| `/sesiones/nueva` | Crear examen | docente |
| `/sesiones/:id` | Examen en vivo: alertas, señales, código | docente |
| `/sesiones/:id/preguntas` | Crear y listar preguntas | docente |
| `/sesiones/:id/participantes` | Sala de espera: admitir/rechazar identidad | docente |
| `/examen` | Código de acceso | estudiante |
| `/examen/:id/sala` | Consentimiento informado y espera | estudiante |
| `/examen/:id/rendir` | Rendir y entregar | estudiante |

- El examen **guarda al responder** (lotes cada 0,5 s) y muestra el estado del guardado; al recargar
  recupera lo respondido. La sala del estudiante consulta sola cada 10 s hasta que lo admiten.
- Corregido de paso: `.campo > label` no casaba con nada (etiquetas de formulario sin estilo), ESLint
  revisaba la caché de Vite, y el editor permitía varias opciones correctas cuando una respuesta
  guardada apunta a una sola.

### 1.8 SPEC-002, 003 y 004 (API)

- **SPEC-002 Sesiones:** crear, listar, ver, unirse por código (normalizado: el estudiante lo teclea
  leyendo una pizarra), ventana de ingreso con tolerancia.
- **SPEC-003 Preguntas:** 5 tipos (opción múltiple, V/F, numérica, completar, desarrollo), tope de 200
  por examen, lote atómico (si una falla no se guarda ninguna).
- **SPEC-004 Matrícula, consentimiento y entrega.** De este SPEC todavía falta la verificación facial,
  que es de Jesús.

### 1.9 Revisión del trabajo de Rider y de Zevallos

- **Rider:** revisó el código en dos pasadas y encontró que el panel marcaba *todas* las filas como
  alerta máxima (anulaba la gradación de severidad) → corregido para reproducir `default_severity` de
  la API. Subió **Electron 39 → 44.5.1** por los 4 CVE (apartado 1.3). Aplicó el sistema de diseño al
  escritorio.
- **Zevallos:** detectó que su `.gitignore` excluía `results/` y `datasets/`, así que **sus números
  medidos no existían en el repositorio** → corregido para versionar resultados y metadatos (el audio
  y los modelos siguen fuera). Restituyó `rq`/`redis` en su `pyproject.toml` (el worker los necesita;
  se había perdido dos veces). Integró su rama de audios propios (PR #16).
- **Pull Requests y merge:** unificó 13 commits que llevaban sin integrarse (PR #1) y que hacían que
  ambos compañeros trabajaran sobre una base desactualizada. Usó *merge commit* y no *squash* para
  **conservar la autoría individual**, que es lo que evalúa el docente.

### 1.10 App de escritorio — integración (a nombre de Héctor)

- La ventana **carga el examen de la web** en `/examen/:id/sala` dentro del kiosco, en vez de una
  página local (antes el estudiante no veía un examen en la app que lo supervisa).
- **Navegación atada al origen del examen** (el preload expone `window.api`: cualquier sitio al que
  navegara la heredaría).
- Puertos fijados (web `5173` con `strictPort`, panel de diagnóstico `5180`) y README del escritorio al
  día.

### 1.11 Documentación escrita

`docs/auditoria-seguridad.md` · `docs/estado-de-pantallas.md` (cada pantalla contra su SPEC y su
responsable) · `docs/como-ver-los-avances.md` (cómo abrir API, web y escritorio y grabar evidencia) ·
`docs/evidencias/semana-06/hector/` (3 capturas + README) · 10 ADR · README raíz.

### 1.12 Errores propios que se corrigieron en el camino

Se documentan porque el profesor valora la trazabilidad: `uv` instalado fuera del `PATH` (documentado el
alta en Windows y el aviso de que PowerShell 5.1 no soporta `&&`) · `hashFiles` no permitido en un `if`
de job · mi README rompió el formato del job de IA de Zevallos · un `vite.config.ts` editado sin volver
a pasar el lint · un mensaje de commit con un carácter corrupto, reescrito antes del PR · el SQL de
promoción a docente se ejecutó con el correo de ejemplo (0 filas) y se detectó y corrigió · una
prueba de seguridad fallaba por enviar `json={}` en un GET · el modo desarrollo se saltaba por
completo la comprobación de matrícula, ahora se comporta igual que producción · un servidor mío
ocupaba el puerto 5173 y confundió el arranque del escritorio.

---

## 2. Rider Rodriguez Ruiz — Scrum Master

**Área:** app de escritorio Electron (kiosco, foco, monitores, procesos, protección).
**Commit propio:** `aac58cb` — `feat(EN-002): detect focus loss, extra displays and suspicious processes`
**+8.806 líneas · 32 archivos** · carpeta `apps/desktop/`.
**Integrado por:** PR #6. Su commit es del 3 de octubre, 14:02.

### 2.1 Lo que hizo él

Andamiaje con `electron-vite` (plantilla `vanilla-ts`), TypeScript estricto, ESLint y Prettier.

| Capacidad | Archivo | Detalle |
|---|---|---|
| **Ventana en kiosco** | `main/index.ts` | `kiosk` fuera de desarrollo; `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false` |
| **Protección de contenido** | `main/protection.ts` | `setContentProtection(true)`: la ventana sale en negro en capturas y pantalla compartida (Zoom, Meet, OBS) |
| **Bloqueo de copiar/pegar** | `main/protection.ts` | Ctrl+C/V/X, Ctrl+Insert, Shift+Insert y menú contextual |
| **`focus_lost`** | `main/index.ts` + `events.ts` | **Un solo evento al volver**, con `duration_ms`; si se cierra la app estando fuera, se emite con `returned: false` |
| **`extra_display`** | `main/index.ts` + `events.ts` | Al arrancar y en `display-added`, con la lista de pantallas y sus dimensiones |
| **`suspicious_process`** | `main/processes.ts` | Sondeo cada **10 s**; lista de 11 procesos en 5 categorías: `screen_share` (Zoom), `remote_desktop` (AnyDesk, TeamViewer), `screen_recorder` (OBS, OBS32, OBS64), `communication` (Discord), `virtual_machine` (VMware, VirtualBox). Un solo evento por nombre aunque haya varias instancias. **No mata el proceso:** es auditor, no juez. |
| **Envío a la API** | `main/sender.ts` | Cola con reintento cada 5 s (tope 500 eventos), cabecera `Authorization`, **renovación del token de Supabase** y control de errores 401/5xx |
| **Contexto de examen** | `main/context.ts` | Sesión y estudiante por variables de entorno mientras no exista el enlace |
| **Preload mínimo** | `preload/index.ts` | Solo la API necesaria vía `contextBridge`; el renderer nunca recibe `ipcRenderer` |
| **Panel local de eventos** | `renderer/` | Tabla de señales en vivo, contador de salidas y de monitores. Usa `textContent`, CSP restrictiva |
| **Pruebas** | `events.test.ts`, `sender.test.ts` | Construcción de eventos y envío |
| **Empaquetado** | `electron-builder.yml` | Configuración del instalador |

### 2.2 Lo que Héctor corrigió o añadió sobre su trabajo

- **Panel:** ponía la clase `alerta` en todas las filas (todo parecía alerta máxima); ahora usa la misma
  gradación que la API. Avisa en pantalla si no hay sesión configurada.
- **Seguridad:** Electron 39.2.6 → **44.5.1** (4 CVE contra `sandbox` y `nodeIntegration`).
- **Diseño:** mismos tokens y estructura visual que la web, **sin cargar fuentes de Google** a propósito
  (la ventana de examen no debe llamar a un CDN).
- **Carga del examen y navegación atada al origen** (apartado 1.10), puertos y README.

### 2.3 Verificado en esta sesión

La app se arrancó contra un examen real. En la máquina de Héctor **detectó AnyDesk y Discord**
corriendo y un `focus_lost`; la API los recibió y los clasificó como severidad alta
(`suspicious_process`) y baja (`focus_lost`). Es decir: el circuito completo
**Electron → API → alerta** funciona.

### 2.4 Pendiente de Rider

| Pendiente | SPEC |
|---|---|
| **Evidencia en vídeo** (Alt+Tab, monitor, Zoom, captura en negro). El README pide guardarla en `docs/evidencias/semana-05/rider/` y **la carpeta está vacía**; los 7 criterios de aceptación del README siguen sin marcar | SPEC-006 |
| Aviso de supervisión en curso en la ventana | SPEC-006 |
| Login del estudiante dentro de la app | SPEC-001 |
| Medir que `extra_display` llega en < 5 s y el proceso sospechoso en < 15 s | SPEC-006 |
| Probar el instalador (`electron-builder`) y publicarlo en GitHub Releases | EN-004 |

---

## 3. Pierreluiggi Zevallos Bocanegra — Desarrollo (servicio de IA)

**Área:** transcripción de voz en español (SP-007), base del servicio de IA de audio.
**Commits propios:** `36016f2` (3 oct, 13:22) y `c78139e` (3 oct, 22:02) · **+1.697 / −13 líneas · 20 archivos**.
**Integrado por:** PR #7 (spike) y PR #16 (audios propios). El PR #4 original quedó cerrado y lo
reemplazó el #7.

### 3.1 Lo que hizo él

Carpeta `services/ai/spikes/`:

| Archivo | Qué hace |
|---|---|
| `transcribe.py` | Transcripción en español con **faster-whisper**, CPU/int8, con VAD, 4 hilos y medición del tiempo real de inferencia |
| `metrics.py` | Cálculo de **WER** por sustitución, inserción y omisión; **conserva tildes y la ñ** |
| `evaluate.py` | Evaluación de varios audios con validación de rutas, identificadores, referencias y **hashes SHA-256** |
| `download_sample.py` | Descarga y restauración segura de audios del dataset público **MediaSpeech** |
| `network.py` | Descargas con los certificados TLS del sistema |
| `demo.py` + `demo.ps1` | Demo portable (Windows, Linux, macOS) |
| `pyproject.toml` + `uv.lock` | Dependencias reproducibles para Python 3.12 |
| `tests/` | **24 pruebas** |

### 3.2 Resultados medidos

| Muestra | Audio | Palabras | Modelo | Errores | **WER** | Inferencia | Factor de tiempo real |
|---|---|---|---|---|---|---|---|
| MediaSpeech (pública, 8 audios) | 116,0 s | 318 | `base` | 69 | 21,70 % | 9,0 s | 0,078 |
| MediaSpeech (pública, 8 audios) | 116,0 s | 318 | **`small`** | 51 | **16,04 %** | 27,2 s | 0,234 |
| Audios propios P01 (2 audios) | 34,3 s | 79 | `base` | 14 | 17,72 % | 2,9 s | 0,083 |
| Audios propios P01 (2 audios) | 34,3 s | 79 | **`small`** | 6 | **7,59 %** | 6,1 s | 0,178 |

**Conclusión de la bitácora:** `small` comete menos errores en las dos muestras. Con `small`, un
fragmento de 10 s cuesta ~2,3 s de transcripción, así que **quedan ~7,7 s** del presupuesto de 10 s
de la alerta de IA por voz para la similitud semántica y la detección de voz sintética.

Las referencias de los audios propios se revisaron escuchándolos; la pausa y el ruido de ventilador
quedaron registrados en la procedencia.

### 3.3 Documentación que escribió

`docs/SP-007-guide.md` · `docs/development-report.md` · `docs/dataset-plan.md` ·
`docs/SP-007-own-results.md` · `datasets/sp007_own/README.md` · manifiestos y `provenance.json`
con hashes · `results/*.json` (evaluación, demo, silencio, audios propios).

### 3.4 Hallazgos suyos que valen la pena citar

- Los **nombres de los spikes en inglés** (`transcribe.py` y no `transcribir.py`) cumplían
  `CLAUDE.md §5`; el README de Héctor estaba equivocado y se corrigió.
- Detectó que el `.gitattributes` raíz normaliza finales de línea y **cambiaría los bytes que sus
  pruebas verifican por hash** → añadió `datasets/**/manifest.csv -text`. Un detalle sutil.
- Su prueba más valiosa **recalcula el WER desde la transcripción guardada** y lo compara con el
  publicado: los números ya no pueden desviarse de su evidencia. Otra regenera el control de silencio
  desde los parámetros documentados y comprueba su SHA-256.

### 3.5 Lo que Héctor corrigió sobre su trabajo

- Su `pyproject.toml` perdió `rq` y `redis` **dos veces** (el worker de la cola los necesita y sin
  ellos `mypy` fallaba en el CI); se restituyeron.
- Sus resultados y metadatos no estaban en el repositorio (apartado 1.9).
- Se comprobó que su última entrega (PR #16) **no pisa nada**: `pyproject`, `uv.lock`, `worker_stub.py`,
  `tasks.py` y `.gitignore` idénticos a `develop`; `ruff`, `mypy` y 24 pruebas en verde.

### 3.6 Pendiente de Zevallos (SPEC-008)

| Pendiente | Detalle |
|---|---|
| **Servicio de IA como servicio** (TA-007) | Hoy es un spike y un worker de prueba; falta la API del servicio y el worker real que procese la cola |
| **Similitud semántica** | `sentence-transformers` multilingüe contra el enunciado de la pregunta en curso |
| **Detección de voz sintética** | La segunda voz que responde |
| **Regla de alerta** | Solo si se cumplen **ambas** condiciones (leer en voz alta no debe alertar) |
| **Importación QTI** | SPEC-003; asignada a su área |
| **Medir accuracy ≥ 80 % y FPR < 20 %** | Meta del objetivo SMART; hoy solo se midió WER |
| Detección de habla en el cliente (Silero VAD) | Va en el renderer de la web, coordinar con Rider |

---

## 4. Jesús Limay Capristan — Visión computacional y base de datos

**Sin commits todavía.** Empieza esta semana 6, como se acordó.

Lo que ya existe en su área, preparado por Héctor porque estaba de viaje:

- `apps/web/spikes/vision/README.md` — carpeta preparada para el spike de visión.
- `supabase/` con 4 migraciones y su README — **el esquema inicial lo creó Héctor**; el mantenimiento
  pasa a Jesús.

### Propuesta de asignación inicial

| Prioridad | Tarea | SPEC | Por qué |
|---|---|---|---|
| 1 | **Verificación de identidad por rostro** (InsightFace/ArcFace, P90 < 500 ms) | SPEC-005 | Es el que **desbloquea** el estado `verified`: hoy el docente tiene que admitir a todos a mano |
| 2 | Spike de **mirada** con MediaPipe (`gaze_away`) | SPEC-007 | Detección liviana en el renderer |
| 3 | **Rostro ausente** y **persona adicional** | SPEC-007 | Mismas bases que la mirada |
| 4 | Migraciones nuevas si el esquema cambia | — | Nunca editar en el panel: siempre una migración |
| 5 | Medir accuracy ≥ 80 % y FPR < 20 % por módulo | SPEC-005/007 | Meta medible del proyecto |

---

## 5. Estado por SPEC

| SPEC | Qué es | Estado | Responsable |
|---|---|---|---|
| 001 | Autenticación y roles | ✅ API y web hechas | Héctor |
| 002 | Gestión de sesiones | ✅ | Héctor |
| 003 | Preguntas | 🟡 CRUD hecho · **falta calificación e importación QTI** | Héctor / Zevallos |
| 004 | Rendición y escritorio | ✅ matrícula, consentimiento, respuestas, entrega | Héctor / Rider |
| 005 | Identidad por rostro | ❌ no iniciado | Jesús |
| 006 | Foco, monitores y procesos | ✅ detección · 🟡 falta evidencia en vídeo | Rider |
| 007 | Visión (mirada, rostro, persona) | ❌ no iniciado | Jesús |
| 008 | Consulta a IA por voz | 🟡 transcripción medida · falta similitud y voz sintética | Zevallos |
| 009 | Riesgo, alertas y decisión | 🟡 alertas en vivo hechas · **falta riesgo, revisión y decisión** | Héctor |

**Lo más importante que falta:** la tabla `decisions` existe pero nadie escribe en ella. La promesa
central del proyecto —*auditor, no juez*— necesita la pantalla donde el docente resuelve un caso con
justificación obligatoria (≥ 10 caracteres). Es lo siguiente a construir, junto con la pantalla de
revisión de caso y el cálculo de riesgo por señal.

## 6. Evidencias que ya están en el repositorio

| Quién | Dónde | Qué hay |
|---|---|---|
| Héctor | `docs/evidencias/semana-06/hector/` | 3 capturas (preguntas, examen del estudiante, sala de espera) y README |
| Héctor | `docs/auditoria-seguridad.md` | Auditoría completa con cómo se verificó cada punto |
| Rider | `apps/desktop/` | Código y pruebas; **sin vídeo todavía** |
| Zevallos | `services/ai/results/` y `docs/` | Resultados medidos, manifiestos con hashes, informes |
| Jesús | — | — |

> **Ojo:** el profesor evalúa por commits y evidencias *individuales*. A Rider y a Jesús les falta
> evidencia en `docs/evidencias/`, y la de Zevallos está dentro de `services/ai/` y no en esa carpeta.
