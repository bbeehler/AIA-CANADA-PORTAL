-- Add administrator-managed member identity fields while keeping Auth private.

alter table public.profiles
add column if not exists email text not null default '';

update public.profiles as profile
set email = lower(coalesce(auth_user.email, ''))
from auth.users as auth_user
where profile.id = auth_user.id
  and profile.email is distinct from lower(coalesce(auth_user.email, ''));

create unique index if not exists profiles_email_lower_unique
on public.profiles (lower(email))
where email <> '';

create or replace function private.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, email, full_name, organization, province)
  values (
    new.id,
    lower(coalesce(new.email, '')),
    coalesce(new.raw_user_meta_data ->> 'full_name', ''),
    coalesce(new.raw_user_meta_data ->> 'organization', ''),
    coalesce(new.raw_user_meta_data ->> 'province', '')
  )
  on conflict (id) do update
  set email = excluded.email;
  return new;
end;
$$;

revoke all on function private.handle_new_user() from public, anon, authenticated;

create or replace function private.sync_profile_email()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  update public.profiles
  set email = lower(coalesce(new.email, ''))
  where id = new.id;
  return new;
end;
$$;

revoke all on function private.sync_profile_email() from public, anon, authenticated;

drop trigger if exists on_auth_user_email_updated on auth.users;
create trigger on_auth_user_email_updated
after update of email on auth.users
for each row
when (old.email is distinct from new.email)
execute function private.sync_profile_email();

