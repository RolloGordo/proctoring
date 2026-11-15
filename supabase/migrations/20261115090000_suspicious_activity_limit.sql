-- Tope de actividades sospechosas por estudiante (reunión del 14/11/2026).
-- Cada señal que genera alerta cuenta como una advertencia; al llegar al tope el
-- docente recibe una alerta alta y el semáforo pasa a rojo. No cierra el examen:
-- la decisión sigue siendo del docente. NULL = sin tope.
alter table public.exam_sessions
  add column if not exists suspicious_activity_limit integer
  check (suspicious_activity_limit between 1 and 100);

comment on column public.exam_sessions.suspicious_activity_limit is
  'Advertencias (señales con alerta) por estudiante antes de avisar al docente que alcanzó el tope. NULL: sin tope.';
