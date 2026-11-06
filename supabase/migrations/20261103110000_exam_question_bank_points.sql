-- Per-exam overrides keep bank question values untouched and reproducible.
create table public.exam_session_question_points (
  session_id uuid not null references public.exam_sessions (id) on delete cascade,
  question_id uuid not null references public.questions (id) on delete cascade,
  points numeric(5, 2) not null check (points >= 0 and points <= 100),
  updated_at timestamptz not null default now(),
  primary key (session_id, question_id)
);

create index exam_session_question_points_question_id_idx
  on public.exam_session_question_points (question_id);

alter table public.exam_session_question_points enable row level security;

create policy exam_session_question_points_teacher_all
  on public.exam_session_question_points
  for all to authenticated
  using ((select private.is_session_teacher(session_id)))
  with check ((select private.is_session_teacher(session_id)));
