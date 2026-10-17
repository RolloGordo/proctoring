# ADR-0010 — La autorización del estudiante vive en la API, no en RLS

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-10-03 |
| **Decide** | Silva Vega, Héctor (Project Manager) |

## Contexto

La base de datos tiene RLS activo en las 15 tablas, con políticas que impiden que un estudiante lea
o escriba filas de otro ([ADR-0003](0003-supabase-datos-auth-storage-realtime.md)). Eso parecería
suficiente.

No lo es. La API principal usa la **service role key**, y esa clave **omite RLS por completo**. Es
una decisión deliberada y necesaria: la API tiene que servir las preguntas al estudiante sin las
respuestas correctas (que están en `question_options.is_correct`, en la misma tabla), y tiene que
escribir en `audio_analyses`, `alerts` y `risk_scores`, tablas donde ningún usuario tiene permiso de
escritura. Sin service role, nada de eso funciona.

La consecuencia es incómoda: **para todo lo que pasa por la API, RLS no protege nada.** Durante la
Fase 3 los endpoints quedaron además sin autenticación, así que cualquiera que conociera la URL
podía insertar eventos a nombre de cualquier estudiante. En un sistema donde la evidencia termina
delante de un docente que decide sobre una nota, eso no es un detalle.

## Decisión

**La autorización por estudiante se implementa en la capa de aplicación de la API, en el caso de
uso, y se prueba como cualquier otra regla de negocio.**

Autenticación:

- Token de Supabase Auth en `Authorization: Bearer <access_token>`.
- La firma se verifica con **ES256 contra el JWKS público** del proyecto
  (`/auth/v1/.well-known/jwks.json`). La API no guarda ningún secreto para autenticar: aunque
  alguien robara su configuración, no podría falsificar un token.
- La lista de algoritmos aceptados es **cerrada** (`ES256`, `RS256`). Aceptar el que diga el token
  es como se cuelan los ataques de confusión de algoritmo.
- El JWKS se cachea 10 minutos, para no meter una llamada de red en el camino más caliente del
  sistema.

Identificación del rol:

- El rol **no viaja en el JWT**: ahí el claim `role` vale siempre `authenticated`, que es el rol de
  PostgreSQL, no el nuestro. El rol del sistema se lee de `public.profiles`, con caché de 60 s.
- Un usuario que existe en Auth pero no tiene fila en `profiles` **no recibe rol por defecto**. Se
  rechaza. Adivinar aquí es como se acaba dando permisos de docente a quien no los tiene.

Reglas, en el caso de uso:

- Un **estudiante** solo registra eventos sobre sí mismo (`student_id` del cuerpo = `sub` del
  token) y solo lee los suyos; si pide los de otro, el filtro se ignora en silencio.
- Un **docente** ve la sesión entera y **no** puede registrar eventos: los reporta el cliente del
  estudiante.

Escape para desarrollo:

- `AUTH_ENABLED=false` desactiva lo anterior, porque la app de escritorio y el spike de visión
  necesitan mandar eventos antes de que exista su pantalla de login.
- Dos seguros: la API **se niega a arrancar** con la autenticación desactivada si `ENV` no es
  `local` ni `test`; y si la variable no existe, la autenticación queda **activada**. Olvidarla en
  un despliegue protege en vez de abrir.
- `GET /health` expone `auth: enabled | disabled`.

## Alternativas consideradas

- **Que la API use el token del usuario en vez de la service role key, y dejar que RLS haga todo.**
  Es la opción más elegante y la que menos código propio necesita. Se descartó porque rompe los dos
  casos que motivan la service role: servir preguntas sin `is_correct`, y escribir en
  `audio_analyses`, `alerts` y `risk_scores` desde los workers, que no actúan en nombre de ningún
  usuario. Quedaría un sistema con dos clientes de Supabase y la frontera entre ambos como fuente
  permanente de errores.
- **Poner el rol en `app_metadata` del JWT.** Ahorraría la consulta a `profiles` en cada petición.
  Se descartó porque exige tocar el usuario por la Admin API en cada cambio de rol, y deja dos
  fuentes de verdad para el mismo dato: el token (que no se puede revocar hasta que caduque) y la
  tabla. La caché de 60 s resuelve el coste sin ese riesgo.
- **Autorización en el router con decoradores.** Más rápido de escribir, pero mete reglas de
  negocio en un adaptador, que es exactamente lo que [`CLAUDE.md`](../../CLAUDE.md) §8 prohíbe, y
  las dejaría fuera de las pruebas unitarias de los casos de uso.
- **Dejarlo para el final, cuando haya login en los clientes.** Es lo que estaba pasando. El riesgo
  es que la API se despliegue en Render antes que el login, que es justo el orden que marca el
  cronograma.

## Consecuencias

**A favor:** la regla queda donde se puede probar — hay pruebas unitarias de que un estudiante no
puede reportar eventos de otro, y de integración de que la API responde 401 y 403. La verificación
de firma no necesita secretos. Desplegar la API abierta es imposible por configuración, no por
disciplina. Y los compañeros pueden seguir trabajando sin login gracias a un interruptor cuyo mal
uso está acotado.

**En contra:** duplicamos conceptualmente lo que RLS ya expresa, y si alguien añade un endpoint
nuevo y olvida pedir el actor, ese endpoint queda abierto sin que nada avise — no hay un mecanismo
que lo impida, solo la revisión de código. Cada petición puede costar una consulta a `profiles`
(mitigado con caché, a cambio de que un cambio de rol tarde hasta un minuto en notarse). Y el modo
`AUTH_ENABLED=false` es, por definición, un camino inseguro que existe en el código: los dos seguros
lo acotan, pero no lo eliminan.

**Pendiente:** un docente puede listar los eventos de **cualquier** sesión, no solo de las suyas.
Comprobarlo exige un repositorio de sesiones que todavía no existe; entra con SPEC-002.
