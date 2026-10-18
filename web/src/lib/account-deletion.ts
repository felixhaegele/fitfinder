// Account deletion (#31, ADR 0005). Pure logic with the Supabase calls passed in, so it
// can be unit-tested without a running Supabase. The server action wires in the real
// admin client (src/app/account/delete/actions.ts).

/** What the user has to type to confirm. Compared exactly (case-sensitive). */
export const CONFIRMATION_WORD = "DELETE";

export function isConfirmed(value: FormDataEntryValue | null): boolean {
  return typeof value === "string" && value.trim() === CONFIRMATION_WORD;
}

/** The bucket that holds every user image, in <user_id>/... folders. */
export const INSOLES_BUCKET = "insoles";

// The Storage API returns at most this many entries per list call; remove() accepts up
// to 1000 paths, so one page always fits in one remove call.
const PAGE_SIZE = 100;

type StorageResult<T> = Promise<{ data: T; error: null } | { data: null; error: { message: string } }>;

/** The slice of the Supabase Storage bucket client this module uses. */
export type BucketClient = {
  list(
    path: string,
    options: { limit: number; offset: number },
  ): StorageResult<{ name: string; id: string | null }[]>;
  remove(paths: string[]): StorageResult<unknown[]>;
};

/** The slice of the Supabase Auth admin client this module uses. */
export type AuthAdminClient = {
  deleteUser(id: string): Promise<{ error: { message: string } | null }>;
};

/**
 * All object paths under `folder`, including subfolders (e.g. <user_id>/processed/).
 * The Storage API lists one level at a time; folders come back with id === null.
 */
export async function listAllFiles(bucket: BucketClient, folder: string): Promise<string[]> {
  const files: string[] = [];
  for (let offset = 0; ; offset += PAGE_SIZE) {
    const { data, error } = await bucket.list(folder, { limit: PAGE_SIZE, offset });
    if (error) {
      throw new Error(`Listing ${folder} failed: ${error.message}`);
    }
    for (const entry of data) {
      const path = `${folder}/${entry.name}`;
      if (entry.id === null) {
        files.push(...(await listAllFiles(bucket, path)));
      } else {
        files.push(path);
      }
    }
    if (data.length < PAGE_SIZE) {
      return files;
    }
  }
}

/** Deletes every object under `<userId>/`. Safe to repeat. Returns how many it removed. */
export async function purgeUserFiles(bucket: BucketClient, userId: string): Promise<number> {
  // Never let a malformed id turn into a broader prefix (e.g. "" would mean the whole bucket).
  if (!/^[0-9a-f-]{36}$/i.test(userId)) {
    throw new Error("Refusing to purge files: invalid user id");
  }
  // List everything first, then delete: deleting while paging would shift the offsets.
  const paths = await listAllFiles(bucket, userId);
  for (let i = 0; i < paths.length; i += PAGE_SIZE) {
    const { error } = await bucket.remove(paths.slice(i, i + PAGE_SIZE));
    if (error) {
      throw new Error(`Removing files failed: ${error.message}`);
    }
  }
  return paths.length;
}

/**
 * Deletes a user and everything they own, in this order:
 *
 * 1. Purge their files. First, because Supabase refuses to delete a user who still owns
 *    storage objects, and because afterwards nothing would point at leftover files.
 * 2. Delete the auth user. Foreign keys cascade to profiles, submissions, measurements
 *    and classifications (pgTAP: supabase/tests/database/90_account_deletion.test.sql).
 * 3. Purge again, for a file the worker may have written between 1 and 2
 *    (the processed copy of an in-flight submission).
 *
 * Steps 1 and 2 are idempotent: if one fails, this throws and the user can try again.
 * Step 3 runs after the account is already gone, so its failure is only logged for the
 * operator (the leftover file is in a folder nobody can access any more) instead of
 * telling the user that a deletion that did happen had failed.
 */
export async function deleteAccount(
  deps: { bucket: BucketClient; authAdmin: AuthAdminClient },
  userId: string,
): Promise<void> {
  await purgeUserFiles(deps.bucket, userId);

  const { error } = await deps.authAdmin.deleteUser(userId);
  if (error) {
    throw new Error(`Deleting user failed: ${error.message}`);
  }

  try {
    await purgeUserFiles(deps.bucket, userId);
  } catch (err) {
    console.error(`Account ${userId} deleted, but the final file purge failed:`, err);
  }
}
