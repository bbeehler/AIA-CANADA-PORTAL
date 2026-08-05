alter table public.datasets
  add column if not exists dataset_type text not null default 'mixed'
    check (dataset_type in ('mixed', 'segment', 'performance'));

update public.datasets
set dataset_type = 'mixed'
where dataset_type is null;

comment on column public.datasets.dataset_type is
  'Validated data contract: mixed legacy dataset, regional/shop segment benchmarks, or performance cohort benchmarks.';
