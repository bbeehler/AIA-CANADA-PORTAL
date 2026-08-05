alter table public.resources
  add column if not exists delivery_type text not null default 'internal'
    check (delivery_type in ('internal', 'external')),
  add column if not exists content_format text not null default 'markdown'
    check (content_format in ('markdown', 'html'));

update public.resources
set
  delivery_type = case
    when nullif(btrim(external_url), '') is not null then 'external'
    else 'internal'
  end,
  content_format = 'markdown';

update public.resources
set external_url = null
where nullif(btrim(external_url), '') is null;

alter table public.resources
  drop constraint if exists resources_published_actionable_check,
  add constraint resources_delivery_content_check
    check (
      (delivery_type = 'external' and nullif(btrim(content), '') is null)
      or
      (delivery_type = 'internal' and nullif(btrim(external_url), '') is null)
    ),
  add constraint resources_external_url_https_check
    check (
      nullif(btrim(external_url), '') is null
      or external_url ~* '^https://[^[:space:]]+$'
    ),
  add constraint resources_published_actionable_check
    check (
      status <> 'published'
      or (
        delivery_type = 'external'
        and nullif(btrim(external_url), '') is not null
      )
      or (
        delivery_type = 'internal'
        and nullif(btrim(content), '') is not null
      )
    );

comment on column public.resources.delivery_type is
  'How members access the resource: inside the portal or through an external HTTPS link.';
comment on column public.resources.content_format is
  'Rendering format for internal content. HTML is sanitized by the application before storage and display.';
