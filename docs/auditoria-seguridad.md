# Auditoría de seguridad

**Fecha:** 2026-10-03 · **Alcance:** `services/api`, `apps/web`, `apps/desktop`, `services/ai`,
`supabase/migrations` · **Revisa:** Silva Vega, Héctor

Cada punto dice **cómo se comprobó**, no solo qué se concluyó. Lo que se verificó con una prueba
automatizada queda protegido para siempre; lo que se verificó a mano hay que repetirlo.

---

## Hallazgos corregidos en esta revisión

### 1. Electron con cuatro CVE que rompen el modelo de seguridad de la app — **alto**

La app usaba Electron `39.2.6`. Cuatro avisos de seguridad afectan **exactamente** a las
protecciones sobre las que se apoya el producto:

| Aviso | Qué permite |
|---|---|
| [GHSA-gr2m-v5gq-v685](https://github.com/advisories/GHSA-gr2m-v5gq-v685) | las ventanas abiertas desde un documento en sandbox **no heredan sus restricciones** |
| [GHSA-9qh4-3jw8-366w](https://github.com/advisories/GHSA-9qh4-3jw8-366w) | `<webview>` puede activar Node.js en Web Workers **pese a `nodeIntegration: false`** |
| [GHSA-hq2x-r82h-9wj4](https://github.com/advisories/GHSA-hq2x-r82h-9wj4) | se pierde el sandbox en ventanas abiertas por `OpenURLFromTab` |
| [GHSA-j84w-jfhq-vhvj](https://github.com/advisories/GHSA-j84w-jfhq-vhvj) | lecturas cross-origin sin `corsEnabled` |

Toda la seguridad de la ventana del examen es `sandbox: true` más `nodeIntegration: false`. Estos
avisos son formas de saltarse las dos.

**Corregido:** Electron y electron-builder a `44.5.1`. `npm audit --omit=dev` pasa de 6 avisos
altos a 0. Lint, pruebas y build verificados tras el salto de versión mayor.

### 2. `metadata` de un evento sin límite de tamaño — **medio**

`POST /api/v1/events` aceptaba un `metadata` de cualquier tamaño, y acaba en una columna `jsonb`.
Un cliente podía mandar megabytes en cada uno de los cientos de eventos de un examen.

**Corregido:** 8 KB y 50 claves como máximo, con su prueba. La metadata documentada son unas pocas
claves, así que el tope es holgado para el uso real.

### 3. `CORS_ORIGINS=*` era posible junto a `allow_credentials` — **medio**

La API envía credenciales. Con un comodín, cualquier sitio podría hacer peticiones autenticadas en
nombre del docente. Los navegadores lo rechazan, pero no todos los clientes son navegadores y el
fallo habría sido silencioso.

**Corregido:** la API **se niega a arrancar** con un comodín. Con su prueba.

### 4. Un endpoint nuevo podía quedar abierto sin que nada avisara — **medio**

Si alguien añadía una ruta y olvidaba pedir `current_user`, el caso de uso recibía `actor=None` y
no comprobaba nada. Solo lo detectaba la revisión de código.

**Corregido:** `test_ninguna_ruta_se_queda_sin_current_user` recorre las rutas de la aplicación y
falla si alguna no identifica a quien la llama. La lista de rutas públicas es explícita y también
está comprobada, para que no crezca sin querer.

---

## Lo verificado y correcto

### Inyección SQL — sin superficie

No hay SQL construido por concatenación en ningún punto. Todo el acceso va por PostgREST con los
valores como parámetros (`.eq("id", str(session_id))`), nunca interpolados en la consulta.
Comprobado con búsqueda de `execute(f"`, concatenación, `rpc(` y `text(`: cero coincidencias.

### Control de acceso roto (BAC) e IDOR

| Recurso | Regla | Prueba |
|---|---|---|
| Sesión de examen | el docente solo accede a las suyas | `test_session_access.py` |
| Eventos | el estudiante solo ve los suyos; el filtro que pida se ignora | `test_authorization.py` |
| Alertas | solo el docente, y solo de sus sesiones | `test_session_access.py` |
| Preguntas con respuestas | solo el docente dueño | `test_questions.py` |
| Registrar evento | el `student_id` debe ser el del token | `test_authorization.py` |
| Subir evidencia | solo para uno mismo | `test_evidence_upload.py` |

**Por qué esto vive en la API y no solo en RLS:** la API usa la *service role key* y **omite RLS**.
Ver [ADR-0010](adr/0010-autenticacion-en-la-api-no-en-rls.md).

### Fuga de información en los mensajes de error

Una sesión ajena y una inexistente devuelven **la misma respuesta**. Un código de acceso inválido
no dice por qué ni repite el código probado. Distinguirlos permitiría enumerar qué exámenes existen
o tantear códigos. Comprobado en `test_security.py`.

### La respuesta correcta no llega al estudiante

Es el riesgo central de SPEC-003. Se defiende con el **tipo**, no con disciplina: `ExamQuestion` y
`ExamOption` **no declaran** `is_correct`, `correct_numeric_answer` ni `correct_text_answer`, y el
único camino para construirlos es `Question.for_student()`.

Además hay dos endpoints separados en vez de uno con un parámetro, así que no existe ninguna ruta
por la que un estudiante pueda pedir las respuestas. Y el examen solo se entrega **mientras está
abierto**: sin eso, se podría descargar la noche anterior.

Las pruebas inspeccionan el **JSON crudo** de la respuesta, no el objeto: lo que importa es lo que
viaja por el cable.

### XSS

- **Web:** React escapa por defecto. Cero usos de `dangerouslySetInnerHTML`, `innerHTML`, `eval` o
  `document.write`.
- **Escritorio:** el panel usa `textContent` y `createElement`, nunca `innerHTML`. CSP restrictiva
  (`default-src 'self'`).

### Autenticación

Tokens ES256 verificados contra el JWKS público del proyecto. **Lista cerrada de algoritmos**
(`ES256`, `RS256`), que cierra los ataques de confusión de algoritmo. Se exigen `exp` y `sub`, y se
validan `aud` e `iss`. Un usuario sin fila en `profiles` **no recibe rol por defecto**: falla
cerrado.

### Asignación masiva

Los 7 modelos de petición declaran `extra="forbid"`. Una clave de más responde `422` en vez de
ignorarse en silencio.

### Secretos

Cero coincidencias de claves secretas en el árbol **y en todo el historial de git**. `.env` está
ignorado. GitHub tiene activados el escaneo de secretos y la protección de push.

### Base de datos

RLS activo en las 15 tablas. Los eventos solo admiten `insert` y `select`: son evidencia, no se
editan ni se borran. `decisions.justification` es obligatoria con al menos 10 caracteres.
`handle_new_user` crea a todos como `student` y un trigger impide que nadie se promueva a `teacher`.

---

## Corregidos en la segunda pasada (SPEC-004)

### 5. No había limitación de peticiones — **medio** · corregido

Nada impedía miles de peticiones por segundo. En `POST /sessions/join` permitía tantear códigos de
acceso por fuerza bruta sin dejar rastro.

**Corregido:** ventana deslizante en memoria, con dos límites. 120 escrituras por minuto en general
—holgado para el ritmo de eventos de un examen— y **10 por minuto en `/sessions/join`**, que es
generoso para un humano que teclea su código y demasiado lento para una fuerza bruta.

El cliente se identifica **por token antes que por IP**: detrás de la red de una universidad todos
los estudiantes comparten IP de salida, y limitar por IP los castigaría a todos por culpa de uno.

Las lecturas no cuentan (la pantalla en vivo del docente lee a menudo) y `/health` nunca se limita,
porque bloquearlo haría que el contenedor se reiniciara solo.

**Limitación honesta:** el contador es *por instancia*. Con una sola réplica es suficiente; si algún
día hay más, esto tiene que pasar a Redis, que ya está desplegado.

Verificado en el contenedor: las 10 primeras peticiones a `/join` responden `400` (código
inexistente), la 11 y la 12 responden `429` con `Retry-After`.

### 6. Un estudiante podía pedir el examen de una sesión ajena — **medio** · corregido

`GET /api/v1/exam/{id}/questions` comprobaba que el examen estuviera abierto, pero no que quien
pedía estuviera **matriculado**.

**Corregido:** `ensure_can_take_exam` exige matrícula, consentimiento, identidad resuelta y no haber
entregado. La comprobación funciona **igual en local que en producción**: en modo sin autenticación
usa el estudiante de desarrollo en vez de saltarse el control, porque un control que solo existe con
autenticación activa no se prueba hasta el despliegue.

Verificado en el contenedor, de punta a punta:

| Paso | Respuesta |
|---|---|
| pedir el examen sin matrícula | `403` |
| matricularse sin aceptar la supervisión | `400` |
| aceptar la supervisión | `201` |
| pedir el examen sin la identidad verificada | `403` |
| el docente lo admite a mano | `200` |
| pedir el examen | `200` |
| entregar | `200` |
| reenviar | `400` |
| pedir el examen tras entregar | `403` |

---

## Pendiente, por orden de riesgo

### 1. ~~No hay limitación de peticiones~~ — corregido, ver arriba

Nada impide que un cliente haga miles de peticiones por segundo. En el plan gratuito de Render eso
tumba el servicio, y en `POST /sessions/join` permite tantear códigos de acceso por fuerza bruta.
Con 31 caracteres y 6 posiciones hay ~900 millones de combinaciones, así que no es inmediato, pero
tampoco hay nada que lo frene ni que lo registre.

**Qué haría:** un límite por IP y por usuario en los endpoints de escritura y en `join`.

### 2. ~~El estudiante puede pedir el examen de una sesión ajena~~ — corregido, ver arriba

### 3. Sin registro de auditoría de accesos — **bajo**

Se registra lo que hace el estudiante, pero no quién leyó la evidencia ni cuándo. En un sistema que
sostiene decisiones académicas, saber qué docente abrió qué caso tiene valor.

### 4. La app de escritorio no verifica la identidad del servidor — **bajo**

En producción la API irá por HTTPS y basta la validación estándar. Mientras sea `http://localhost`
no aplica, pero conviene no olvidarlo al desplegar.

---

## Cómo repetir esta auditoría

```bash
cd services/api && uv run pytest tests/integration/http/test_security.py
```

```bash
cd services/api && uv run pytest tests/integration/http/test_rate_limit.py
```

```bash
cd apps/desktop && npm audit --omit=dev
```

```bash
cd apps/web && npm audit --omit=dev
```

Lo demás son búsquedas en el código, documentadas arriba junto a cada punto.
