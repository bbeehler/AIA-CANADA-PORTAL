-- AIA Canada Data Portal: schema, authorization, storage and governance.
-- Generated deterministically after the Supabase CLI was unavailable in the build environment.

create extension if not exists pgcrypto;
create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null default '',
  organization text not null default '',
  province text not null default '',
  role text not null default 'member' check (role in ('member', 'analyst', 'admin')),
  membership_status text not null default 'pending' check (membership_status in ('pending', 'active', 'suspended')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.source_reports (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  publisher text not null default 'AIA Canada',
  publication_date date,
  source_url text,
  citation text not null,
  notes text,
  created_at timestamptz not null default now()
);

create table public.datasets (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  title text not null,
  description text not null default '',
  data_year integer check (data_year between 1900 and 2200),
  source_report_id uuid references public.source_reports(id) on delete set null,
  status text not null default 'draft' check (status in ('draft', 'published', 'archived')),
  version integer not null default 1 check (version > 0),
  row_count integer not null default 0 check (row_count >= 0),
  source_filename text,
  storage_path text,
  created_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.benchmark_observations (
  id bigint generated always as identity primary key,
  dataset_id uuid not null references public.datasets(id) on delete cascade,
  segment text not null check (segment in ('Mechanical', 'Tire')),
  shop_size text not null,
  geography_type text not null check (geography_type in ('region', 'national')),
  geography text not null,
  affiliation text not null default 'All',
  sample_size integer check (sample_size >= 0),
  average_repair_orders_year numeric,
  average_hours_repair_order numeric,
  average_repair_orders_technician_day numeric,
  percentage_exceed_two_hours numeric check (percentage_exceed_two_hours between 0 and 100),
  percentage_sales_from_tires numeric check (percentage_sales_from_tires between 0 and 100),
  percentage_with_apprentices numeric check (percentage_with_apprentices between 0 and 100),
  hours_sold_technician_day numeric,
  percentage_with_service_advisor numeric check (percentage_with_service_advisor between 0 and 100),
  percentage_parts_from_oem numeric check (percentage_parts_from_oem between 0 and 100),
  source_page integer check (source_page > 0),
  created_at timestamptz not null default now(),
  unique (dataset_id, segment, shop_size, geography_type, geography, affiliation)
);

create table public.performance_benchmarks (
  id bigint generated always as identity primary key,
  dataset_id uuid not null references public.datasets(id) on delete cascade,
  shop_type text not null check (shop_type in ('Mechanical', 'Tire')),
  cohort text not null,
  metric_code text not null,
  metric_label text not null,
  value numeric not null,
  unit text not null check (unit in ('count', 'hours', 'percent', 'ratio', 'cad', 'days', 'years')),
  sort_order integer not null default 0,
  source_page integer check (source_page > 0),
  created_at timestamptz not null default now(),
  unique (dataset_id, shop_type, cohort, metric_code)
);

create table public.contributions (
  id uuid primary key default gen_random_uuid(),
  contributor_id uuid not null references public.profiles(id) on delete restrict,
  organization text not null,
  reporting_period_start date not null,
  reporting_period_end date not null,
  original_filename text not null,
  storage_path text not null unique,
  row_count integer not null check (row_count > 0),
  notes text not null default '',
  status text not null default 'submitted' check (status in ('submitted', 'in_review', 'approved', 'rejected', 'archived')),
  admin_notes text not null default '',
  reviewed_by uuid references public.profiles(id) on delete set null,
  submitted_at timestamptz not null default now(),
  reviewed_at timestamptz,
  updated_at timestamptz not null default now(),
  check (reporting_period_end >= reporting_period_start)
);

create table public.resources (
  id uuid primary key default gen_random_uuid(),
  section text not null,
  title text not null,
  summary text not null,
  resource_type text not null,
  external_url text,
  status text not null default 'draft' check (status in ('draft', 'published', 'archived')),
  sort_order integer not null default 0,
  published_at timestamptz,
  created_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.audit_log (
  id bigint generated always as identity primary key,
  actor_id uuid,
  action text not null,
  entity_type text not null,
  entity_id text not null,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index benchmark_observations_dataset_idx on public.benchmark_observations(dataset_id);
create index performance_benchmarks_dataset_idx on public.performance_benchmarks(dataset_id);
create index contributions_contributor_idx on public.contributions(contributor_id, submitted_at desc);
create index contributions_status_idx on public.contributions(status, submitted_at desc);
create index resources_status_sort_idx on public.resources(status, section, sort_order);
create index audit_log_created_idx on public.audit_log(created_at desc);

create or replace function private.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1 from public.profiles
    where id = (select auth.uid())
      and role = 'admin'
      and membership_status = 'active'
  );
$$;

create or replace function private.is_active_member()
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1 from public.profiles
    where id = (select auth.uid())
      and membership_status = 'active'
  );
$$;

revoke all on function private.is_admin() from public, anon;
revoke all on function private.is_active_member() from public, anon;
grant usage on schema private to authenticated;
grant execute on function private.is_admin() to authenticated;
grant execute on function private.is_active_member() to authenticated;

create or replace function private.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_set_updated_at before update on public.profiles
for each row execute function private.set_updated_at();
create trigger datasets_set_updated_at before update on public.datasets
for each row execute function private.set_updated_at();
create trigger contributions_set_updated_at before update on public.contributions
for each row execute function private.set_updated_at();
create trigger resources_set_updated_at before update on public.resources
for each row execute function private.set_updated_at();

create or replace function private.set_contribution_reviewer()
returns trigger
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
begin
  if new.status is distinct from old.status and (select private.is_admin()) then
    new.reviewed_by = (select auth.uid());
    new.reviewed_at = now();
  end if;
  return new;
end;
$$;

create trigger contributions_set_reviewer before update on public.contributions
for each row execute function private.set_contribution_reviewer();

create or replace function private.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  insert into public.profiles (id, full_name, organization, province)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'full_name', ''),
    coalesce(new.raw_user_meta_data ->> 'organization', ''),
    coalesce(new.raw_user_meta_data ->> 'province', '')
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

revoke all on function private.handle_new_user() from public, anon, authenticated;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function private.handle_new_user();

create or replace function public.admin_update_member(
  target_user_id uuid,
  new_membership_status text,
  new_role text
)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if not (select private.is_admin()) then
    raise exception 'Administrator access required' using errcode = '42501';
  end if;
  if new_membership_status not in ('pending', 'active', 'suspended') then
    raise exception 'Invalid membership status';
  end if;
  if new_role not in ('member', 'analyst', 'admin') then
    raise exception 'Invalid portal role';
  end if;
  if target_user_id = (select auth.uid())
     and (new_role <> 'admin' or new_membership_status <> 'active') then
    raise exception 'Administrators cannot demote or suspend their own account';
  end if;
  update public.profiles
  set membership_status = new_membership_status, role = new_role
  where id = target_user_id;
  if not found then
    raise exception 'Member not found';
  end if;
  insert into public.audit_log(actor_id, action, entity_type, entity_id, details)
  values ((select auth.uid()), 'member_access_updated', 'profile', target_user_id::text,
          jsonb_build_object('membership_status', new_membership_status, 'role', new_role));
end;
$$;

revoke all on function public.admin_update_member(uuid, text, text) from public, anon;
grant execute on function public.admin_update_member(uuid, text, text) to authenticated;

create or replace function private.audit_governed_change()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  record_id text;
  audit_details jsonb;
begin
  if tg_op = 'DELETE' then
    record_id = old.id::text;
    audit_details = jsonb_build_object('old_status', to_jsonb(old) ->> 'status');
  elsif tg_op = 'INSERT' then
    record_id = new.id::text;
    audit_details = jsonb_build_object('new_status', to_jsonb(new) ->> 'status');
  else
    record_id = new.id::text;
    audit_details = jsonb_build_object(
      'old_status', to_jsonb(old) ->> 'status',
      'new_status', to_jsonb(new) ->> 'status'
    );
  end if;
  insert into public.audit_log(actor_id, action, entity_type, entity_id, details)
  values ((select auth.uid()), lower(tg_op), tg_table_name, record_id, audit_details);
  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

revoke all on function private.audit_governed_change() from public, anon, authenticated;

create trigger contributions_audit after insert or update or delete on public.contributions
for each row execute function private.audit_governed_change();
create trigger datasets_audit after insert or update or delete on public.datasets
for each row execute function private.audit_governed_change();
create trigger resources_audit after insert or update or delete on public.resources
for each row execute function private.audit_governed_change();

alter table public.profiles enable row level security;
alter table public.source_reports enable row level security;
alter table public.datasets enable row level security;
alter table public.benchmark_observations enable row level security;
alter table public.performance_benchmarks enable row level security;
alter table public.contributions enable row level security;
alter table public.resources enable row level security;
alter table public.audit_log enable row level security;

create policy profiles_select_own_or_admin on public.profiles
for select to authenticated
using ((select auth.uid()) = id or (select private.is_admin()));

create policy source_reports_select_active on public.source_reports
for select to authenticated
using ((select private.is_active_member()) or (select private.is_admin()));
create policy source_reports_admin_all on public.source_reports
for all to authenticated
using ((select private.is_admin()))
with check ((select private.is_admin()));

create policy datasets_select_published on public.datasets
for select to authenticated
using (
  ((select private.is_active_member()) and status = 'published')
  or (select private.is_admin())
);
create policy datasets_admin_all on public.datasets
for all to authenticated
using ((select private.is_admin()))
with check ((select private.is_admin()));

create policy observations_select_published on public.benchmark_observations
for select to authenticated
using (
  (select private.is_active_member())
  and exists (select 1 from public.datasets d where d.id = dataset_id and d.status = 'published')
);
create policy observations_admin_all on public.benchmark_observations
for all to authenticated
using ((select private.is_admin()))
with check ((select private.is_admin()));

create policy performance_select_published on public.performance_benchmarks
for select to authenticated
using (
  (select private.is_active_member())
  and exists (select 1 from public.datasets d where d.id = dataset_id and d.status = 'published')
);
create policy performance_admin_all on public.performance_benchmarks
for all to authenticated
using ((select private.is_admin()))
with check ((select private.is_admin()));

create policy contributions_select_own_or_admin on public.contributions
for select to authenticated
using ((select auth.uid()) = contributor_id or (select private.is_admin()));
create policy contributions_insert_own on public.contributions
for insert to authenticated
with check (
  (select private.is_active_member())
  and (select auth.uid()) = contributor_id
  and status = 'submitted'
);
create policy contributions_admin_update on public.contributions
for update to authenticated
using ((select private.is_admin()))
with check ((select private.is_admin()));

create policy resources_select_published on public.resources
for select to authenticated
using (
  ((select private.is_active_member()) and status = 'published')
  or (select private.is_admin())
);
create policy resources_admin_all on public.resources
for all to authenticated
using ((select private.is_admin()))
with check ((select private.is_admin()));

create policy audit_log_admin_select on public.audit_log
for select to authenticated
using ((select private.is_admin()));

-- Explicit grants support Supabase projects where new public tables are not
-- automatically exposed to the Data API. RLS remains the authorization layer.
grant usage on schema public to authenticated;
grant select on public.profiles, public.source_reports, public.datasets,
  public.benchmark_observations, public.performance_benchmarks,
  public.contributions, public.resources, public.audit_log to authenticated;
grant insert on public.contributions, public.datasets, public.benchmark_observations,
  public.performance_benchmarks, public.resources, public.source_reports to authenticated;
grant update on public.contributions, public.datasets, public.benchmark_observations,
  public.performance_benchmarks, public.resources, public.source_reports to authenticated;
grant usage, select on all sequences in schema public to authenticated;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'member-contributions', 'member-contributions', false, 10485760,
  array['text/csv', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']
)
on conflict (id) do nothing;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('admin-datasets', 'admin-datasets', false, 26214400, array['text/csv'])
on conflict (id) do nothing;

create policy member_contribution_upload on storage.objects
for insert to authenticated
with check (
  bucket_id = 'member-contributions'
  and (storage.foldername(name))[1] = (select auth.uid())::text
  and (select private.is_active_member())
);

create policy member_contribution_read on storage.objects
for select to authenticated
using (
  bucket_id = 'member-contributions'
  and ((storage.foldername(name))[1] = (select auth.uid())::text or (select private.is_admin()))
);

create policy member_contribution_cleanup on storage.objects
for delete to authenticated
using (
  bucket_id = 'member-contributions'
  and (
    (select private.is_admin())
    or (
      (storage.foldername(name))[1] = (select auth.uid())::text
      and not exists (select 1 from public.contributions c where c.storage_path = name)
    )
  )
);

create policy admin_dataset_read on storage.objects
for select to authenticated
using (bucket_id = 'admin-datasets' and (select private.is_admin()));
create policy admin_dataset_insert on storage.objects
for insert to authenticated
with check (bucket_id = 'admin-datasets' and (select private.is_admin()));
create policy admin_dataset_update on storage.objects
for update to authenticated
using (bucket_id = 'admin-datasets' and (select private.is_admin()))
with check (bucket_id = 'admin-datasets' and (select private.is_admin()));
create policy admin_dataset_delete on storage.objects
for delete to authenticated
using (bucket_id = 'admin-datasets' and (select private.is_admin()));

insert into public.source_reports (id, title, publisher, publication_date, citation, notes)
values (
  '11111111-1111-4111-8111-111111111111',
  'The View from Here: 2015 Productivity Benchmarks in the Canadian Automotive Service Sector',
  'Automotive Industries Association of Canada',
  '2016-09-01',
  'AIA Canada. The View from Here: 2015 Productivity Benchmarks in the Canadian Automotive Service Sector. Last updated September 2016.',
  'Historical survey of 572 automotive service providers. Values must be displayed with year and source context.'
)
on conflict (id) do nothing;

insert into public.datasets (
  id, slug, title, description, data_year, source_report_id, status, version, row_count
)
values (
  '22222222-2222-4222-8222-222222222222',
  'aia-2015-productivity-benchmarks',
  '2015 Productivity Benchmarks',
  'Regional, shop-size and high-performance cohort benchmarks from AIA Canada research.',
  2015,
  '11111111-1111-4111-8111-111111111111',
  'published',
  1,
  114
)
on conflict (id) do nothing;

insert into public.resources (
  id, section, title, summary, resource_type, status, sort_order, published_at
)
values
  (
    '33333333-3333-4333-8333-333333333331', 'Featured research', '2015 Productivity Benchmarks',
    'Benchmark repair orders, labour sales and technician productivity by shop size and region.',
    'Research report', 'published', 10, '2016-09-01'
  ),
  (
    '33333333-3333-4333-8333-333333333332', 'Data guidance', 'How member contributions are reviewed',
    'AIA Canada validates structure, removes direct identifiers and approves data before aggregation.',
    'Methodology', 'published', 20, now()
  )
on conflict (id) do nothing;
