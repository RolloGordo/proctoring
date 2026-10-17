-- 0005 question banks
--
-- Hasta aqui una pregunta pertenecia a UN examen (`questions.session_id`), asi que
-- el docente tenia que escribirlas de nuevo en cada examen. Un banco es un
-- conjunto de preguntas que vive aparte y del que un examen EXTRAE.
--
-- Decisiones:
--
-- 1. El banco es del DOCENTE, y `course_id` es opcional. Asi puede tener un banco
--    general ("Bases de datos") y usarlo en los examenes de varios cursos, o uno
--    atado a un curso concreto. Lo pidio asi el equipo.
-- 2. Una pregunta pertenece a un banco O a un examen, nunca a los dos ni a
--    ninguno. Las preguntas sueltas de un examen siguen funcionando igual: no se
--    migra nada y lo que ya existe sigue valido.
-- 3. Un examen puede sacar de VARIOS bancos (`exam_session_banks`), porque el
--    docente quiera combinar dos temas.
--
-- `exam_sessions.question_pool_size` ya existia sin usarse: es cuantas preguntas
-- recibe cada estudiante del total disponible.

create table public.question_banks (
  id uuid primary key default gen_random_uuid(),
  teacher_id uuid not null references public.profiles (id) on delete cascade,
  -- Opcional a proposito: un banco sin curso sirve para todos los del docente.
  course_id uuid references public.courses (id) on delete set null,
  name text not null check (char_length(btrim(name)) > 0),
  description text,
  created_at timestamptz not null default now()
);
create index question_banks_teacher_id_idx on public.question_banks (teacher_id, created_at desc);
create index question_banks_course_id_idx on public.question_banks (course_id);

-- De que bancos extrae un examen. Varios, porque un parcial puede combinar temas.
create table public.exam_session_banks (
  session_id uuid not null references public.exam_sessions (id) on delete cascade,
  bank_id uuid not null references public.question_banks (id) on delete cascade,
  added_at timestamptz not null default now(),
  primary key (session_id, bank_id)
);
create index exam_session_banks_bank_id_idx on public.exam_session_banks (bank_id);

-- Una pregunta ahora puede colgar de un banco en vez de un examen.
alter table public.questions add column bank_id uuid references public.question_banks (id) on delete cascade;
alter table public.questions alter column session_id drop not null;

-- Exactamente uno de los dos. Sin esto podria quedar una pregunta huerfana (sin
-- examen ni banco), invisible para todo el mundo y imposible de borrar desde la
-- interfaz.
alter table public.questions add constraint questions_belongs_to_one
  check ((session_id is not null) <> (bank_id is not null));

-- `unique (session_id, position)` ya no sirve tal cual: con `session_id` nulo,
-- PostgreSQL considera distintos todos los nulos y dejaria repetir posiciones
-- dentro de un banco. Se reemplaza por dos indices parciales, uno por caso.
alter table public.questions drop constraint questions_session_id_position_key;
create unique index questions_session_position_idx
  on public.questions (session_id, position) where session_id is not null;
create unique index questions_bank_position_idx
  on public.questions (bank_id, position) where bank_id is not null;
create index questions_bank_id_idx on public.questions (bank_id);

-- ===== RLS =====
-- La API usa la service role key y omite RLS; estas politicas protegen el acceso
-- directo desde el navegador del docente.
alter table public.question_banks enable row level security;
alter table public.exam_session_banks enable row level security;

create or replace function private.is_bank_owner(p_bank_id uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.question_banks b
    where b.id = p_bank_id and b.teacher_id = (select auth.uid())
  );
$$;

create policy question_banks_teacher_all on public.question_banks
  for all to authenticated
  using (teacher_id = (select auth.uid()))
  with check (teacher_id = (select auth.uid()));

-- Para atar un banco a un examen hay que ser dueno de LOS DOS. Si no, un docente
-- podria colgar el banco de otro de su propio examen y leerlo entero.
create policy exam_session_banks_teacher_all on public.exam_session_banks
  for all to authenticated
  using ((select private.is_session_teacher(session_id)) and (select private.is_bank_owner(bank_id)))
  with check ((select private.is_session_teacher(session_id)) and (select private.is_bank_owner(bank_id)));

-- La politica de `questions` miraba solo `session_id`, que ahora puede ser nulo:
-- una pregunta de banco quedaba sin dueno y nadie podia leerla.
drop policy if exists questions_teacher_all on public.questions;
create policy questions_teacher_all on public.questions
  for all to authenticated
  using (
    (session_id is not null and (select private.is_session_teacher(session_id)))
    or (bank_id is not null and (select private.is_bank_owner(bank_id)))
  )
  with check (
    (session_id is not null and (select private.is_session_teacher(session_id)))
    or (bank_id is not null and (select private.is_bank_owner(bank_id)))
  );

drop policy if exists question_options_teacher_all on public.question_options;
create policy question_options_teacher_all on public.question_options
  for all to authenticated
  using (exists (
    select 1 from public.questions q
    where q.id = question_id
      and ((q.session_id is not null and (select private.is_session_teacher(q.session_id)))
        or (q.bank_id is not null and (select private.is_bank_owner(q.bank_id))))
  ))
  with check (exists (
    select 1 from public.questions q
    where q.id = question_id
      and ((q.session_id is not null and (select private.is_session_teacher(q.session_id)))
        or (q.bank_id is not null and (select private.is_bank_owner(q.bank_id))))
  ));
