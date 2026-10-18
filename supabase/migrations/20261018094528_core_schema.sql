-- Core schema: profiles, shoe_models, submissions, measurements, classifications.
--
-- Raw upload (submissions), measured values (measurements, per pipeline_version) and
-- classifier output (classifications, per classifier_version) live in separate tables,
-- so either step can be re-run later without touching the originals (ADR 0002).
--
-- Access model:
--   anon          read shoe_models, nothing else
--   authenticated read/create shoe_models; read/insert/delete own submissions;
--                 read measurements/classifications of own submissions
--   service_role  (worker) bypasses RLS: sets status, writes measurements/classifications
--
-- Classifier labels are text + check constraint rather than Postgres enums: enum values
-- can't be removed, and these labels will change as the classifier evolves.

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- profiles: one row per auth user, created automatically on sign-up
-- ---------------------------------------------------------------------------

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "profiles: users read their own"
  on public.profiles for select
  to authenticated
  using (id = (select auth.uid()));

-- Rows are created by the trigger below and removed by cascade; users never write here.
revoke insert, update, delete on public.profiles from anon, authenticated;

-- Runs as the function owner (security definer) because the signing-up user can't
-- insert into profiles themselves. search_path is pinned so it can't be hijacked.
create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id) values (new.id);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- shoe_models: public catalogue, extendable by logged-in users
-- ---------------------------------------------------------------------------

create table public.shoe_models (
  id uuid primary key default gen_random_uuid(),
  brand text not null check (length(trim(brand)) between 1 and 100),
  model text not null check (length(trim(model)) between 1 and 200),
  year smallint not null check (year between 1990 and 2100),
  created_by uuid default auth.uid() references public.profiles (id) on delete set null,
  created_at timestamptz not null default now()
);

-- "Shimano RC7 2023" and "shimano rc7  2023" are the same shoe.
create unique index shoe_models_brand_model_year_key
  on public.shoe_models (lower(trim(brand)), lower(trim(model)), year);

alter table public.shoe_models enable row level security;

create policy "shoe_models: anyone can read"
  on public.shoe_models for select
  to anon, authenticated
  using (true);

create policy "shoe_models: logged-in users can add"
  on public.shoe_models for insert
  to authenticated
  with check (created_by = (select auth.uid()));

-- Users may only supply these columns; id, created_by and created_at come from defaults.
revoke insert, update on public.shoe_models from anon, authenticated;
grant insert (brand, model, year) on public.shoe_models to authenticated;

-- ---------------------------------------------------------------------------
-- submissions: one uploaded insole photo + what the user told us about it
-- ---------------------------------------------------------------------------

create table public.submissions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  shoe_model_id uuid not null references public.shoe_models (id) on delete restrict,
  size numeric(4, 1) not null check (size > 0),
  size_system text not null check (size_system in ('eu', 'us_m', 'us_w', 'uk', 'mondopoint')),
  -- Path inside the private "insoles" storage bucket, always under the owner's folder (#12).
  image_path text not null,
  status text not null default 'queued'
    check (status in ('queued', 'processing', 'done', 'rejected', 'failed')),
  -- User-facing reason when status = 'rejected' (e.g. "markers not found").
  rejection_reason text,
  -- Explicit upload consent (GDPR / Swiss FADP). No default: the client must send it.
  consent_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (image_path like user_id::text || '/%'),
  check ((status = 'rejected') = (rejection_reason is not null))
);

create index submissions_user_id_idx on public.submissions (user_id);
create index submissions_shoe_model_id_idx on public.submissions (shoe_model_id);

create trigger submissions_set_updated_at
  before update on public.submissions
  for each row execute function public.set_updated_at();

alter table public.submissions enable row level security;

create policy "submissions: users read their own"
  on public.submissions for select
  to authenticated
  using (user_id = (select auth.uid()));

create policy "submissions: users create their own"
  on public.submissions for insert
  to authenticated
  with check (user_id = (select auth.uid()));

create policy "submissions: users delete their own"
  on public.submissions for delete
  to authenticated
  using (user_id = (select auth.uid()));

-- No update policy: status and results are set by the worker only.
-- Column grants: users can't choose status, rejection_reason, user_id or timestamps.
revoke insert, update on public.submissions from anon, authenticated;
grant insert (shoe_model_id, size, size_system, image_path, consent_at)
  on public.submissions to authenticated;

-- ---------------------------------------------------------------------------
-- measurements: millimetre values from one run of the measurement pipeline
-- ---------------------------------------------------------------------------

create table public.measurements (
  id uuid primary key default gen_random_uuid(),
  submission_id uuid not null references public.submissions (id) on delete cascade,
  pipeline_version text not null,
  length_mm numeric(6, 2) not null check (length_mm > 0),
  ball_width_mm numeric(6, 2) not null check (ball_width_mm > 0),
  heel_width_mm numeric(6, 2) not null check (heel_width_mm > 0),
  arch_width_mm numeric(6, 2) not null check (arch_width_mm > 0),
  -- Toe-box shape as a number (how quickly the insole narrows towards the toes);
  -- the label (round/square/pointed) is a classification.
  toe_taper numeric(6, 4),
  -- Room for measures added later, before they earn their own column.
  extra jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (submission_id, pipeline_version)
);

alter table public.measurements enable row level security;

create policy "measurements: users read those of their own submissions"
  on public.measurements for select
  to authenticated
  using (
    exists (
      select 1 from public.submissions s
      where s.id = submission_id and s.user_id = (select auth.uid())
    )
  );

revoke insert, update, delete on public.measurements from anon, authenticated;

-- ---------------------------------------------------------------------------
-- classifications: foot-shape labels from one classifier version
-- ---------------------------------------------------------------------------

create table public.classifications (
  id uuid primary key default gen_random_uuid(),
  measurement_id uuid not null references public.measurements (id) on delete cascade,
  classifier_version text not null,
  width_class text not null check (width_class in ('narrow', 'regular', 'wide')),
  arch_class text not null check (arch_class in ('low', 'medium', 'high')),
  toe_box_shape text not null check (toe_box_shape in ('round', 'square', 'pointed')),
  created_at timestamptz not null default now(),
  unique (measurement_id, classifier_version)
);

alter table public.classifications enable row level security;

create policy "classifications: users read those of their own submissions"
  on public.classifications for select
  to authenticated
  using (
    exists (
      select 1
      from public.measurements m
      join public.submissions s on s.id = m.submission_id
      where m.id = measurement_id and s.user_id = (select auth.uid())
    )
  );

revoke insert, update, delete on public.classifications from anon, authenticated;
