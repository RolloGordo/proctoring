-- A lost audio fragment is an availability problem, not a signal about the
-- student.
--
-- For gaze_away a photo corroborates: the event stands on its own metadata
-- (yaw degrees, face count). For speech the fragment IS the whole evidence,
-- because the two conditions the project requires -- that what was said
-- resembles the question, and that a synthetic voice answers -- are computed by
-- the worker from that audio. Emitting speech_detected without it would leave a
-- "voice detected" nobody can ever verify, which is the unsupported accusation
-- the system promises not to make: reading aloud is not misconduct.
--
-- So the signal is dropped and recorded here instead, and the teacher can see
-- that nothing was being heard during that stretch.
alter table public.supervision_diagnostics
  drop constraint supervision_diagnostics_code_check;

alter table public.supervision_diagnostics
  add constraint supervision_diagnostics_code_check check (code in (
    'camera_interrupted', 'camera_no_image', 'camera_recovered',
    'vision_module_failed', 'vision_module_recovered',
    'vision_module_summary',
    'audio_segment_lost'
  ));
