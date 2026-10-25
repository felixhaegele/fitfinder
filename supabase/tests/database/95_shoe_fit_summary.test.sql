-- Public shoe fit summary (#92, ADR 0011): anyone can read shoe-level aggregates, nobody
-- but the owner can read the rows behind them, and only the newest results of done
-- submissions count.
--
-- The local database is shared with e2e runs, so every assertion is limited to this
-- file's shoe models. created_at is set explicitly: now() is the same for the whole
-- transaction, so "newest" would otherwise be decided by luck.
begin;
create extension if not exists pgtap with schema extensions;
select plan(31);

insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-0000000092a1', 'fit-a@example.com'),
  ('00000000-0000-0000-0000-0000000092b2', 'fit-b@example.com');
insert into public.shoe_models (id, brand, model, year) values
  ('10000000-0000-0000-0000-000000000921', 'Fitbrand92', 'Alpha Pro', 2023),
  ('10000000-0000-0000-0000-000000000922', 'Fitbrand92', 'Only Rejected', 2023);

-- Model 921:
--   s1 done, EU 43: two measurement versions (old 300 mm, new 270 mm); the new one has two
--      classifications (old narrow, new wide)
--   s2 done, EU 44: 280 mm, wide / high / square / greek
--   s3 done, EU 44: 290 mm, not classified yet
--   s4 rejected, s5 failed, s6 processing: measured and classified narrow, must not count
--   s7 queued, s8 done without a measurement: must not count
-- If anything that must not count did count, "narrow" would win the width vote and the
-- median length would move.
-- Model 922: only a rejected submission, so it must not be listed.
insert into public.submissions
  (id, user_id, shoe_model_id, size, size_system, image_path, consent_at, insole_condition, status, rejection_reason)
values
  ('20000000-0000-0000-0000-000000000921', '00000000-0000-0000-0000-0000000092a1', '10000000-0000-0000-0000-000000000921', 43, 'eu', '00000000-0000-0000-0000-0000000092a1/s1.jpg', now(), 'new', 'done', null),
  ('20000000-0000-0000-0000-000000000922', '00000000-0000-0000-0000-0000000092a1', '10000000-0000-0000-0000-000000000921', 44, 'eu', '00000000-0000-0000-0000-0000000092a1/s2.jpg', now(), 'new', 'done', null),
  ('20000000-0000-0000-0000-000000000923', '00000000-0000-0000-0000-0000000092a1', '10000000-0000-0000-0000-000000000921', 44, 'eu', '00000000-0000-0000-0000-0000000092a1/s3.jpg', now(), 'used', 'done', null),
  ('20000000-0000-0000-0000-000000000924', '00000000-0000-0000-0000-0000000092a1', '10000000-0000-0000-0000-000000000921', 43, 'eu', '00000000-0000-0000-0000-0000000092a1/s4.jpg', now(), 'new', 'rejected', 'Markers not found.'),
  ('20000000-0000-0000-0000-000000000925', '00000000-0000-0000-0000-0000000092a1', '10000000-0000-0000-0000-000000000921', 43, 'eu', '00000000-0000-0000-0000-0000000092a1/s5.jpg', now(), 'new', 'failed', null),
  ('20000000-0000-0000-0000-000000000926', '00000000-0000-0000-0000-0000000092a1', '10000000-0000-0000-0000-000000000921', 43, 'eu', '00000000-0000-0000-0000-0000000092a1/s6.jpg', now(), 'new', 'processing', null),
  ('20000000-0000-0000-0000-000000000927', '00000000-0000-0000-0000-0000000092a1', '10000000-0000-0000-0000-000000000921', 43, 'eu', '00000000-0000-0000-0000-0000000092a1/s7.jpg', now(), 'new', 'queued', null),
  ('20000000-0000-0000-0000-000000000928', '00000000-0000-0000-0000-0000000092a1', '10000000-0000-0000-0000-000000000921', 43, 'eu', '00000000-0000-0000-0000-0000000092a1/s8.jpg', now(), 'new', 'done', null),
  ('20000000-0000-0000-0000-000000000929', '00000000-0000-0000-0000-0000000092a1', '10000000-0000-0000-0000-000000000922', 43, 'eu', '00000000-0000-0000-0000-0000000092a1/s9.jpg', now(), 'new', 'rejected', 'Too blurry.');

insert into public.measurements
  (id, submission_id, pipeline_version, length_mm, ball_width_mm, heel_width_mm, arch_width_mm, side, outline_mm, created_at)
select m.id::uuid, m.submission_id::uuid, m.version, m.length_mm, 100, 60, 75, 'right',
       (select jsonb_agg(jsonb_build_array(0, i)) from generate_series(0, 255) i), m.created_at::timestamptz
from (values
  ('30000000-0000-0000-0000-000000000911', '20000000-0000-0000-0000-000000000921', '1.0.0', 300, '2026-01-01'),
  ('30000000-0000-0000-0000-000000000912', '20000000-0000-0000-0000-000000000921', '1.10.0', 270, '2026-02-01'),
  ('30000000-0000-0000-0000-000000000920', '20000000-0000-0000-0000-000000000922', '1.0.0', 280, '2026-01-01'),
  ('30000000-0000-0000-0000-000000000930', '20000000-0000-0000-0000-000000000923', '1.0.0', 290, '2026-01-01'),
  ('30000000-0000-0000-0000-000000000940', '20000000-0000-0000-0000-000000000924', '1.0.0', 999, '2026-01-01'),
  ('30000000-0000-0000-0000-000000000950', '20000000-0000-0000-0000-000000000925', '1.0.0', 999, '2026-01-01'),
  ('30000000-0000-0000-0000-000000000960', '20000000-0000-0000-0000-000000000926', '1.0.0', 999, '2026-01-01'),
  ('30000000-0000-0000-0000-000000000990', '20000000-0000-0000-0000-000000000929', '1.0.0', 999, '2026-01-01')
) as m (id, submission_id, version, length_mm, created_at);

insert into public.classifications
  (measurement_id, classifier_version, width_class, arch_class, toe_box_shape, toe_shape, created_at)
select c.measurement_id::uuid, c.version, c.width_class, c.arch_class, c.toe_box_shape, c.toe_shape, c.created_at::timestamptz
from (values
  -- old classifier version on the old measurement, and on the new one: both ignored
  ('30000000-0000-0000-0000-000000000911', '1.0.0', 'narrow', 'low', 'pointed', 'egyptian', '2026-01-01'),
  ('30000000-0000-0000-0000-000000000912', '1.0.0', 'narrow', 'low', 'pointed', 'egyptian', '2026-02-01'),
  ('30000000-0000-0000-0000-000000000912', '1.1.0', 'wide', 'medium', 'round', 'roman', '2026-03-01'),
  ('30000000-0000-0000-0000-000000000920', '1.0.0', 'wide', 'high', 'square', 'greek', '2026-01-01'),
  ('30000000-0000-0000-0000-000000000940', '1.0.0', 'narrow', 'low', 'pointed', 'egyptian', '2026-01-01'),
  ('30000000-0000-0000-0000-000000000950', '1.0.0', 'narrow', 'low', 'pointed', 'egyptian', '2026-01-01'),
  ('30000000-0000-0000-0000-000000000960', '1.0.0', 'narrow', 'low', 'pointed', 'egyptian', '2026-01-01'),
  ('30000000-0000-0000-0000-000000000990', '1.0.0', 'narrow', 'low', 'pointed', 'egyptian', '2026-01-01')
) as c (measurement_id, version, width_class, arch_class, toe_box_shape, toe_shape, created_at);

-- ---------------------------------------------------------------------------
-- The functions themselves: definer, pinned search_path, exact grants, fixed columns
-- ---------------------------------------------------------------------------

select ok(
  (select bool_and(prosecdef) from pg_proc
   where oid in ('public.shoe_fit_summaries(text)'::regprocedure, 'public.shoe_fit_by_size(uuid)'::regprocedure)),
  'both functions are security definer'
);
select ok(
  (select bool_and('search_path=""' = any(proconfig)) from pg_proc
   where oid in ('public.shoe_fit_summaries(text)'::regprocedure, 'public.shoe_fit_by_size(uuid)'::regprocedure)),
  'both functions pin an empty search_path'
);
-- A null ACL means "default", which includes PUBLIC, so it must be set explicitly.
select ok(
  (select bool_and(proacl is not null and not exists (select 1 from aclexplode(proacl) a where a.grantee = 0))
   from pg_proc
   where oid in ('public.shoe_fit_summaries(text)'::regprocedure, 'public.shoe_fit_by_size(uuid)'::regprocedure)),
  'PUBLIC cannot execute either function'
);
select ok(
  has_function_privilege('anon', 'public.shoe_fit_summaries(text)', 'execute')
  and has_function_privilege('authenticated', 'public.shoe_fit_summaries(text)', 'execute')
  and has_function_privilege('anon', 'public.shoe_fit_by_size(uuid)', 'execute')
  and has_function_privilege('authenticated', 'public.shoe_fit_by_size(uuid)', 'execute'),
  'anon and authenticated can execute both functions'
);
-- The output columns are the privacy boundary. Adding one is a deliberate decision
-- (ADR 0011): shoe-level only, never user_id, image paths, dates or outlines.
select is(
  pg_get_function_result('public.shoe_fit_summaries(text)'::regprocedure),
  'TABLE(shoe_model_id uuid, brand text, model text, year smallint, submission_count integer, '
  'median_length_mm numeric, median_ball_width_mm numeric, median_heel_width_mm numeric, '
  'median_arch_width_mm numeric, width_class text, arch_class text, toe_box_shape text, toe_shape text)',
  'shoe_fit_summaries returns shoe-level columns only'
);
select is(
  pg_get_function_result('public.shoe_fit_by_size(uuid)'::regprocedure),
  'TABLE(size numeric, size_system text, submission_count integer, '
  'median_length_mm numeric, median_ball_width_mm numeric, median_heel_width_mm numeric, '
  'median_arch_width_mm numeric, width_class text, arch_class text, toe_box_shape text, toe_shape text)',
  'shoe_fit_by_size returns shoe-level columns only'
);

-- ---------------------------------------------------------------------------
-- As anon
-- ---------------------------------------------------------------------------
set local role anon;
select set_config('request.jwt.claims', '{"role": "anon"}', true);

select is_empty($$select id from public.submissions where shoe_model_id = '10000000-0000-0000-0000-000000000921'$$,
  'anon cannot read submissions');
select is_empty($$select id from public.measurements where id::text like '30000000-0000-0000-0000-0000000009%'$$,
  'anon cannot read measurements');
select is_empty($$select id from public.classifications where measurement_id::text like '30000000-0000-0000-0000-0000000009%'$$,
  'anon cannot read classifications');
select throws_ok('select * from private.latest_fit_results', '42501', null,
  'anon cannot read the private helper view');

create temporary table summary on commit drop as
  select * from public.shoe_fit_summaries() where shoe_model_id = '10000000-0000-0000-0000-000000000921';

select is((select count(*) from summary)::int, 1, 'anon gets one summary row for the measured shoe');
select is((select submission_count from summary), 3,
  'only done submissions with a measurement count (not rejected, failed, processing, queued)');
select is((select median_length_mm from summary), 280.00::numeric,
  'median length uses the newest measurement of done submissions only');
select is((select width_class from summary), 'wide',
  'most common width uses the newest classification of done submissions only');
select is((select arch_class from summary), 'high',
  'ties go to the first label alphabetically; unclassified submissions add no label');
select is((select toe_shape from summary), 'greek', 'toe shape is aggregated too');
select is((select brand || ' ' || model || ' ' || year from summary), 'Fitbrand92 Alpha Pro 2023',
  'the shoe is named');
select is_empty(
  $$select 1 from public.shoe_fit_summaries() where shoe_model_id = '10000000-0000-0000-0000-000000000922'$$,
  'a shoe with only rejected submissions is not listed'
);

-- Search: every word must appear in "brand model year", as plain text
select is((select count(*) from public.shoe_fit_summaries('  fitbrand92   ALPHA ')
           where shoe_model_id = '10000000-0000-0000-0000-000000000921')::int, 1,
  'search is case-insensitive and ignores extra spaces');
select is((select count(*) from public.shoe_fit_summaries('pro 2023')
           where shoe_model_id = '10000000-0000-0000-0000-000000000921')::int, 1,
  'search matches across model and year');
select is((select count(*) from public.shoe_fit_summaries('alpha nope')
           where shoe_model_id = '10000000-0000-0000-0000-000000000921')::int, 0,
  'every word must match');
select is((select count(*) from public.shoe_fit_summaries('%')
           where shoe_model_id = '10000000-0000-0000-0000-000000000921')::int, 0,
  '% is not a wildcard');
select is((select count(*) from public.shoe_fit_summaries('')
           where shoe_model_id = '10000000-0000-0000-0000-000000000921')::int, 1,
  'an empty search lists everything');

-- Per size
select results_eq(
  $$select size, size_system, submission_count, median_length_mm, width_class, arch_class
    from public.shoe_fit_by_size('10000000-0000-0000-0000-000000000921')$$,
  $$values (43.0::numeric, 'eu'::text, 1, 270.00::numeric, 'wide'::text, 'medium'::text),
           (44.0::numeric, 'eu'::text, 2, 285.00::numeric, 'wide'::text, 'high'::text)$$,
  'per size: newest results of done submissions, grouped by size'
);
select is_empty($$select 1 from public.shoe_fit_by_size('10000000-0000-0000-0000-000000000922')$$,
  'per size: nothing for a shoe without done submissions');

-- ---------------------------------------------------------------------------
-- As user B, who uploaded nothing
-- ---------------------------------------------------------------------------
reset role;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub": "00000000-0000-0000-0000-0000000092b2", "role": "authenticated"}', true);

select is_empty($$select id from public.submissions where shoe_model_id = '10000000-0000-0000-0000-000000000921'$$,
  'other users cannot read the submissions behind the summary');
select is_empty($$select id from public.measurements where id::text like '30000000-0000-0000-0000-0000000009%'$$,
  'other users cannot read the measurements behind the summary');
select is_empty($$select id from public.classifications where measurement_id::text like '30000000-0000-0000-0000-0000000009%'$$,
  'other users cannot read the classifications behind the summary');
select is((select submission_count from public.shoe_fit_summaries()
           where shoe_model_id = '10000000-0000-0000-0000-000000000921'), 3,
  'logged-in users get the same summary');
select is((select count(*) from public.shoe_fit_by_size('10000000-0000-0000-0000-000000000921'))::int, 2,
  'logged-in users get the per-size summary');

-- ---------------------------------------------------------------------------
-- Deleting the account removes the data from the summary
-- ---------------------------------------------------------------------------
reset role;
delete from auth.users where id = '00000000-0000-0000-0000-0000000092a1';
select is_empty(
  $$select 1 from public.shoe_fit_summaries() where shoe_model_id = '10000000-0000-0000-0000-000000000921'$$,
  'deleting the uploader removes their insoles from the summary'
);

select * from finish();
rollback;
