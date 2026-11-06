-- Portada de cada curso: una imagen que el docente sube para reconocerlo de un
-- vistazo en su panel y en «Mis cursos».
--
-- La imagen vive en un bucket privado, igual que la evidencia: la web la sube
-- con una URL firmada que entrega la API y la muestra con otra URL firmada que
-- caduca en una hora. No hay políticas de Storage para usuarios: solo la API
-- (service role) firma, y lo hace después de comprobar que el curso es del
-- docente que la pide.

alter table public.courses
  add column if not exists cover_path text;

-- Solo rutas con la forma que genera la API: `<id del curso>/<32 hex>.<ext>`.
-- Así una fila no puede apuntar a la portada de otro curso ni a cualquier otra
-- ruta del bucket, aunque alguien escribiera en la tabla sin pasar por la API.
alter table public.courses
  drop constraint if exists courses_cover_path_format;
alter table public.courses
  add constraint courses_cover_path_format check (
    cover_path is null
    or cover_path ~ ('^' || id::text || '/[0-9a-f]{32}\.(webp|jpg|png)$')
  );

comment on column public.courses.cover_path is
  'Ruta de la portada en el bucket course-covers, o null si el curso no tiene imagen.';

-- 2 MB y solo imágenes: la web la reduce a 1600 px y la pasa a WebP antes de
-- subirla, así que una portada real pesa unos cientos de KB. El límite protege
-- la cuota del plan gratuito si alguien sube el archivo sin pasar por la web.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('course-covers', 'course-covers', false, 2097152, array['image/webp', 'image/jpeg', 'image/png'])
on conflict (id) do nothing;
