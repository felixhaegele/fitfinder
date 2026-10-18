-- The worker's cleaned copy of the photo, kept next to the original upload.
--
-- image_path            original upload, re-encoded in the browser (untrusted: a client
--                       can skip that step)
-- processed_image_path  re-encoded on the server by the worker (#29): checked file type,
--                       orientation applied, no metadata. Null until the worker made it.
--
-- Both live in the private insoles bucket under the owner's folder, so the existing
-- storage policies let the owner view them and account deletion (#31) removes both.
-- Convention: <user_id>/processed/<submission_id>.jpg

alter table public.submissions
  add column processed_image_path text,
  add constraint submissions_processed_image_path_owner
    check (processed_image_path like user_id::text || '/processed/%');

-- Not added to the insert grant: only the worker (service role) sets it.
