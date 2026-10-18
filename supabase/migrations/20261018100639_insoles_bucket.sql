-- Private storage bucket for raw insole photos.
--
-- Layout: insoles/<user_id>/<file>. submissions.image_path enforces the same prefix,
-- so a submission can only point at a photo in its owner's folder.
--
-- Access model:
--   anon          nothing
--   authenticated upload, read and delete files in their own <user_id>/ folder only.
--                 No update: a photo can't be overwritten after upload (we keep the raw
--                 image so old submissions can be re-processed).
--   service_role  (worker) bypasses RLS: downloads photos for measuring.
--
-- The bucket is private, so files are only reachable through signed URLs that expire.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'insoles',
  'insoles',
  false,
  10 * 1024 * 1024, -- 10 MiB: plenty for a phone photo re-encoded in the browser (#28)
  array['image/jpeg', 'image/png', 'image/webp']
);

-- storage.objects already has RLS enabled by Supabase; these policies add access to
-- this bucket. (storage.foldername(name))[1] is the first folder in the path.

create policy "insoles: users read their own photos"
  on storage.objects for select
  to authenticated
  using (
    bucket_id = 'insoles'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );

create policy "insoles: users upload into their own folder"
  on storage.objects for insert
  to authenticated
  with check (
    bucket_id = 'insoles'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );

create policy "insoles: users delete their own photos"
  on storage.objects for delete
  to authenticated
  using (
    bucket_id = 'insoles'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );
