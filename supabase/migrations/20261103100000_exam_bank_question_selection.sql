-- Per-exam exclusions from attached question banks. Unlisted questions remain included.
create table public.exam_session_question_exclusions (
  session_id uuid not null references public.exam_sessions (id) on delete cascade,
  question_id uuid not null references public.questions (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (session_id, question_id)
);

create index exam_session_question_exclusions_question_id_idx
  on public.exam_session_question_exclusions (question_id);

alter table public.exam_session_question_exclusions enable row level security;

create policy exam_session_question_exclusions_teacher_all
  on public.exam_session_question_exclusions
  for all to authenticated
  using ((select private.is_session_teacher(session_id)))
  with check ((select private.is_session_teacher(session_id)));
