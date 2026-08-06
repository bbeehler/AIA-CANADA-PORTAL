-- Approved member contributions become a governed, privacy-safe analytics pool.
-- Raw shop observations remain visible only to active AIA Canada administrators.

alter table public.contributions
  add column if not exists ingested_row_count integer not null default 0
    check (ingested_row_count >= 0),
  add column if not exists ingested_at timestamptz;

create table public.approved_shop_observations (
  id bigint generated always as identity primary key,
  contribution_id uuid not null references public.contributions(id) on delete cascade,
  contributor_id uuid not null references public.profiles(id) on delete restrict,
  row_number integer not null check (row_number > 0),
  reporting_month date not null check (reporting_month = date_trunc('month', reporting_month)::date),
  province text not null check (
    province in ('AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC', 'SK', 'YT')
  ),
  municipality text,
  forward_sortation_area text check (
    forward_sortation_area is null or forward_sortation_area ~ '^[A-Z][0-9][A-Z]$'
  ),
  shop_type text not null check (shop_type in ('Mechanical', 'Tire', 'Collision', 'Other')),
  bay_count numeric not null check (bay_count > 0),
  technician_count numeric not null check (technician_count > 0),
  repair_orders numeric not null check (repair_orders >= 0),
  hours_sold numeric not null check (hours_sold >= 0),
  labour_sales_cad numeric not null check (labour_sales_cad >= 0),
  parts_sales_cad numeric not null check (parts_sales_cad >= 0),
  tire_sales_cad numeric not null check (tire_sales_cad >= 0),
  ingested_at timestamptz not null default now(),
  unique (contribution_id, row_number)
);

comment on table public.approved_shop_observations is
  'Validated shop-month rows from approved contributions. Raw values are restricted to AIA Canada administrators.';

create index approved_shop_observations_contribution_idx
  on public.approved_shop_observations (contribution_id);
create index approved_shop_observations_contributor_idx
  on public.approved_shop_observations (contributor_id);
create index approved_shop_observations_pool_idx
  on public.approved_shop_observations (reporting_month desc, province, shop_type, contribution_id);

create table public.member_benchmark_aggregates (
  id bigint generated always as identity primary key,
  reporting_month date not null,
  geography_type text not null check (geography_type in ('national', 'province')),
  geography_code text not null,
  shop_type text not null check (shop_type in ('Mechanical', 'Tire', 'Collision', 'Other')),
  contributor_count integer not null check (contributor_count >= 5),
  submitted_row_count integer not null check (submitted_row_count >= contributor_count),
  privacy_threshold integer not null default 5 check (privacy_threshold >= 5),
  average_bay_count numeric not null,
  average_technician_count numeric not null,
  average_repair_orders numeric not null,
  average_hours_sold numeric not null,
  hours_per_repair_order numeric,
  hours_per_technician numeric,
  average_labour_sales_cad numeric not null,
  average_parts_sales_cad numeric not null,
  average_tire_sales_cad numeric not null,
  average_total_sales_cad numeric not null,
  sales_per_repair_order_cad numeric,
  refreshed_at timestamptz not null default now(),
  unique (reporting_month, geography_type, geography_code, shop_type),
  check (
    (geography_type = 'national' and geography_code = 'CA')
    or (geography_type = 'province' and geography_code in (
      'AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC', 'SK', 'YT'
    ))
  )
);

comment on table public.member_benchmark_aggregates is
  'Member-visible shop benchmarks. Cohorts with fewer than five independent contributors are never stored.';

create index member_benchmark_aggregates_filter_idx
  on public.member_benchmark_aggregates (
    geography_type, geography_code, shop_type, reporting_month desc
  );

alter table public.approved_shop_observations enable row level security;
alter table public.member_benchmark_aggregates enable row level security;

create policy approved_shop_observations_admin_all
on public.approved_shop_observations
for all to authenticated
using ((select private.is_admin()))
with check ((select private.is_admin()));

create policy member_benchmark_aggregates_select_active
on public.member_benchmark_aggregates
for select to authenticated
using (
  ((select private.is_active_member()) and contributor_count >= privacy_threshold)
  or (select private.is_admin())
);

create policy member_benchmark_aggregates_admin_insert
on public.member_benchmark_aggregates
for insert to authenticated
with check ((select private.is_admin()));

create policy member_benchmark_aggregates_admin_delete
on public.member_benchmark_aggregates
for delete to authenticated
using ((select private.is_admin()));

grant select, insert, delete on public.approved_shop_observations to authenticated;
grant select, insert, delete on public.member_benchmark_aggregates to authenticated;
grant usage, select on sequence public.approved_shop_observations_id_seq to authenticated;
grant usage, select on sequence public.member_benchmark_aggregates_id_seq to authenticated;

create or replace function public.rebuild_member_benchmark_aggregates()
returns integer
language plpgsql
security invoker
set search_path = ''
as $$
declare
  aggregate_count integer;
begin
  if not (select private.is_admin()) then
    raise exception 'Only an active AIA Canada administrator can rebuild member benchmarks.';
  end if;

  delete from public.member_benchmark_aggregates;

  insert into public.member_benchmark_aggregates (
    reporting_month,
    geography_type,
    geography_code,
    shop_type,
    contributor_count,
    submitted_row_count,
    privacy_threshold,
    average_bay_count,
    average_technician_count,
    average_repair_orders,
    average_hours_sold,
    hours_per_repair_order,
    hours_per_technician,
    average_labour_sales_cad,
    average_parts_sales_cad,
    average_tire_sales_cad,
    average_total_sales_cad,
    sales_per_repair_order_cad,
    refreshed_at
  )
  select
    observations.reporting_month,
    case when grouping(observations.province) = 1 then 'national' else 'province' end,
    case when grouping(observations.province) = 1 then 'CA' else observations.province end,
    observations.shop_type,
    count(distinct observations.contributor_id)::integer,
    count(*)::integer,
    5,
    round(avg(observations.bay_count), 2),
    round(avg(observations.technician_count), 2),
    round(avg(observations.repair_orders), 2),
    round(avg(observations.hours_sold), 2),
    round(sum(observations.hours_sold) / nullif(sum(observations.repair_orders), 0), 2),
    round(sum(observations.hours_sold) / nullif(sum(observations.technician_count), 0), 2),
    round(avg(observations.labour_sales_cad), 2),
    round(avg(observations.parts_sales_cad), 2),
    round(avg(observations.tire_sales_cad), 2),
    round(avg(
      observations.labour_sales_cad + observations.parts_sales_cad + observations.tire_sales_cad
    ), 2),
    round(sum(
      observations.labour_sales_cad + observations.parts_sales_cad + observations.tire_sales_cad
    ) / nullif(sum(observations.repair_orders), 0), 2),
    now()
  from public.approved_shop_observations observations
  join public.contributions contributions
    on contributions.id = observations.contribution_id
   and contributions.status = 'approved'
  group by grouping sets (
    (observations.reporting_month, observations.shop_type),
    (observations.reporting_month, observations.province, observations.shop_type)
  )
  having count(distinct observations.contributor_id) >= 5;

  get diagnostics aggregate_count = row_count;
  return aggregate_count;
end;
$$;

revoke execute on function public.rebuild_member_benchmark_aggregates() from public, anon;
grant execute on function public.rebuild_member_benchmark_aggregates() to authenticated;

update public.resources
set
  summary = 'How validated member submissions become privacy-safe industry benchmarks.',
  content = '### Review and aggregation process

1. **Prepare:** Members use the standard template or guided form and exclude customer, employee, vehicle and invoice identifiers.
2. **Validate:** The portal checks every field and stores only a normalized private CSV.
3. **Review:** AIA Canada reviews each submission and repeats validation before approval.
4. **Pool:** Approved shop-month rows enter an administrator-only observation table with contribution provenance.
5. **Aggregate:** National and provincial benchmarks are refreshed automatically. A cohort is visible only when at least five distinct contributors are represented; raw shop figures are never published.'
where id = '33333333-3333-4333-8333-333333333332';
