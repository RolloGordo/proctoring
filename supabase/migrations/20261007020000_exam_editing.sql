-- Editar y cancelar examenes, y nota sobre una escala.
--
-- Dos cosas que faltaban:
--
-- 1. Un docente que se equivocaba al crear un examen no podia deshacerlo. Ahora
--    un examen se puede cancelar, y el estudiante que llega con su codigo recibe
--    "lo cancelo tu docente" en vez de un error generico. Se cancela en vez de
--    borrarse cuando ya hubo participantes: borrar la fila se llevaria por
--    delante los eventos, las alertas y las respuestas, que son justamente la
--    evidencia que este sistema existe para conservar.
--
-- 2. La nota salia en "puntos", la suma de lo que valiera cada pregunta. En Peru
--    se califica sobre 20, asi que el examen guarda su escala y la nota se
--    reparte sobre ella. Por defecto 20, que es lo que espera el docente.

-- `cancelled` no se usa en esta misma migracion a proposito: PostgreSQL no deja
-- usar un valor de enum recien anadido dentro de la transaccion que lo crea.
alter type session_status add value if not exists 'cancelled';

alter table public.exam_sessions
  add column if not exists max_score numeric(5, 2) not null default 20;

comment on column public.exam_sessions.max_score is
  'Nota maxima del examen. 20 por defecto (escala peruana). Los puntos de las '
  'preguntas se reparten proporcionalmente sobre esta nota.';

-- Una nota maxima de cero haria imposible calcular ninguna nota: la division por
-- el maximo es como se pasa de puntos a nota.
alter table public.exam_sessions
  drop constraint if exists exam_sessions_max_score_positive;
alter table public.exam_sessions
  add constraint exam_sessions_max_score_positive check (max_score > 0 and max_score <= 100);

-- Quien lo cancelo y cuando. `status` solo dice que esta cancelado; para
-- responderle a un estudiante que pregunta hace falta saber cuando paso.
alter table public.exam_sessions
  add column if not exists cancelled_at timestamptz;

comment on column public.exam_sessions.cancelled_at is
  'Cuando se cancelo. Nulo mientras el examen siga en pie.';
