-- Guard rail: every table in the public schema must have Row-Level Security enabled.
-- The browser talks to Postgres directly (ADR 0002), so a table without RLS is readable
-- by anyone with the anon key. This test fails the moment someone forgets.
begin;
create extension if not exists pgtap with schema extensions;
select plan(1);

select is_empty(
  $$
    select c.relname
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relkind in ('r', 'p')  -- ordinary and partitioned tables
      and not c.relrowsecurity
  $$,
  'every table in public has RLS enabled'
);

select * from finish();
rollback;
