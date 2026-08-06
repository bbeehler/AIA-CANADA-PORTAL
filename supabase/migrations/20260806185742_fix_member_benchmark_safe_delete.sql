-- Preserve the existing function while adding the explicit predicate required
-- by Supabase's safe-update protection.
do $migration$
declare
  function_definition text;
  unsafe_statement constant text :=
    'delete from public.member_benchmark_aggregates;';
  safe_statement constant text :=
    'delete from public.member_benchmark_aggregates where id is not null;';
begin
  select pg_get_functiondef(
    'public.rebuild_member_benchmark_aggregates()'::regprocedure
  )
  into function_definition;

  if position(safe_statement in function_definition) > 0 then
    raise notice 'Safe aggregate delete is already installed.';
    return;
  end if;

  if position(unsafe_statement in function_definition) = 0 then
    raise exception
      'Expected aggregate delete statement was not found; migration stopped.';
  end if;

  function_definition := replace(
    function_definition,
    unsafe_statement,
    safe_statement
  );
  execute function_definition;
end;
$migration$;

-- Preserve the intended API boundary explicitly.
revoke execute on function public.rebuild_member_benchmark_aggregates()
  from public, anon;
grant execute on function public.rebuild_member_benchmark_aggregates()
  to authenticated;
