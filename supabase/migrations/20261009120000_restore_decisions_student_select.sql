-- SPEC-006: preservar el acceso directo solo de lectura a las decisiones propias.
-- La migración 20261009010000 puede estar YA APLICADA en otros entornos.
-- NO modificarla para intentar revertirla: crear la política aquí de nuevo.
-- La condición teacher-only de INSERT/UPDATE y el endurecimiento RLS
-- de session_participants y answers NO se tocan.
-- El DROP hace que esta migración sea segura si un entorno ya conservó la política.
drop policy if exists decisions_student_select on public.decisions;
create policy decisions_student_select on public.decisions
  for select to authenticated
  using (student_id = (select auth.uid()));
