# ADR-0003 — Supabase para datos, autenticación, almacenamiento y tiempo real

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-10-03 |
| **Decide** | Silva Vega, Héctor (Project Manager) |

## Contexto

Necesitamos base de datos relacional, inicio de sesión con roles, almacenamiento de capturas y
audio, y alertas en vivo al docente. Presupuesto: **cero**. Y cuatro personas que deben poder
levantar todo en local sin configurar media docena de servicios.

## Decisión

**Supabase** como plataforma única:

- **PostgreSQL** para los datos, con **RLS** activado en todas las tablas.
- **Auth** para inicio de sesión y roles con JWT (`profiles.role` es `teacher` o `student`).
- **Storage** para capturas y fragmentos de audio, en un bucket privado `evidences`, con **URLs
  firmadas** que genera la API.
- **Realtime** para las alertas en vivo: la web del docente se suscribe a los cambios de la tabla
  `alerts` en lugar de preguntar cada segundo.

La API nunca expone la clave de servicio; el cliente usa solo la clave anónima y RLS hace el resto.
El acceso a Supabase está detrás de un puerto, así que hay un adaptador en memoria equivalente.

## Alternativas consideradas

- **PostgreSQL propio + autenticación a mano + S3 + WebSockets.** Más control y sin dependencia de
  un proveedor, pero son cuatro piezas que hay que desplegar, asegurar y pagar.
- **Firebase.** Realtime y autenticación excelentes, pero el modelo de datos es documental y el
  nuestro es claramente relacional (sesiones, preguntas, respuestas, eventos, decisiones).
- **PocketBase.** Ligero y todo en uno, pero hay que alojarlo y su ecosistema es mucho más pequeño.

## Consecuencias

**A favor:** cuatro necesidades resueltas con un solo proveedor y un solo juego de credenciales;
Realtime nos ahorra escribir un servidor de WebSockets; RLS pone la seguridad en la base de datos,
donde no se puede saltar desde el cliente.

**En contra:** dependencia de un proveedor concreto, y el plan gratuito tiene límites (pausa por
inactividad, cuota de almacenamiento) que pueden mordernos en la demo. Mitigación: el acceso está
detrás de un puerto, así que migrar a un PostgreSQL propio significa escribir un adaptador nuevo, no
reescribir el sistema.
