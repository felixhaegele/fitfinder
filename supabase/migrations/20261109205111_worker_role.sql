-- A restricted database role for the measurement worker (#33).
--
-- Until now the worker connected as `postgres`, which can do anything. On Cloud Run it
-- logs in as `worker` instead, which can only do what store.py needs:
--
--   - the `submissions` queue: read messages, change their visibility, archive them.
--     Not send (only the insert trigger does that) and no other queue;
--   - submissions: read the four columns it loads, set status / rejection_reason /
--     processed_image_path. Not insert, delete, or change who or which photo;
--   - measurements and classifications: insert results (plus read back the new id).
--
-- Nothing else: no profiles, shoe models, storage, auth or private schema. Photos are
-- still fetched with the secret key over the Storage API; that's outside this role.
-- supabase/tests/database/96_worker_role.test.sql pins the exact list of grants.
--
-- The role has no password here: passwords don't belong in migrations. Locally seed.sql
-- sets one; on staging and prod the owner sets it once (infra/README.md).

-- Roles belong to the whole Postgres cluster, not one database, so a local
-- `supabase db reset` may find it already there.
do $$
begin
  if not exists (select from pg_roles where rolname = 'worker') then
    create role worker nologin;
  end if;
end;
$$;

-- ---------------------------------------------------------------------------
-- Queue. pgmq's functions run with the caller's rights and are executable by everyone,
-- so access is decided by the queue's tables: q_submissions holds the waiting messages,
-- a_submissions the archived ones.
-- ---------------------------------------------------------------------------

grant usage on schema pgmq to worker;
-- read = update read_ct/vt ... returning; set_vt = update; archive = delete + insert.
-- Delete also allows purging this queue; pgmq has no narrower right for archive.
grant select, update, delete on pgmq.q_submissions to worker;
-- archive's insert ends with `returning msg_id`, which needs select on that column.
grant insert, select (msg_id) on pgmq.a_submissions to worker;

-- ---------------------------------------------------------------------------
-- Tables. RLS applies to `worker` like to any other role that isn't service_role, so
-- each grant comes with a policy. The policies match every row: the worker handles
-- everyone's submissions; the column grants are what limit it.
-- ---------------------------------------------------------------------------

grant select (id, user_id, image_path, status) on public.submissions to worker;
grant update (status, rejection_reason, processed_image_path) on public.submissions to worker;

create policy "submissions: worker reads all"
  on public.submissions for select
  to worker
  using (true);

-- Also needed for `select ... for update`, which the worker uses to lock a row.
create policy "submissions: worker updates results"
  on public.submissions for update
  to worker
  using (true)
  with check (true);

grant insert on public.measurements to worker;
-- `insert ... returning id` needs to read the id back, so select on that column only.
grant select (id) on public.measurements to worker;

create policy "measurements: worker adds results"
  on public.measurements for insert
  to worker
  with check (true);

create policy "measurements: worker reads back ids"
  on public.measurements for select
  to worker
  using (true);

grant insert on public.classifications to worker;

create policy "classifications: worker adds results"
  on public.classifications for insert
  to worker
  with check (true);
