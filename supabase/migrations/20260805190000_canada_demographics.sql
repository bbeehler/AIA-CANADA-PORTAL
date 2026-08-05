create table public.demographic_geographies (
  geo_uid text primary key,
  geo_level text not null check (geo_level in ('province', 'municipality', 'postal_region')),
  geo_code text not null,
  geo_name text not null,
  province_code text not null check (province_code ~ '^[A-Z]{2}$'),
  census_year smallint not null check (census_year between 1900 and 2200),
  source_flow text not null check (source_flow in ('DF_PR', 'DF_CSD', 'DF_FSA')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (geo_level, census_year, geo_code)
);

create table public.demographic_metrics (
  metric_code text primary key check (metric_code ~ '^[a-z0-9]+(?:_[a-z0-9]+)*$'),
  label text not null,
  category text not null check (category in ('Population', 'Households', 'Age', 'Income', 'Workforce')),
  unit text not null check (unit in ('count', 'percent', 'years', 'cad', 'people_per_square_km')),
  description text not null default '',
  sort_order integer not null default 0
);

create table public.demographic_observations (
  geography_id text not null references public.demographic_geographies(geo_uid) on delete cascade,
  metric_code text not null references public.demographic_metrics(metric_code) on delete restrict,
  reference_period text not null,
  value numeric not null,
  source_characteristic_id text not null,
  source_characteristic_name text not null,
  source_flow text not null,
  source_url text not null,
  retrieved_at timestamptz not null default now(),
  primary key (geography_id, metric_code, reference_period)
);

create table public.demographic_sync_runs (
  id bigint generated always as identity primary key,
  source text not null default 'Statistics Canada 2021 Census Profile',
  status text not null check (status in ('running', 'completed', 'failed')),
  levels text[] not null default '{}',
  geography_count integer not null default 0 check (geography_count >= 0),
  observation_count integer not null default 0 check (observation_count >= 0),
  message text not null default '',
  started_at timestamptz not null default now(),
  completed_at timestamptz
);

create index demographic_geographies_level_province_name_idx
  on public.demographic_geographies (geo_level, province_code, geo_name);
create index demographic_observations_metric_reference_idx
  on public.demographic_observations (metric_code, reference_period);
create index demographic_sync_runs_started_idx
  on public.demographic_sync_runs (started_at desc);

create trigger demographic_geographies_set_updated_at
before update on public.demographic_geographies
for each row execute function private.set_updated_at();

alter table public.demographic_geographies enable row level security;
alter table public.demographic_metrics enable row level security;
alter table public.demographic_observations enable row level security;
alter table public.demographic_sync_runs enable row level security;

create policy demographic_geographies_member_read on public.demographic_geographies
for select to authenticated
using ((select private.is_active_member()));

create policy demographic_metrics_member_read on public.demographic_metrics
for select to authenticated
using ((select private.is_active_member()));

create policy demographic_observations_member_read on public.demographic_observations
for select to authenticated
using ((select private.is_active_member()));

create policy demographic_sync_runs_admin_read on public.demographic_sync_runs
for select to authenticated
using ((select private.is_admin()));

revoke all on public.demographic_geographies, public.demographic_metrics,
  public.demographic_observations, public.demographic_sync_runs from anon;
grant select on public.demographic_geographies, public.demographic_metrics,
  public.demographic_observations to authenticated;
grant select on public.demographic_sync_runs to authenticated;
grant all on public.demographic_geographies, public.demographic_metrics,
  public.demographic_observations, public.demographic_sync_runs to service_role;
grant usage, select on sequence public.demographic_sync_runs_id_seq to service_role;

insert into public.demographic_metrics
  (metric_code, label, category, unit, description, sort_order)
values
  ('population_2021', 'Population, 2021', 'Population', 'count', 'Usual resident population in the 2021 Census.', 10),
  ('population_2016', 'Population, 2016', 'Population', 'count', 'Usual resident population in the 2016 Census.', 20),
  ('population_growth_2016_2021', 'Population growth, 2016 to 2021', 'Population', 'percent', 'Percentage population change between the 2016 and 2021 censuses.', 30),
  ('population_density', 'Population density', 'Population', 'people_per_square_km', 'Population per square kilometre.', 40),
  ('total_private_dwellings', 'Total private dwellings', 'Households', 'count', 'All private dwellings in the geography.', 50),
  ('occupied_private_dwellings', 'Occupied private dwellings', 'Households', 'count', 'Private dwellings occupied by usual residents.', 60),
  ('average_household_size', 'Average household size', 'Households', 'count', 'Average number of persons in private households.', 70),
  ('one_person_households', 'One-person households', 'Households', 'count', 'Private households with one person.', 80),
  ('age_0_14', 'Population aged 0 to 14', 'Age', 'count', 'Population aged 0 to 14 years.', 90),
  ('age_15_64', 'Population aged 15 to 64', 'Age', 'count', 'Population aged 15 to 64 years.', 100),
  ('age_65_plus', 'Population aged 65 and over', 'Age', 'count', 'Population aged 65 years and over.', 110),
  ('median_age', 'Median age', 'Age', 'years', 'Median age of the population.', 120),
  ('median_household_income', 'Median household income, 2020', 'Income', 'cad', 'Median total household income in 2020 dollars.', 130),
  ('average_household_income', 'Average household income, 2020', 'Income', 'cad', 'Average total household income in 2020 dollars.', 140),
  ('median_after_tax_household_income', 'Median after-tax household income, 2020', 'Income', 'cad', 'Median after-tax household income in 2020 dollars; a spending-capacity context measure.', 150),
  ('average_after_tax_household_income', 'Average after-tax household income, 2020', 'Income', 'cad', 'Average after-tax household income in 2020 dollars; a spending-capacity context measure.', 160),
  ('participation_rate', 'Labour-force participation rate', 'Workforce', 'percent', 'Share of the population in the labour force.', 170),
  ('employment_rate', 'Employment rate', 'Workforce', 'percent', 'Share of the population that was employed.', 180),
  ('unemployment_rate', 'Unemployment rate', 'Workforce', 'percent', 'Share of the labour force that was unemployed.', 190)
on conflict (metric_code) do update set
  label = excluded.label,
  category = excluded.category,
  unit = excluded.unit,
  description = excluded.description,
  sort_order = excluded.sort_order;
