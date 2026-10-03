-- 0004 hardening: every signup is a student; teachers are promoted explicitly by an admin.
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id, full_name, email, role)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'full_name', new.email),
    new.email,
    'student'
  );
  return new;
end;
$$;

revoke execute on function public.handle_new_user() from public, anon, authenticated;

-- Students cannot change their own role through profiles_update_own.
create or replace function public.prevent_role_change()
returns trigger language plpgsql set search_path = '' as $$
begin
  if new.role is distinct from old.role and current_user not in ('postgres', 'service_role', 'supabase_admin') then
    raise exception 'role can only be changed by an administrator';
  end if;
  return new;
end;
$$;
revoke execute on function public.prevent_role_change() from public, anon, authenticated;

create trigger profiles_prevent_role_change
  before update on public.profiles
  for each row execute function public.prevent_role_change();
