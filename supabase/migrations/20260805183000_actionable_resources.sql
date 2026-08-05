alter table public.resources
  add column if not exists content text not null default '';

update public.resources
set external_url = 'https://www.aiacanada.com/product/the-view-from-here-2015-productivity-benchmarks-in-the-canadian-automotive-service-sector/'
where id = '33333333-3333-4333-8333-333333333331';

update public.resources
set content = '### Review process

1. **Prepare:** Members use the standard template and remove customer, employee, vehicle and invoice identifiers.
2. **Validate:** The portal checks the file structure, reporting period, province and numeric values.
3. **Review:** AIA Canada reviews each submission before approval.
4. **Aggregate:** Approved information may be included only in anonymized industry benchmarks; raw shop files are not published.'
where id = '33333333-3333-4333-8333-333333333332';

alter table public.resources
  add constraint resources_published_actionable_check
  check (
    status <> 'published'
    or nullif(btrim(external_url), '') is not null
    or nullif(btrim(content), '') is not null
  );
