-- The teacher's live session view needs all events, not only elevated alerts.
-- RLS on public.events still limits each subscriber to their own authorized rows:
-- events_student_select is student_id = auth.uid(), events_teacher_select is
-- private.is_session_teacher(session_id). Verified against the live database
-- before applying this.
alter publication supabase_realtime add table public.events;

-- Availability diagnostics, not misconduct signals.
--
-- signal_rejected is the one that matters most: when the API refuses a signal
-- the client drops it and the reason died in console.error, which in a kiosk
-- window nobody opens. An observed signal that vanishes without a trace is the
-- worst failure here -- in a case file it reads exactly like nothing happened.
alter table public.supervision_diagnostics
  drop constraint supervision_diagnostics_code_check;

alter table public.supervision_diagnostics
  add constraint supervision_diagnostics_code_check check (code in (
    'camera_interrupted', 'camera_no_image', 'camera_recovered',
    'vision_module_failed', 'vision_module_recovered',
    'vision_module_summary', 'audio_segment_lost', 'image_evidence_lost',
    'signal_rejected', 'signal_queue_stuck'
  ));
