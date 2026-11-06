-- SEC-01: la cara de referencia la escribe solo la API.
--
-- Hasta ahora `reference_faces_student_all` dejaba al estudiante hacer
-- INSERT/UPDATE/DELETE de su propia fila con su token, directo contra
-- PostgREST. Con eso podía escribir su `embedding` a mano, y el worker de IA
-- compara contra el embedding guardado sin volver a mirar la foto: bastaba con
-- poner el embedding de otra persona para que esa persona pasara la
-- verificación por él. Ningún cliente escribe en esta tabla (la web y la app
-- pasan por `POST /api/v1/me/reference-face`), así que el estudiante se queda
-- solo con leer la suya. La API usa la service role y no le afecta.

alter table public.reference_faces
  add column if not exists needs_review boolean not null default false;

comment on column public.reference_faces.needs_review is
  'La referencia se cambió después de usarse para verificar. Hasta que un docente admita al estudiante, una coincidencia con ella no basta para entrar.';

drop policy if exists reference_faces_student_all on public.reference_faces;

create policy reference_faces_student_select on public.reference_faces
  for select to authenticated
  using (student_id = (select auth.uid()));

revoke insert, update, delete, truncate on public.reference_faces from anon, authenticated;
