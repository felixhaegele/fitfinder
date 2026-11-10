-- Public insoles (#122, ADR 0014): anyone can list a shoe's measured insoles and fetch one
-- insole's outline, with shoe data only; the rows behind them stay private, and only the
-- newest results of done submissions count.
--
-- The local database is shared with e2e runs, so every assertion is limited to this
-- file's shoe models. created_at is set explicitly, as in 95_shoe_fit_summary.
begin;
create extension if not exists pgtap with schema extensions;
select plan(24);

insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-0000000097a1', 'insole-a@example.com'),
  ('00000000-0000-0000-0000-0000000097b2', 'insole-b@example.com');
insert into public.shoe_models (id, brand, model, year) values
  ('10000000-0000-0000-0000-000000000971', 'Insolebrand97', 'Alpha', 2024),
  ('10000000-0000-0000-0000-000000000972', 'Insolebrand97', 'Other', 2024);

-- Model 971:
--   s1 done, EU 44, left insole, used: two measurement versions (old 300 mm, new 270 mm);
--      the new one has two classifications (old narrow, new wide)
--   s2 done, EU 43, right insole, new: 280 mm, not classified yet
--   s3 rejected: measured, must not be listed
-- Model 972: s4 done, to check that one shoe's list doesn't include another's insoles.
insert into public.submissions
  (id, public_id, user_id, shoe_model_id, size, size_system, image_path, consent_at, insole_condition, status, rejection_reason)
values
  ('20000000-0000-0000-0000-000000000971', '40000000-0000-0000-0000-000000000971', '00000000-0000-0000-0000-0000000097a1', '10000000-0000-0000-0000-000000000971', 44, 'eu', '00000000-0000-0000-0000-0000000097a1/s1.jpg', now(), 'used', 'done', null),
  ('20000000-0000-0000-0000-000000000972', '40000000-0000-0000-0000-000000000972', '00000000-0000-0000-0000-0000000097a1', '10000000-0000-0000-0000-000000000971', 43, 'eu', '00000000-0000-0000-0000-0000000097a1/s2.jpg', now(), 'new', 'done', null),
  ('20000000-0000-0000-0000-000000000973', '40000000-0000-0000-0000-000000000973', '00000000-0000-0000-0000-0000000097a1', '10000000-0000-0000-0000-000000000971', 43, 'eu', '00000000-0000-0000-0000-0000000097a1/s3.jpg', now(), 'new', 'rejected', 'Markers not found.'),
  ('20000000-0000-0000-0000-000000000974', '40000000-0000-0000-0000-000000000974', '00000000-0000-0000-0000-0000000097a1', '10000000-0000-0000-0000-000000000972', 43, 'eu', '00000000-0000-0000-0000-0000000097a1/s4.jpg', now(), 'new', 'done', null);

-- The outline's second point carries the measurement's length, so the test can tell which
-- measurement's outline came back.
insert into public.measurements
  (id, submission_id, pipeline_version, length_mm, ball_width_mm, heel_width_mm, arch_width_mm, side, outline_mm, created_at)
select m.id::uuid, m.submission_id::uuid, m.version, m.length_mm, 100, 60, 75, m.side,
       (select jsonb_agg(jsonb_build_array(0, case when i = 1 then m.length_mm else i end)) from generate_series(0, 255) i),
       m.created_at::timestamptz
from (values
  ('30000000-0000-0000-0000-000000000971', '20000000-0000-0000-0000-000000000971', '1.0.0', 300, 'left', '2026-01-01'),
  ('30000000-0000-0000-0000-000000000972', '20000000-0000-0000-0000-000000000971', '1.10.0', 270, 'left', '2026-02-01'),
  ('30000000-0000-0000-0000-000000000973', '20000000-0000-0000-0000-000000000972', '1.0.0', 280, 'right', '2026-01-01'),
  ('30000000-0000-0000-0000-000000000974', '20000000-0000-0000-0000-000000000973', '1.0.0', 999, 'right', '2026-01-01'),
  ('30000000-0000-0000-0000-000000000975', '20000000-0000-0000-0000-000000000974', '1.0.0', 260, 'right', '2026-01-01')
) as m (id, submission_id, version, length_mm, side, created_at);

insert into public.classifications
  (measurement_id, classifier_version, width_class, arch_class, toe_box_shape, toe_shape, created_at)
select c.measurement_id::uuid, c.version, c.width_class, c.arch_class, c.toe_box_shape, c.toe_shape, c.created_at::timestamptz
from (values
  ('30000000-0000-0000-0000-000000000972', '1.0.0', 'narrow', 'low', 'pointed', 'egyptian', '2026-02-01'),
  ('30000000-0000-0000-0000-000000000972', '1.1.0', 'wide', 'medium', 'round', 'roman', '2026-03-01'),
  ('30000000-0000-0000-0000-000000000974', '1.0.0', 'narrow', 'low', 'pointed', 'egyptian', '2026-01-01')
) as c (measurement_id, version, width_class, arch_class, toe_box_shape, toe_shape, created_at);

-- ---------------------------------------------------------------------------
-- public_id
-- ---------------------------------------------------------------------------

select ok(
  (select public_id is not null and public_id <> id
   from public.submissions where id = '20000000-0000-0000-0000-000000000971'),
  'every submission has a public id, separate from its id'
);
select ok(
  not has_column_privilege('authenticated', 'public.submissions', 'public_id', 'insert')
  and not has_column_privilege('authenticated', 'public.submissions', 'public_id', 'update'),
  'users cannot choose or change the public id'
);

-- ---------------------------------------------------------------------------
-- The functions themselves: definer, pinned search_path, exact grants, fixed columns
-- ---------------------------------------------------------------------------

select ok(
  (select bool_and(prosecdef) from pg_proc
   where oid in ('public.shoe_insoles(uuid)'::regprocedure, 'public.shoe_insole(uuid)'::regprocedure)),
  'both functions are security definer'
);
select ok(
  (select bool_and('search_path=""' = any(proconfig)) from pg_proc
   where oid in ('public.shoe_insoles(uuid)'::regprocedure, 'public.shoe_insole(uuid)'::regprocedure)),
  'both functions pin an empty search_path'
);
select ok(
  (select bool_and(proacl is not null and not exists (select 1 from aclexplode(proacl) a where a.grantee = 0))
   from pg_proc
   where oid in ('public.shoe_insoles(uuid)'::regprocedure, 'public.shoe_insole(uuid)'::regprocedure)),
  'PUBLIC cannot execute either function'
);
select ok(
  has_function_privilege('anon', 'public.shoe_insoles(uuid)', 'execute')
  and has_function_privilege('authenticated', 'public.shoe_insoles(uuid)', 'execute')
  and has_function_privilege('anon', 'public.shoe_insole(uuid)', 'execute')
  and has_function_privilege('authenticated', 'public.shoe_insole(uuid)', 'execute'),
  'anon and authenticated can execute both functions'
);
-- The output columns are the privacy boundary. Adding one is a deliberate decision
-- (ADR 0014): shoe data only, never user_id, image paths, dates or the submission id.
select is(
  pg_get_function_result('public.shoe_insoles(uuid)'::regprocedure),
  'TABLE(insole_id uuid, size numeric, size_system text, insole_condition text, side text, '
  'length_mm numeric, ball_width_mm numeric, heel_width_mm numeric, arch_width_mm numeric, '
  'width_class text, arch_class text, toe_box_shape text, toe_shape text)',
  'shoe_insoles returns shoe data columns only'
);
select is(
  pg_get_function_result('public.shoe_insole(uuid)'::regprocedure),
  'TABLE(insole_id uuid, shoe_model_id uuid, brand text, model text, year smallint, '
  'size numeric, size_system text, insole_condition text, side text, '
  'length_mm numeric, ball_width_mm numeric, heel_width_mm numeric, arch_width_mm numeric, '
  'width_class text, arch_class text, toe_box_shape text, toe_shape text, outline_mm jsonb)',
  'shoe_insole returns shoe data columns and the outline only'
);

-- ---------------------------------------------------------------------------
-- As anon
-- ---------------------------------------------------------------------------
set local role anon;
select set_config('request.jwt.claims', '{"role": "anon"}', true);

select is_empty($$select id from public.submissions where shoe_model_id = '10000000-0000-0000-0000-000000000971'$$,
  'anon cannot read submissions');
select is_empty($$select id from public.measurements where id::text like '30000000-0000-0000-0000-0000000009_%'
                  and submission_id::text like '20000000-0000-0000-0000-00000000097%'$$,
  'anon cannot read measurements');

select results_eq(
  $$select insole_id, size, size_system, insole_condition, side, length_mm, width_class, toe_shape
    from public.shoe_insoles('10000000-0000-0000-0000-000000000971')$$,
  $$values ('40000000-0000-0000-0000-000000000972'::uuid, 43.0::numeric, 'eu'::text, 'new'::text, 'right'::text,
            280.00::numeric, null::text, null::text),
           ('40000000-0000-0000-0000-000000000971'::uuid, 44.0::numeric, 'eu'::text, 'used'::text, 'left'::text,
            270.00::numeric, 'wide'::text, 'roman'::text)$$,
  'one row per done insole, newest results, ordered by size; unclassified labels are null'
);
select is_empty(
  $$select 1 from public.shoe_insoles('10000000-0000-0000-0000-000000000971')
    where insole_id = '40000000-0000-0000-0000-000000000973'$$,
  'a rejected insole is not listed'
);
select is((select count(*) from public.shoe_insoles('10000000-0000-0000-0000-000000000972'))::int, 1,
  'another shoe only lists its own insoles');
select is_empty($$select 1 from public.shoe_insoles('00000000-0000-0000-0000-000000000000')$$,
  'an unknown shoe has no insoles');

create temporary table insole on commit drop as
  select * from public.shoe_insole('40000000-0000-0000-0000-000000000971');

select is((select count(*) from insole)::int, 1, 'one insole by its public id');
select is((select brand || ' ' || model || ' ' || year from insole), 'Insolebrand97 Alpha 2024',
  'the insole names its shoe');
select is((select shoe_model_id from insole), '10000000-0000-0000-0000-000000000971'::uuid,
  'the insole names its shoe model id');
select is((select (outline_mm -> 1 ->> 1)::numeric from insole), 270::numeric,
  'the outline is the newest measurement''s');
select is((select jsonb_array_length(outline_mm) from insole), 256, 'the whole outline is returned');
select is_empty($$select 1 from public.shoe_insole('40000000-0000-0000-0000-000000000973')$$,
  'a rejected insole cannot be fetched');
select is_empty($$select 1 from public.shoe_insole('20000000-0000-0000-0000-000000000971')$$,
  'the submission id does not work as a public id');

-- ---------------------------------------------------------------------------
-- As user B, who uploaded nothing
-- ---------------------------------------------------------------------------
reset role;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub": "00000000-0000-0000-0000-0000000097b2", "role": "authenticated"}', true);

select is_empty($$select id from public.submissions where shoe_model_id = '10000000-0000-0000-0000-000000000971'$$,
  'other users cannot read the submissions behind the insoles');
select is((select count(*) from public.shoe_insoles('10000000-0000-0000-0000-000000000971'))::int, 2,
  'logged-in users get the same insole list');

-- ---------------------------------------------------------------------------
-- Deleting the account removes the insoles
-- ---------------------------------------------------------------------------
reset role;
delete from auth.users where id = '00000000-0000-0000-0000-0000000097a1';
select is_empty($$select 1 from public.shoe_insoles('10000000-0000-0000-0000-000000000971')$$,
  'deleting the uploader removes their insoles from the list');

select * from finish();
rollback;
