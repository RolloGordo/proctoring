-- Encuadre insuficiente (Jesús Limay): la cámara deja de mostrar hombros y
-- brazos durante el examen, típicamente porque se volvió a apuntar solo a la
-- cara. Es una señal revisable, como prohibited_object: no acusa de nada.
alter type public.event_type add value if not exists 'framing_lost';
